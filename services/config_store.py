"""Configuração persistente do backend + perfis nomeados.

Tudo em JSON legível dentro de ``config/`` (gitignored):
- ``config/settings.json`` — configuração ativa (validada por pydantic);
- ``config/profiles/<slug>.json`` — perfis salvos pelo usuário.

Escrita sempre atômica (arquivo temporário no mesmo diretório + os.replace).
Arquivo corrompido nunca derruba o app: é renomeado para ``.corrupted.bak``
e os defaults são recriados, com evento registrado no log.
"""
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from services.app_logging import record_app_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
PROFILES_DIR = CONFIG_DIR / "profiles"

_lock = threading.RLock()
_settings_cache: Dict[str, Any] = {"settings": None, "mtime": None}

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LEGACY_WINDOWS_VOICE_IDS = {
    "preset_windows_1",
    "preset_windows_2",
    "preset_windows_3",
    "preset_windows_4",
    "speaker_1",
    "speaker_2",
    "speaker_3",
    "speaker_4",
}
_VOICE_SELECTION_KEYS = (
    "voice_id",
    "default_voice_id",
    "selected_voice_id",
    "identity_voice_id",
)
_VOICE_MAP_KEYS = (
    "speaker_voices",
    "speaker_voice_map",
)


# ------------------------------------------------------------------ modelos

class WhisperDefaults(BaseModel):
    model: str = "large-v3-turbo"
    device: Literal["cuda", "cpu"] = "cuda"
    compute_type: Literal["float32", "float16", "int8", "int8_float16"] = "float16"
    beam_size: int = Field(5, ge=1, le=10)
    language: str = "auto"
    vad_filter: bool = True
    cpu_threads: int = Field(8, ge=1, le=32)
    temperature: float = Field(0.0, ge=0.0, le=1.0)


class VibeVoiceAsrDefaults(BaseModel):
    diarization: bool = True
    chunk_length_seconds: float = Field(45.0, ge=15.0, le=90.0)
    temperature: float = Field(0.0, ge=0.0, le=1.0)
    repetition_penalty: float = Field(1.1, ge=1.0, le=1.5)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=0, le=100)
    num_beams: int = Field(1, ge=1, le=5)
    max_new_tokens: int = Field(2048, ge=256, le=8192)


class TtsDefaults(BaseModel):
    tts_model: Literal["tts_1_5b", "tts_large", "realtime_0_5b"] = "tts_1_5b"
    speaker_id: str = "speaker_1"
    temperature: float = Field(0.7, ge=0.1, le=1.2)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=0, le=100)
    repetition_penalty: float = Field(1.1, ge=1.0, le=1.5)
    speed: float = Field(1.0, ge=0.5, le=2.0)


class EngineDefaults(BaseModel):
    whisper: WhisperDefaults = Field(default_factory=WhisperDefaults)
    vibevoice_asr: VibeVoiceAsrDefaults = Field(default_factory=VibeVoiceAsrDefaults)
    tts: TtsDefaults = Field(default_factory=TtsDefaults)


class SettingsModel(BaseModel):
    version: int = 1
    first_run_completed: bool = False
    active_profile: Optional[str] = None
    vram_policy: Literal["exclusive", "manual"] = "exclusive"
    history_retention_days: int = Field(30, ge=1, le=365)
    retained_inputs_max_mb: int = Field(500, ge=0, le=50000)
    defaults: EngineDefaults = Field(default_factory=EngineDefaults)


class ProfileBody(BaseModel):
    """Corpo aceito no PUT de perfil (o slug vem do path)."""
    name: str = Field(min_length=1, max_length=80)
    base_preset: Optional[str] = None
    engine_params: EngineDefaults = Field(default_factory=EngineDefaults)
    notes: str = Field("", max_length=2000)


class ProfileModel(ProfileBody):
    slug: str
    created_at: str
    updated_at: str


# ------------------------------------------------------------------ helpers

