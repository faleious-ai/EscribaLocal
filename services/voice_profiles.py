"""Biblioteca de vozes reais do VibeVoice TTS 1.5B.

Perfis persistentes em ``data/voices/<uuid>/`` (profile.json, áudio original,
reference.wav 24kHz mono, preview.wav e embeddings em CPU). Vozes vêm de
gravação/upload com consentimento explícito persistido.

Privacidade: tudo local; logs nunca registram áudio, transcrição da amostra
ou caminhos absolutos. IDs são UUIDs (nome nunca vira caminho físico).
"""
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import scipy.io.wavfile as wavfile

from services.app_logging import record_app_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOICES_DIR = PROJECT_ROOT / "data" / "voices"

SAMPLE_RATE = 24000
VOICE_SCHEMA_VERSION = 2
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".opus", ".aac"}
MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MIN_DURATION_SECONDS = 0.5
EMBEDDINGS_FILENAME = "vibevoice_1_5b.pt"

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LEGACY_WINDOWS_VOICE_PATTERN = re.compile(r"^(preset_windows_[1-4]|speaker_[1-4])$")
_STYLE_ID_PATTERN = re.compile(r"[^a-z0-9]+")

_lock = threading.RLock()
_in_use: Dict[str, int] = {}

# Builder de embeddings injetado pelo serviço do 1.5B (evita import circular):
# fn(reference_wav_path: str) -> (tensor_cpu (n, hidden), model_revision: str)
_embedding_builder: Optional[Callable[[str], Tuple[Any, str]]] = None
_revision_getter: Optional[Callable[[], str]] = None


class VoiceNotFound(Exception):
    pass


class VoiceInUse(Exception):
    pass


