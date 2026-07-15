import io
import wave

import numpy as np
from scipy.io import wavfile

from services.audio_assembler import assemble_render_plan
from services.tts_orchestration import RenderJob, RenderPlan


def _plan(*jobs):
    return RenderPlan(version=1, jobs=list(jobs))


def _job(job_id="job-a", order=0, **kwargs):
    values = {
        "job_id": job_id,
        "order": order,
        "section_id": None,
        "speaker_id": None,
        "section_title": None,
        "voice_id": "voice-a",
        "style_id": None,
        "reference": None,
        "parameters": {},
        "original_text": "Oi.",
        "normalized_text": "Oi.",
    }
    values.update(kwargs)
    return RenderJob(**values)


def test_assembler_returns_canonical_wav_and_manifest():
    result = assemble_render_plan(_plan(_job()), {"job-a": np.ones(240, dtype=np.float32) * 0.2})

    with wave.open(io.BytesIO(result.wav_bytes), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24000, 1, 2)
        assert wav.getnframes() == 240
    assert result.manifest["sample_rate"] == 24000
    assert result.manifest["channels"] == 1
    assert result.manifest["items"][0]["job_id"] == "job-a"


def test_assembler_orders_pause_and_event_before_the_declared_job():
    plan = _plan(_job("job-a", 0), _job("job-b", 1, pause_before_ms=100, events_before=("breath_short",)))
    result = assemble_render_plan(
        plan,
        {"job-a": np.ones(24, dtype=np.float32), "job-b": np.ones(24, dtype=np.float32)},
        {"breath_short": np.ones(12, dtype=np.float32)},
    )

    assert [item["kind"] for item in result.manifest["items"]] == ["segment", "pause", "event", "segment"]
    assert result.manifest["items"][1]["duration_ms"] == 100


def test_assembler_resamples_stereo_wav_and_rejects_missing_event():
    source = io.BytesIO()
    wavfile.write(source, 12_000, np.ones((12, 2), dtype=np.int16) * 1000)
    result = assemble_render_plan(_plan(_job()), {"job-a": source.getvalue()})
    with wave.open(io.BytesIO(result.wav_bytes), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getnframes()) == (24000, 1, 24)

    missing = _plan(_job(events_before=("unknown",)))
    try:
        assemble_render_plan(missing, {"job-a": np.zeros(4, dtype=np.float32)})
    except ValueError as exc:
        assert "evento ausente" in str(exc)
    else:
        raise AssertionError("evento ausente deveria falhar")