def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60]
    if not slug:
        raise ValueError(f"Nome de perfil inválido: {name!r}")
    return slug


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _profile_path(slug: str) -> Path:
    clean = slugify(slug)
    path = (PROFILES_DIR / f"{clean}.json").resolve()
    if path.parent != PROFILES_DIR.resolve():
        raise ValueError("Slug de perfil inválido.")
    return path


def _single_unambiguous_real_voice_id() -> Optional[str]:
    try:
        from services import voice_profiles

        voices = voice_profiles.list_voices().get("custom", [])
        defaults = [voice["id"] for voice in voices if voice.get("is_default")]
        if len(defaults) == 1:
            return defaults[0]
        if len(voices) == 1:
            return voices[0]["id"]
    except Exception as exc:
        record_app_event(
            "legacy_tts_voice_migration_lookup_failed",
            error_message=str(exc)[:200],
        )
    return None


def _real_voice_exists(voice_id: str) -> bool:
    if not _UUID_PATTERN.match(str(voice_id or "")):
        return False
    try:
        from services import voice_profiles

        voice_profiles.get_voice(voice_id)
        return True
    except Exception:
        return False


def _migrate_voice_selection(value: Any, fallback_voice_id: Optional[str]) -> Tuple[Any, bool]:
    if value in (None, ""):
        return value, False
    candidate = str(value).strip()
    if candidate in _LEGACY_WINDOWS_VOICE_IDS:
        return fallback_voice_id or "", True
    if _real_voice_exists(candidate):
        return candidate, False
    return "", True


def _migrate_tts_section(tts_section: Any, fallback_voice_id: Optional[str]) -> bool:
    if not isinstance(tts_section, dict):
        return False

    changed = False
    for key in _VOICE_SELECTION_KEYS:
        if key not in tts_section:
            continue
        migrated, did_change = _migrate_voice_selection(tts_section.get(key), fallback_voice_id)
        if did_change:
            tts_section[key] = migrated
            changed = True

    for key in _VOICE_MAP_KEYS:
        voice_map = tts_section.get(key)
        if not isinstance(voice_map, dict):
            continue
        migrated_map: Dict[str, Any] = {}
        for speaker, value in voice_map.items():
            migrated, did_change = _migrate_voice_selection(value, fallback_voice_id)
            changed = changed or did_change
            if migrated:
                migrated_map[str(speaker)] = migrated
        if migrated_map != voice_map:
            tts_section[key] = migrated_map
            changed = True

    return changed


def _migrate_legacy_tts_voice_config(raw: Dict[str, Any]) -> bool:
    """Remove selecoes antigas de voz Windows sem criar identidade falsa.

    Campos reais existentes sao preservados. IDs legados ou inexistentes sao
    substituidos apenas quando ha uma unica voz real inequivoca; caso contrario,
    a selecao fica vazia para manter o TTS pendente/desabilitado.
    """
    fallback_voice_id = _single_unambiguous_real_voice_id()
    changed = False
    defaults = raw.get("defaults")
    if isinstance(defaults, dict):
        changed = _migrate_tts_section(defaults.get("tts"), fallback_voice_id) or changed
    engine_params = raw.get("engine_params")
    if isinstance(engine_params, dict):
        changed = _migrate_tts_section(engine_params.get("tts"), fallback_voice_id) or changed
    changed = _migrate_tts_section(raw.get("tts"), fallback_voice_id) or changed
    return changed


