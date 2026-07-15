"""Montagem determinística de segmentos TTS em WAV canônico."""

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly


OUTPUT_SAMPLE_RATE = 24_000
OUTPUT_CHANNELS = 1
FADE_MS = 5


class AudioAssemblyError(ValueError):
    """Entrada de timeline ou áudio incompatível com o contrato."""


@dataclass(frozen=True)
class AudioAssemblyResult:
    wav_bytes: bytes
    manifest: dict


class RenderAudioCache:
    """Cache local de WAVs intermediários indexado por identidade do job."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path_for(self, job_id: str) -> Path:
        clean = str(job_id or "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", clean):
            raise AudioAssemblyError(f"job_id inválido para cache: {job_id!r}.")
        return self.root / f"{clean}.wav"

    def store(self, job_id: str, audio: object) -> Path:
        _, normalized = _decode_audio(audio)
        path = self.path_for(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_wav_bytes(normalized))
        return path

    def load(self, job_id: str) -> bytes:
        path = self.path_for(job_id)
        if not path.is_file():
            raise AudioAssemblyError(f"Áudio ausente no cache para job: {job_id}.")
        return path.read_bytes()


def _decode_audio(value: object) -> tuple[int, np.ndarray]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            sample_rate, audio = wavfile.read(io.BytesIO(bytes(value)))
        except Exception as exc:
            raise AudioAssemblyError("Áudio WAV inválido.") from exc
    else:
        sample_rate = OUTPUT_SAMPLE_RATE
        audio = np.asarray(value)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if audio.ndim != 1 or not audio.size:
        raise AudioAssemblyError("Áudio deve ser um vetor mono não vazio.")
    if np.issubdtype(audio.dtype, np.integer):
        limit = max(abs(np.iinfo(audio.dtype).min), np.iinfo(audio.dtype).max)
        audio = audio.astype(np.float32) / limit
    else:
        audio = audio.astype(np.float32, copy=True)
    audio = np.clip(audio, -1.0, 1.0)
    if sample_rate != OUTPUT_SAMPLE_RATE:
        gcd = np.gcd(int(sample_rate), OUTPUT_SAMPLE_RATE)
        audio = resample_poly(audio, OUTPUT_SAMPLE_RATE // gcd, int(sample_rate) // gcd).astype(np.float32)
    return OUTPUT_SAMPLE_RATE, audio.copy()


def _silence(milliseconds: int) -> np.ndarray:
    if milliseconds < 0:
        raise AudioAssemblyError("Duração de pausa não pode ser negativa.")
    return np.zeros(round(OUTPUT_SAMPLE_RATE * milliseconds / 1000), dtype=np.float32)


def _with_edge_fades(audio: np.ndarray) -> np.ndarray:
    result = audio.copy()
    fade_samples = min(round(OUTPUT_SAMPLE_RATE * FADE_MS / 1000), result.size // 2)
    if fade_samples:
        ramp = np.linspace(0.0, 1.0, fade_samples, endpoint=True, dtype=np.float32)
        result[:fade_samples] *= ramp
        result[-fade_samples:] *= ramp[::-1]
    return result


def _wav_bytes(audio: np.ndarray) -> bytes:
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    output = io.BytesIO()
    wavfile.write(output, OUTPUT_SAMPLE_RATE, pcm)
    return output.getvalue()


def assemble_render_plan(plan, segments: Mapping[str, object], events: Optional[Mapping[str, object]] = None) -> AudioAssemblyResult:
    """Monta segmentos e eventos na ordem do RenderPlan, sem mutar as entradas."""
    if not plan.jobs:
        raise AudioAssemblyError("RenderPlan não contém jobs.")
    event_audio = events or {}
    chunks = []
    items = []
    for job in sorted(plan.jobs, key=lambda item: item.order):
        pause_ms = int(getattr(job, "pause_before_ms", 0) or 0)
        if pause_ms:
            chunks.append(_silence(pause_ms))
            items.append({"kind": "pause", "duration_ms": pause_ms, "before_job_id": job.job_id})
        for event_id in tuple(getattr(job, "events_before", ()) or ()):
            if event_id not in event_audio:
                raise AudioAssemblyError(f"Áudio do evento ausente: {event_id}.")
            _, event = _decode_audio(event_audio[event_id])
            chunks.append(_with_edge_fades(event))
            items.append({"kind": "event", "event_id": event_id, "duration_ms": round(event.size * 1000 / OUTPUT_SAMPLE_RATE)})
        if job.job_id not in segments:
            raise AudioAssemblyError(f"Áudio ausente para job: {job.job_id}.")
        _, audio = _decode_audio(segments[job.job_id])
        audio = _with_edge_fades(audio)
        chunks.append(audio)
        items.append({"kind": "segment", "job_id": job.job_id, "order": job.order,
                      "duration_ms": round(audio.size * 1000 / OUTPUT_SAMPLE_RATE)})
    merged = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    wav_bytes = _wav_bytes(merged)
    manifest = {"version": getattr(plan, "version", 1), "sample_rate": OUTPUT_SAMPLE_RATE,
                "channels": OUTPUT_CHANNELS, "duration_ms": round(merged.size * 1000 / OUTPUT_SAMPLE_RATE),
                "items": items}
    return AudioAssemblyResult(wav_bytes=wav_bytes, manifest=manifest)


def assemble_cached_render_plan(plan, cache: RenderAudioCache,
                                 regenerated: Optional[Mapping[str, object]] = None,
                                 events: Optional[Mapping[str, object]] = None) -> AudioAssemblyResult:
    """Atualiza somente jobs regenerados e remonta usando o restante do cache."""
    jobs = {job.job_id for job in plan.jobs}
    for job_id, audio in (regenerated or {}).items():
        if job_id not in jobs:
            raise AudioAssemblyError(f"Job regenerado não pertence ao RenderPlan: {job_id}.")
        cache.store(job_id, audio)
    segments = {job_id: cache.load(job_id) for job_id in jobs}
    return assemble_render_plan(plan, segments, events=events)