class InvalidVoice(Exception):
    def __init__(self, message: str, analysis: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.analysis = analysis or {}


def set_embedding_builder(builder: Callable[[str], Tuple[Any, str]],
                          revision_getter: Callable[[], str]) -> None:
    global _embedding_builder, _revision_getter
    _embedding_builder = builder
    _revision_getter = revision_getter


# ------------------------------------------------------------------ caminhos

def resolve_voice_id(voice_id: Optional[str]) -> Optional[str]:
    """Retorna o identificador como recebido; aliases legados nao resolvem voz."""
    if not voice_id:
        return None
    return voice_id


def is_legacy_windows_voice_id(voice_id: Optional[str]) -> bool:
    return bool(_LEGACY_WINDOWS_VOICE_PATTERN.match(str(voice_id or "")))


def _voice_dir(voice_id: str) -> Path:
    # UUID estrito: nomes nunca viram caminho; bloqueia path traversal.
    if not _UUID_PATTERN.match(str(voice_id or "")):
        raise VoiceNotFound(f"Voz desconhecida: {voice_id!r}")
    return VOICES_DIR / voice_id


def _profile_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "profile.json"


def reference_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "reference.wav"


def preview_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "previews" / "preview.wav"


def previous_preview_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "previews" / "preview_anterior.wav"


def embeddings_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "engines" / "vibevoice_1_5b" / EMBEDDINGS_FILENAME


def _original_dir(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "original"


def _styles_dir(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "styles"


def _events_dir(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "events"


def _previews_dir(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "previews"


def _engine_dir(voice_id: str, engine_key: str) -> Path:
    return _voice_dir(voice_id) / "engines" / engine_key


def _style_dir(voice_id: str, style_id: str) -> Path:
    return _styles_dir(voice_id) / style_id


def _style_path(voice_id: str, style_id: str) -> Path:
    return _style_dir(voice_id, style_id) / "style.json"


def style_reference_path(voice_id: str, style_id: str) -> Path:
    return _style_dir(voice_id, style_id) / "reference.wav"


def style_original_path(voice_id: str, style_id: str) -> Path:
    return _style_dir(voice_id, style_id) / "original.wav"


# ------------------------------------------------------------------- perfis

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _write_profile_json(path: Path, profile: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
        json.dump(profile, tmp_file, ensure_ascii=False, indent=2)
    os.replace(tmp_name, path)


def _ensure_voice_layout(voice_id: str) -> None:
    for path in (
        _original_dir(voice_id),
        _styles_dir(voice_id),
        _events_dir(voice_id),
        _previews_dir(voice_id),
        _engine_dir(voice_id, "vibevoice_1_5b"),
        _engine_dir(voice_id, "chatterbox_pt_br"),
    ):
        path.mkdir(parents=True, exist_ok=True)


def _slugify_style_id(name: str) -> str:
    normalized = "".join(
        ch for ch in unicodedata.normalize("NFKD", str(name or "").strip().lower())
        if unicodedata.category(ch) != "Mn"
    )
    slug = _STYLE_ID_PATTERN.sub("-", normalized).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:60]
    if not slug:
        raise InvalidVoice("Nome de estilo inválido.")
    return slug


def _load_style(voice_id: str, style_id: str) -> Dict[str, Any]:
    path = _style_path(voice_id, style_id)
    if not path.exists():
        raise VoiceNotFound(f"Estilo desconhecido: {style_id!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_style(voice_id: str, style: Dict[str, Any]) -> None:
    _write_profile_json(_style_path(voice_id, style["style_id"]), style)


def _style_public(style: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "style_id": style["style_id"],
        "name": style["name"],
        "description": style.get("description", ""),
        "aliases": list(style.get("aliases", [])),
        "instruction": style.get("instruction", ""),
        "parameters": dict(style.get("parameters", {})),
        "order": int(style.get("order", 0)),
        "active": bool(style.get("active", True)),
        "engine_compatibility": dict(style.get("engine_compatibility", {})),
        "reference": dict(style.get("reference", {"status": "missing"})),
        "created_at": style.get("created_at"),
        "updated_at": style.get("updated_at"),
    }


def _list_style_items(voice_id: str, profile: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    items = []
    profile = profile or {}
    for entry in ((profile.get("styles") or {}).get("items") or []):
        style_id = entry.get("style_id")
        if not style_id:
            continue
        try:
            items.append(_style_public(_load_style(voice_id, style_id)))
        except (OSError, json.JSONDecodeError, VoiceNotFound) as exc:
            record_app_event(
                "voice_style_invalid",
                voice_id=voice_id,
                style_id=style_id,
                error_message=str(exc)[:200],
            )
    return sorted(items, key=lambda item: (item["order"], item["name"]))


def _canonical_original_relative_path(voice_id: str) -> Optional[str]:
    voice_dir = _voice_dir(voice_id)
    canonical = None

    originals = sorted(_original_dir(voice_id).glob("source.*"))
    if originals:
        canonical = originals[0]
    else:
        legacy = sorted(voice_dir.glob("original_audio.*"))
        if legacy:
            canonical = _original_dir(voice_id) / f"source{legacy[0].suffix.lower()}"
            if legacy[0] != canonical:
                canonical.parent.mkdir(parents=True, exist_ok=True)
                if not canonical.exists():
                    os.replace(legacy[0], canonical)
                else:
                    legacy[0].unlink()

    if canonical is None or not canonical.exists():
        return None
    return canonical.relative_to(voice_dir).as_posix()


def _migrate_preview_layout(voice_id: str) -> None:
    voice_dir = _voice_dir(voice_id)
    for legacy_name, target in (
        ("preview.wav", preview_path(voice_id)),
        ("preview_anterior.wav", previous_preview_path(voice_id)),
    ):
        legacy_path = voice_dir / legacy_name
        if legacy_path.exists() and legacy_path != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.replace(legacy_path, target)
            else:
                legacy_path.unlink()


def _migrate_embeddings_layout(voice_id: str) -> None:
    legacy_path = _voice_dir(voice_id) / "embeddings" / EMBEDDINGS_FILENAME
    target = embeddings_path(voice_id)
    if legacy_path.exists() and legacy_path != target:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            os.replace(legacy_path, target)
        else:
            legacy_path.unlink()


def _default_engine_state(status: str = "pending",
                          model_revision: Optional[str] = None,
                          reference_hash: Optional[str] = None) -> Dict[str, Any]:
    return {
        "artifacts_dir": "engines/vibevoice_1_5b",
        "embedding": {
            "path": f"engines/vibevoice_1_5b/{EMBEDDINGS_FILENAME}",
            "status": status,
            "model_revision": model_revision,
            "reference_hash": reference_hash,
        },
    }


def _ensure_profile_schema(profile: Dict[str, Any]) -> bool:
    voice_id = str(profile["id"])
    changed = False
    _ensure_voice_layout(voice_id)
    _migrate_preview_layout(voice_id)
    _migrate_embeddings_layout(voice_id)
    original_rel = _canonical_original_relative_path(voice_id)

    sample_rate = int(profile.get("sample_rate") or SAMPLE_RATE)
    reference_hash = profile.get("reference_hash")
    if reference_hash is None and reference_path(voice_id).exists():
        reference_hash = hashlib.sha256(reference_path(voice_id).read_bytes()).hexdigest()
        profile["reference_hash"] = reference_hash
        changed = True

    if profile.get("schema_version") != VOICE_SCHEMA_VERSION:
        profile["schema_version"] = VOICE_SCHEMA_VERSION
        changed = True

    expected_reference = {
        "path": "reference.wav",
        "hash": reference_hash,
        "sample_rate": sample_rate,
    }
    if profile.get("reference") != expected_reference:
        profile["reference"] = expected_reference
        changed = True

    expected_original = {
        "path": original_rel,
        "source_ext": Path(original_rel).suffix.lower() if original_rel else None,
    }
    if profile.get("original") != expected_original:
        profile["original"] = expected_original
        changed = True

    expected_library = {"is_default": bool(profile.get("is_default", False))}
    if profile.get("library") != expected_library:
        profile["library"] = expected_library
        changed = True
    if profile.get("is_default") != expected_library["is_default"]:
        profile["is_default"] = expected_library["is_default"]
        changed = True

    styles = profile.get("styles")
    if not isinstance(styles, dict) or "items" not in styles:
        profile["styles"] = {"items": []}
        changed = True
    else:
        synced_styles = _list_style_items(voice_id, profile)
        if profile["styles"].get("items") != synced_styles:
            profile["styles"]["items"] = synced_styles
            changed = True

    events = profile.get("events")
    if not isinstance(events, dict) or "items" not in events:
        profile["events"] = {"items": {}}
        changed = True

    legacy_embeddings = dict((profile.get("model_embeddings") or {}).get("vibevoice_1_5b") or {})
    vibe_state = _default_engine_state(
        status=legacy_embeddings.get("status", "pending"),
        model_revision=legacy_embeddings.get("model_revision"),
        reference_hash=legacy_embeddings.get("reference_hash"),
    )
    engines = profile.get("engines")
    if not isinstance(engines, dict):
        engines = {}
        profile["engines"] = engines
        changed = True
    if engines.get("vibevoice_1_5b") != vibe_state:
        engines["vibevoice_1_5b"] = vibe_state
        changed = True

    chatterbox_state = engines.get("chatterbox_pt_br")
    expected_chatterbox = {
        "artifacts_dir": "engines/chatterbox_pt_br",
        "reference": {"status": "pending"},
    }
    if chatterbox_state != expected_chatterbox:
        engines["chatterbox_pt_br"] = expected_chatterbox
        changed = True

    expected_model_embeddings = {
        "vibevoice_1_5b": {
            "status": engines["vibevoice_1_5b"]["embedding"]["status"],
            "model_revision": engines["vibevoice_1_5b"]["embedding"]["model_revision"],
            "reference_hash": engines["vibevoice_1_5b"]["embedding"]["reference_hash"],
        }
    }
    if profile.get("model_embeddings") != expected_model_embeddings:
        profile["model_embeddings"] = expected_model_embeddings
        changed = True

    return changed


def _load_profile(voice_id: str) -> Dict[str, Any]:
    path = _profile_path(voice_id)
    if not path.exists():
        raise VoiceNotFound(f"Voz não encontrada: {voice_id}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if _ensure_profile_schema(profile):
        _write_profile_json(path, profile)
    return profile


def _save_profile(profile: Dict[str, Any]) -> None:
    _ensure_profile_schema(profile)
    profile["updated_at"] = _now_iso()
    path = _profile_path(profile["id"])
    _write_profile_json(path, profile)


def _dir_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _public(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Visão pública do perfil: nunca expõe caminhos do disco."""
    voice_id = profile["id"]
    return {
        "id": voice_id,
        "name": profile.get("name"),
        "source": profile.get("source"),
        "language": profile.get("language"),
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
        "duration_seconds": profile.get("duration_seconds"),
        "sample_rate": profile.get("sample_rate"),
        "consent_confirmed": profile.get("consent_confirmed", False),
        "is_preset": False,
        "is_default": profile.get("is_default", False),
        "reference_hash": profile.get("reference_hash"),
        "analysis": profile.get("analysis"),
        "validation": profile.get("validation"),
        "styles": profile.get("styles", {"items": []}),
        "model_embeddings": profile.get("model_embeddings", {}),
        "has_preview": preview_path(voice_id).exists(),
        "has_previous_preview": previous_preview_path(voice_id).exists(),
        "disk_bytes": _dir_size(_voice_dir(voice_id)),
    }


def list_voices() -> Dict[str, Any]:
    custom: List[Dict[str, Any]] = []
    if VOICES_DIR.is_dir():
        for entry in sorted(VOICES_DIR.iterdir()):
            if entry.is_dir() and _UUID_PATTERN.match(entry.name) and (entry / "profile.json").exists():
                try:
                    custom.append(_public(_load_profile(entry.name)))
                except (json.JSONDecodeError, OSError) as exc:
                    record_app_event("voice_profile_invalid", voice_id=entry.name,
                                     error_message=str(exc)[:200])
    return {
        "presets": [],
        "custom": custom,
        "total_disk_bytes": _dir_size(VOICES_DIR),
    }


def get_voice(voice_id: str) -> Dict[str, Any]:
    voice_id = resolve_voice_id(voice_id)
    return _public(_load_profile(voice_id))


def get_default_voice_id() -> Optional[str]:
    for voice in list_voices()["custom"]:
        if voice.get("is_default"):
            return voice["id"]
    return None


# ------------------------------------------------------------ uso simultâneo

class voice_in_use:
    """Marca a voz como em uso durante uma geração (bloqueia exclusão)."""

    def __init__(self, voice_ids: List[str]):
        self.voice_ids = [v for v in voice_ids if v]

    def __enter__(self):
        with _lock:
            for voice_id in self.voice_ids:
                _in_use[voice_id] = _in_use.get(voice_id, 0) + 1
        return self

    def __exit__(self, *exc_info):
        with _lock:
            for voice_id in self.voice_ids:
                _in_use[voice_id] = max(0, _in_use.get(voice_id, 0) - 1)
                if _in_use[voice_id] == 0:
                    _in_use.pop(voice_id, None)


def is_in_use(voice_id: str) -> bool:
    with _lock:
        return _in_use.get(voice_id, 0) > 0


# ------------------------------------------------------------------- análise

def _probe_original(audio_bytes: bytes, ext: str) -> Tuple[Optional[int], Optional[int]]:
    """Melhor esforço: taxa e canais originais via banner do ffmpeg."""
    import subprocess

    import imageio_ffmpeg

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            proc = subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", tmp_path],
                capture_output=True, text=True, timeout=20,
            )
            match = re.search(r"(\d+)\s*Hz,\s*([a-zA-Z0-9.]+)", proc.stderr or "")
            if match:
                channels_text = match.group(2).lower()
                channels = {"mono": 1, "stereo": 2}.get(channels_text)
                if channels is None:
                    digits = re.match(r"(\d+)", channels_text)
                    channels = int(digits.group(1)) if digits else None
                return int(match.group(1)), channels
        finally:
            os.unlink(tmp_path)
    except Exception:
        pass
    return None, None


def _trim_silence(audio: np.ndarray, threshold: float = 0.01,
                  frame_ms: int = 20) -> Tuple[np.ndarray, float]:
    """Remove silêncio das pontas; retorna (áudio, segundos_de_fala_estimados)."""
    frame = max(1, int(SAMPLE_RATE * frame_ms / 1000))
    n_frames = len(audio) // frame
    if n_frames == 0:
        return audio, 0.0
    frames = audio[: n_frames * frame].reshape(n_frames, frame)
    energy = np.sqrt((frames ** 2).mean(axis=1))
    active = energy > threshold
    if not active.any():
        return audio, 0.0
    first = int(np.argmax(active))
    last = int(n_frames - np.argmax(active[::-1]))
    speech_seconds = float(active.sum() * frame / SAMPLE_RATE)
    return audio[first * frame: last * frame], speech_seconds


def analyze_reference(audio: np.ndarray, sample_rate_original: Optional[int],
                      channels_original: Optional[int]) -> Dict[str, Any]:
    duration = len(audio) / SAMPLE_RATE
    _, speech_seconds = _trim_silence(audio)
    silence_ratio = round(1.0 - (speech_seconds / duration), 3) if duration > 0 else 1.0
    rms = float(np.sqrt((audio ** 2).mean())) if len(audio) else 0.0
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    clipping = bool((np.abs(audio) >= 0.985).mean() > 0.001) if len(audio) else False

    warnings: List[str] = []
    if duration < 3.0:
        warnings.append("Gravação curta (menos de 3s); 5–15s tendem a clonar melhor.")
    if rms < 0.02:
        warnings.append("Volume baixo; aproxime o microfone ou aumente o ganho.")
    if clipping:
        warnings.append("Clipping detectado (áudio saturado); reduza o volume de entrada.")
    if silence_ratio > 0.5:
        warnings.append("Mais da metade da gravação é silêncio.")

    if duration < MIN_DURATION_SECONDS or speech_seconds < 0.3:
        status = "invalid"
    elif duration < 2.0 or rms < 0.008 or (clipping and rms > 0.3):
        status = "poor"
    elif warnings:
        status = "acceptable"
    else:
        status = "good"

    return {
        "duration_seconds": round(duration, 2),
        "speech_seconds": round(speech_seconds, 2),
        "silence_ratio": silence_ratio,
        "sample_rate_original": sample_rate_original,
        "sample_rate_normalized": SAMPLE_RATE,
        "channels_original": channels_original,
        "clipping_detected": clipping,
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "quality_status": status,
        "warnings": warnings,
    }


def _normalize_reference_audio(audio_bytes: bytes, original_ext: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    ext = (original_ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidVoice(f"Formato não suportado: {ext}. Use {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
    if not audio_bytes or len(audio_bytes) < 128:
        raise InvalidVoice("Arquivo de áudio vazio ou pequeno demais.")
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        raise InvalidVoice("Arquivo acima de 60MB; envie uma amostra menor.")

    from services.transcriber import decode_audio_ffmpeg

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        try:
            audio = decode_audio_ffmpeg(tmp_path, sampling_rate=SAMPLE_RATE)
        except Exception as exc:
            raise InvalidVoice(f"Não foi possível decodificar o áudio: {exc}")
    finally:
        os.unlink(tmp_path)

    sr_original, ch_original = _probe_original(audio_bytes, ext)
    trimmed, _ = _trim_silence(np.asarray(audio, dtype=np.float32))
    normalized = trimmed if len(trimmed) else np.asarray(audio, dtype=np.float32)
    analysis = analyze_reference(normalized, sr_original, ch_original)
    if analysis["quality_status"] == "invalid":
        raise InvalidVoice(
            "A amostra não contém fala suficiente para criar uma referência "
            f"(duração {analysis['duration_seconds']}s, fala {analysis['speech_seconds']}s).",
            analysis,
        )
    return normalized, analysis


# ------------------------------------------------------------------- criação

def create_voice(
    name: str,
    audio_bytes: bytes,
    original_ext: str,
    source: str,
    consent_confirmed: bool,
    language: str = "pt-BR",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Cria um perfil a partir de upload/gravação. Retorna (perfil, análise)."""
    name = (name or "").strip()
    if not name:
        raise InvalidVoice("Dê um nome à voz.")
    if not consent_confirmed:
        raise InvalidVoice(
            "É obrigatório confirmar que a voz é sua ou que você possui "
            "autorização expressa da pessoa gravada."
        )
    ext = (original_ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext
    reference, analysis = _normalize_reference_audio(audio_bytes, ext)

    voice_id = str(uuid.uuid4())
    voice_dir = _voice_dir(voice_id)
    voice_dir.mkdir(parents=True, exist_ok=False)
    _ensure_voice_layout(voice_id)

    (_original_dir(voice_id) / f"source{ext}").write_bytes(audio_bytes)
    pcm = (np.clip(reference, -1.0, 1.0) * 32767).astype(np.int16)
    wavfile.write(str(reference_path(voice_id)), SAMPLE_RATE, pcm)
    ref_hash = hashlib.sha256(reference_path(voice_id).read_bytes()).hexdigest()

    profile = {
        "id": voice_id,
        "name": name,
        "source": source,
        "language": language,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "duration_seconds": analysis["duration_seconds"],
        "sample_rate": SAMPLE_RATE,
        "consent_confirmed": True,
        "is_preset": False,
        "is_default": False,
        "schema_version": VOICE_SCHEMA_VERSION,
        "reference_hash": ref_hash,
        "reference": {
            "path": "reference.wav",
            "hash": ref_hash,
            "sample_rate": SAMPLE_RATE,
        },
        "original": {
            "path": f"original/source{ext}",
            "source_ext": ext,
        },
        "library": {"is_default": False},
        "styles": {"items": []},
        "events": {"items": {}},
        "analysis": analysis,
        "validation": None,
        "engines": {
            "vibevoice_1_5b": _default_engine_state(),
            "chatterbox_pt_br": {
                "artifacts_dir": "engines/chatterbox_pt_br",
                "reference": {"status": "pending"},
            },
        },
        "model_embeddings": {
            "vibevoice_1_5b": {
                "status": "pending",
                "model_revision": None,
                "reference_hash": None,
            }
        },
    }
    _save_profile(profile)

    # Extração eager dos embeddings quando o builder está disponível;
    # falha vira status "pending" (recalculado na primeira geração).
    try:
        build_embeddings(voice_id)
        profile = _load_profile(voice_id)
    except Exception as exc:
        record_app_event("voice_embeddings_deferred", voice_id=voice_id,
                         error_message=str(exc)[:200])

    record_app_event("voice_created", voice_id=voice_id, source=source,
                     duration_seconds=analysis["duration_seconds"],
                     quality=analysis["quality_status"])
    return _public(profile), analysis


# --------------------------------------------------------------- embeddings

def build_embeddings(voice_id: str) -> Dict[str, Any]:
    """(Re)constrói os embeddings da referência via builder do serviço 1.5B."""
    if _embedding_builder is None:
        raise InvalidVoice("Motor de embeddings indisponível (serviço TTS não inicializado).")
    profile = _load_profile(voice_id)
    ref_path = reference_path(voice_id)
    if not ref_path.exists():
        raise InvalidVoice("reference.wav ausente; reenvie/regrave a voz.")

    import torch

    embeds, model_revision = _embedding_builder(str(ref_path))
    embeds = embeds.detach().to("cpu")
    payload = {
        "embeds": embeds,
        "model_revision": model_revision,
        "reference_hash": profile["reference_hash"],
        "built_at": _now_iso(),
    }
    embeddings_path(voice_id).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, str(embeddings_path(voice_id)))

    profile["model_embeddings"]["vibevoice_1_5b"] = {
        "status": "ready",
        "model_revision": model_revision,
        "reference_hash": profile["reference_hash"],
    }
    profile.setdefault("engines", {})
    profile["engines"]["vibevoice_1_5b"] = _default_engine_state(
        status="ready",
        model_revision=model_revision,
        reference_hash=profile["reference_hash"],
    )
    _save_profile(profile)
    record_app_event("voice_embeddings_built", voice_id=voice_id,
                     frames=int(embeds.shape[0]))
    return profile["model_embeddings"]["vibevoice_1_5b"]


def load_embeddings(voice_id: str):
    """Tensor CPU dos embeddings, validando hash da referência e revisão do
    modelo; recalcula quando inválidos/ausentes. Nunca cai para outra voz."""
    profile = _load_profile(voice_id)
    expected_hash = profile["reference_hash"]
    expected_revision = _revision_getter() if _revision_getter else None

    path = embeddings_path(voice_id)
    if path.exists():
        import torch

        try:
            payload = torch.load(str(path), map_location="cpu", weights_only=False)
            if (payload.get("reference_hash") == expected_hash
                    and (expected_revision is None
                         or payload.get("model_revision") == expected_revision)):
                return payload["embeds"]
            record_app_event("voice_embeddings_stale", voice_id=voice_id)
        except Exception as exc:
            record_app_event("voice_embeddings_corrupt", voice_id=voice_id,
                             error_message=str(exc)[:200])

    build_embeddings(voice_id)
    import torch
    return torch.load(str(path), map_location="cpu", weights_only=False)["embeds"]


# ------------------------------------------------------------------- gestão

def rename_voice(voice_id: str, name: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise InvalidVoice("Nome inválido.")
    profile = _load_profile(voice_id)
    profile["name"] = name
    _save_profile(profile)
    record_app_event("voice_renamed", voice_id=voice_id)
    return _public(profile)


def set_default(voice_id: str) -> Dict[str, Any]:
    target = _load_profile(voice_id)
    if VOICES_DIR.is_dir():
        for entry in VOICES_DIR.iterdir():
            if entry.is_dir() and (entry / "profile.json").exists() and entry.name != voice_id:
                other = _load_profile(entry.name)
                if other.get("is_default"):
                    other["is_default"] = False
                    _save_profile(other)
    target["is_default"] = True
    _save_profile(target)
    record_app_event("voice_set_default", voice_id=voice_id)
    return _public(target)


def delete_voice(voice_id: str) -> Dict[str, Any]:
    _load_profile(voice_id)  # 404 se não existir
    if is_in_use(voice_id):
        raise VoiceInUse("Esta voz está sendo usada por uma geração em andamento; tente de novo em instantes.")
    freed = _dir_size(_voice_dir(voice_id))
    shutil.rmtree(_voice_dir(voice_id))
    record_app_event("voice_deleted", voice_id=voice_id, freed_bytes=freed)
    return {"deleted": voice_id, "freed_bytes": freed}


def record_validation(voice_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    profile = _load_profile(voice_id)
    profile["validation"] = result
    _save_profile(profile)
    return _public(profile)


def export_voice(voice_id: str) -> bytes:
    _load_profile(voice_id)
    buffer = io.BytesIO()
    voice_dir = _voice_dir(voice_id)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in voice_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(voice_dir).as_posix())
    record_app_event("voice_exported", voice_id=voice_id)
    return buffer.getvalue()


def import_voice(zip_bytes: bytes) -> Dict[str, Any]:
    """Importa um perfil exportado; ganha novo UUID e embeddings pendentes."""
    new_id = str(uuid.uuid4())
    voice_dir = _voice_dir(new_id)
    voice_dir.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.namelist():
                target = (voice_dir / member).resolve()
                if not str(target).startswith(str(voice_dir.resolve())):
                    raise InvalidVoice("Zip inválido (caminhos fora do perfil).")
            zf.extractall(voice_dir)
        profile = _load_profile(new_id)
        profile["id"] = new_id
        profile["is_default"] = False
        ref = reference_path(new_id)
        if not ref.exists():
            raise InvalidVoice("Zip não contém reference.wav.")
        profile["reference_hash"] = hashlib.sha256(ref.read_bytes()).hexdigest()
        profile["model_embeddings"] = {"vibevoice_1_5b": {"status": "pending",
                                                          "model_revision": None,
                                                          "reference_hash": None}}
        profile["engines"] = {
            "vibevoice_1_5b": _default_engine_state(),
            "chatterbox_pt_br": {
                "artifacts_dir": "engines/chatterbox_pt_br",
                "reference": {"status": "pending"},
            },
        }
        _save_profile(profile)
        record_app_event("voice_imported", voice_id=new_id)
        return _public(profile)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise InvalidVoice(f"Arquivo de perfil inválido: {exc}")
    except Exception:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise


def create_style(
    voice_id: str,
    *,
    name: str,
    description: str = "",
    aliases: Optional[List[str]] = None,
    instruction: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    engine_compatibility: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    profile = _load_profile(voice_id)
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise InvalidVoice("Dê um nome ao estilo.")

    style_id = _slugify_style_id(normalized_name)
    if _style_path(voice_id, style_id).exists():
        raise InvalidVoice(f"Já existe um estilo com id '{style_id}'.")

    normalized_aliases = []
    for alias in aliases or []:
        clean = _slugify_style_id(alias)
        if clean != style_id and clean not in normalized_aliases:
            normalized_aliases.append(clean)

    style = {
        "style_id": style_id,
        "name": normalized_name,
        "description": str(description or "").strip(),
        "aliases": normalized_aliases,
        "instruction": str(instruction or "").strip(),
        "parameters": dict(parameters or {}),
        "order": len((profile.get("styles") or {}).get("items") or []),
        "active": True,
        "engine_compatibility": dict(engine_compatibility or {}),
        "reference": {"status": "missing"},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    _style_dir(voice_id, style_id).mkdir(parents=True, exist_ok=False)
    _save_style(voice_id, style)

    profile.setdefault("styles", {"items": []})
    profile["styles"]["items"] = _list_style_items(voice_id, profile) + [_style_public(style)]
    _save_profile(profile)
    record_app_event("voice_style_created", voice_id=voice_id, style_id=style_id)
    return _style_public(_load_style(voice_id, style_id))


def set_style_reference(
    voice_id: str,
    style_id: str,
    *,
    audio_bytes: bytes,
    original_ext: str,
) -> Dict[str, Any]:
    _load_profile(voice_id)
    style = _load_style(voice_id, style_id)
    reference, _analysis = _normalize_reference_audio(audio_bytes, original_ext)

    pcm = (np.clip(reference, -1.0, 1.0) * 32767).astype(np.int16)
    style_dir = _style_dir(voice_id, style_id)
    style_dir.mkdir(parents=True, exist_ok=True)
    style_original_path(voice_id, style_id).write_bytes(audio_bytes)
    wavfile.write(str(style_reference_path(voice_id, style_id)), SAMPLE_RATE, pcm)

    reference_hash = hashlib.sha256(style_reference_path(voice_id, style_id).read_bytes()).hexdigest()
    style["reference"] = {
        "status": "ready",
        "path": "reference.wav",
        "hash": reference_hash,
        "sample_rate": SAMPLE_RATE,
        "original_path": "original.wav",
    }
    style["updated_at"] = _now_iso()
    _save_style(voice_id, style)
    _save_profile(_load_profile(voice_id))
    record_app_event("voice_style_reference_set", voice_id=voice_id, style_id=style_id)
    return _style_public(_load_style(voice_id, style_id))


def clear_style_reference(voice_id: str, style_id: str) -> Dict[str, Any]:
    _load_profile(voice_id)
    style = _load_style(voice_id, style_id)

    for path in (style_reference_path(voice_id, style_id), style_original_path(voice_id, style_id)):
        if path.exists():
            path.unlink()

    style["reference"] = {"status": "missing"}
    style["updated_at"] = _now_iso()
    _save_style(voice_id, style)
    _save_profile(_load_profile(voice_id))
    record_app_event("voice_style_reference_cleared", voice_id=voice_id, style_id=style_id)
    return _style_public(_load_style(voice_id, style_id))


def update_style(
    voice_id: str,
    style_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    instruction: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    active: Optional[bool] = None,
    order: Optional[int] = None,
    engine_compatibility: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    _load_profile(voice_id)
    style = _load_style(voice_id, style_id)

    if name is not None:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise InvalidVoice("Nome de estilo inválido.")
        style["name"] = normalized_name
    if description is not None:
        style["description"] = str(description).strip()
    if aliases is not None:
        normalized_aliases = []
        for alias in aliases:
            clean = _slugify_style_id(alias)
            if clean != style_id and clean not in normalized_aliases:
                normalized_aliases.append(clean)
        style["aliases"] = normalized_aliases
    if instruction is not None:
        style["instruction"] = str(instruction).strip()
    if parameters is not None:
        style["parameters"] = dict(parameters)
    if active is not None:
        style["active"] = bool(active)
    if engine_compatibility is not None:
        style["engine_compatibility"] = dict(engine_compatibility)

    styles = _list_style_items(voice_id, _load_profile(voice_id))
    if order is not None:
        target_order = max(0, int(order))
        current_ids = [item["style_id"] for item in styles if item["style_id"] != style_id]
        target_order = min(target_order, len(current_ids))
        current_ids.insert(target_order, style_id)
        for index, current_style_id in enumerate(current_ids):
            current = style if current_style_id == style_id else _load_style(voice_id, current_style_id)
            current["order"] = index
            current["updated_at"] = _now_iso()
            _save_style(voice_id, current)
    else:
        style["updated_at"] = _now_iso()
        _save_style(voice_id, style)

    if order is not None:
        style = _load_style(voice_id, style_id)
    if order is None:
        style["updated_at"] = _now_iso()
        _save_style(voice_id, style)

    profile = _load_profile(voice_id)
    _save_profile(profile)
    record_app_event("voice_style_updated", voice_id=voice_id, style_id=style_id)
    return _style_public(_load_style(voice_id, style_id))


def duplicate_style(voice_id: str, style_id: str, *, name: str) -> Dict[str, Any]:
    source = _load_style(voice_id, style_id)
    reference_source: Optional[Path] = None
    original_source: Optional[Path] = None
    if source.get("reference", {}).get("status") == "ready":
        reference_source = style_reference_path(voice_id, style_id)
        original_source = style_original_path(voice_id, style_id)
        if not reference_source.exists() or not original_source.exists():
            raise InvalidVoice(
                "Não foi possível duplicar o estilo: mídia de referência incompleta."
            )

    duplicated = create_style(
        voice_id,
        name=name,
        description=source.get("description", ""),
        aliases=list(source.get("aliases", [])),
        instruction=source.get("instruction", ""),
        parameters=dict(source.get("parameters", {})),
        engine_compatibility=dict(source.get("engine_compatibility", {})),
    )
    duplicated_style_id = duplicated["style_id"]
    try:
        duplicated_style = _load_style(voice_id, duplicated_style_id)
        if reference_source is not None and original_source is not None:
            shutil.copy2(reference_source, style_reference_path(voice_id, duplicated_style_id))
            shutil.copy2(original_source, style_original_path(voice_id, duplicated_style_id))
            duplicated_style["reference"] = dict(source.get("reference", {}))

        duplicated_style["updated_at"] = _now_iso()
        _save_style(voice_id, duplicated_style)
        _save_profile(_load_profile(voice_id))
    except Exception as duplicate_error:
        try:
            shutil.rmtree(_style_dir(voice_id, duplicated_style_id))
            _save_profile(_load_profile(voice_id))
        except Exception as rollback_error:
            raise RuntimeError(
                "Falha ao duplicar o estilo e o rollback também falhou: "
                f"{rollback_error}"
            ) from duplicate_error
        raise

    record_app_event(
        "voice_style_duplicated",
        voice_id=voice_id,
        style_id=style_id,
        duplicated_style_id=duplicated_style_id,
    )
    return _style_public(_load_style(voice_id, duplicated_style_id))


def delete_style(voice_id: str, style_id: str) -> Dict[str, Any]:
    _load_profile(voice_id)
    _load_style(voice_id, style_id)
    shutil.rmtree(_style_dir(voice_id, style_id))

    remaining = _list_style_items(voice_id, _load_profile(voice_id))
    for index, item in enumerate(remaining):
        current = _load_style(voice_id, item["style_id"])
        if current.get("order") != index:
            current["order"] = index
            current["updated_at"] = _now_iso()
            _save_style(voice_id, current)

    profile = _load_profile(voice_id)
    _save_profile(profile)
    record_app_event("voice_style_deleted", voice_id=voice_id, style_id=style_id)
    return {"deleted": style_id}