def _load_json_with_legacy_tts_migration(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if _migrate_legacy_tts_voice_config(raw):
        _atomic_write_json(path, raw)
        record_app_event("legacy_tts_voice_config_migrated", path=str(path))
    return raw


# ----------------------------------------------------------------- settings

def get_settings() -> SettingsModel:
    """Carrega settings com cache por mtime; recria defaults se corrompido."""
    with _lock:
        if not SETTINGS_PATH.exists():
            settings = SettingsModel()
            _write_settings(settings)
            record_app_event("settings_created_with_defaults", path=str(SETTINGS_PATH))
            return settings

        mtime = SETTINGS_PATH.stat().st_mtime
        if _settings_cache["settings"] is not None and _settings_cache["mtime"] == mtime:
            return _settings_cache["settings"]

        try:
            raw = _load_json_with_legacy_tts_migration(SETTINGS_PATH)
            settings = SettingsModel.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, OSError) as exc:
            backup = SETTINGS_PATH.with_suffix(".json.corrupted.bak")
            try:
                os.replace(SETTINGS_PATH, backup)
            except OSError:
                pass
            record_app_event(
                "settings_corrupted_recreated",
                error_message=str(exc)[:300],
                backup=str(backup),
            )
            settings = SettingsModel()
            _write_settings(settings)
            return settings

        _settings_cache["settings"] = settings
        _settings_cache["mtime"] = SETTINGS_PATH.stat().st_mtime
        return settings


def _write_settings(settings: SettingsModel) -> None:
    _atomic_write_json(SETTINGS_PATH, settings.model_dump())
    _settings_cache["settings"] = settings
    _settings_cache["mtime"] = SETTINGS_PATH.stat().st_mtime


def save_settings(settings: SettingsModel) -> SettingsModel:
    with _lock:
        _write_settings(settings)
    _apply_side_effects(settings)
    record_app_event("settings_saved", vram_policy=settings.vram_policy,
                     active_profile=settings.active_profile)
    return settings


def _apply_side_effects(settings: SettingsModel) -> None:
    # A política de VRAM vive nos settings; o árbitro precisa refletir.
    try:
        from services.resource_arbiter import arbiter

        if arbiter.policy != settings.vram_policy:
            arbiter.set_policy(settings.vram_policy)
    except Exception as exc:
        record_app_event("settings_side_effect_error", error_message=str(exc))


def apply_settings_on_startup() -> SettingsModel:
    settings = get_settings()
    _apply_side_effects(settings)
    return settings


# ----------------------------------------------------------------- perfis

def list_profiles() -> List[Dict[str, Any]]:
    if not PROFILES_DIR.is_dir():
        return []
    profiles = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            raw = _load_json_with_legacy_tts_migration(path)
            profile = ProfileModel.model_validate(raw)
            profiles.append({
                "name": profile.name,
                "slug": profile.slug,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "base_preset": profile.base_preset,
                "notes": profile.notes,
            })
        except (json.JSONDecodeError, ValidationError) as exc:
            record_app_event("profile_invalid_skipped", path=str(path), error_message=str(exc)[:200])
    return profiles


def get_profile(slug: str) -> Optional[ProfileModel]:
    path = _profile_path(slug)
    if not path.exists():
        return None
    raw = _load_json_with_legacy_tts_migration(path)
    return ProfileModel.model_validate(raw)


def save_profile(slug: str, body: ProfileBody) -> ProfileModel:
    with _lock:
        path = _profile_path(slug)
        clean_slug = path.stem
        existing = get_profile(clean_slug) if path.exists() else None
        profile = ProfileModel(
            **body.model_dump(),
            slug=clean_slug,
            created_at=existing.created_at if existing else _now_iso(),
            updated_at=_now_iso(),
        )
        _atomic_write_json(path, profile.model_dump())
    record_app_event("profile_saved", slug=clean_slug)
    return profile


def delete_profile(slug: str) -> bool:
    with _lock:
        path = _profile_path(slug)
        if not path.exists():
            return False
        path.unlink()
        settings = get_settings()
        if settings.active_profile == path.stem:
            settings = settings.model_copy(update={"active_profile": None})
            _write_settings(settings)
    record_app_event("profile_deleted", slug=path.stem)
    return True


def apply_profile(slug: str) -> Optional[SettingsModel]:
    """Copia os engine_params do perfil para os defaults ativos."""
    with _lock:
        profile = get_profile(slug)
        if profile is None:
            return None
        settings = get_settings().model_copy(update={
            "defaults": profile.engine_params,
            "active_profile": profile.slug,
        })
        _write_settings(settings)
    _apply_side_effects(settings)
    record_app_event("profile_applied", slug=profile.slug)
    return settings
