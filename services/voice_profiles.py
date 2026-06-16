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
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".opus", ".aac"}
MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MIN_DURATION_SECONDS = 0.5
EMBEDDINGS_FILENAME = "vibevoice_1_5b.pt"

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LEGACY_WINDOWS_VOICE_PATTERN = re.compile(r"^(preset_windows_[1-4]|speaker_[1-4])$")

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
    return _voice_dir(voice_id) / "preview.wav"


def previous_preview_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "preview_anterior.wav"


def embeddings_path(voice_id: str) -> Path:
    return _voice_dir(voice_id) / "embeddings" / EMBEDDINGS_FILENAME


# ------------------------------------------------------------------- perfis

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _load_profile(voice_id: str) -> Dict[str, Any]:
    path = _profile_path(voice_id)
    if not path.exists():
        raise VoiceNotFound(f"Voz não encontrada: {voice_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_profile(profile: Dict[str, Any]) -> None:
    profile["updated_at"] = _now_iso()
    path = _profile_path(profile["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
        json.dump(profile, tmp_file, ensure_ascii=False, indent=2)
    os.replace(tmp_name, path)


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
    analysis = analyze_reference(trimmed if len(trimmed) else np.asarray(audio, dtype=np.float32),
                                 sr_original, ch_original)
    if analysis["quality_status"] == "invalid":
        raise InvalidVoice(
            "A amostra não contém fala suficiente para criar uma voz "
            f"(duração {analysis['duration_seconds']}s, fala {analysis['speech_seconds']}s).",
            analysis,
        )
    reference = trimmed if len(trimmed) else np.asarray(audio, dtype=np.float32)

    voice_id = str(uuid.uuid4())
    voice_dir = _voice_dir(voice_id)
    voice_dir.mkdir(parents=True, exist_ok=False)
    (voice_dir / "embeddings").mkdir()

    (voice_dir / f"original_audio{ext}").write_bytes(audio_bytes)
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
        "reference_hash": ref_hash,
        "analysis": analysis,
        "validation": None,
        "model_embeddings": {"vibevoice_1_5b": {"status": "pending",
                                                "model_revision": None,
                                                "reference_hash": None}},
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
        _save_profile(profile)
        record_app_event("voice_imported", voice_id=new_id)
        return _public(profile)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise InvalidVoice(f"Arquivo de perfil inválido: {exc}")
    except Exception:
        shutil.rmtree(voice_dir, ignore_errors=True)
        raise
