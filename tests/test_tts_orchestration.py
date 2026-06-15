import pytest

from services.tts_orchestration import TtsOrchestrationError, orchestrate_tts


def test_orchestration_normalizes_pt_br_and_strips_valid_tags():
    plan = orchestrate_tts(
        "Voz 2: Dra. Ana tem 2 gatos. [style:calmo]\n"
        "Ela pagou R$ 12,50 em 10/05.",
        default_speaker_id="speaker_1",
    )

    assert plan.engine_script == (
        "Speaker 2: doutora Ana tem dois gatos. "
        "Ela pagou doze reais e cinquenta centavos em dez de maio."
    )
    assert "[" not in plan.engine_script
    assert plan.segments[0].speaker_number == "2"
    assert plan.segments[0].style == {"style": "calmo"}


def test_orchestration_rejects_unknown_tags():
    with pytest.raises(TtsOrchestrationError) as excinfo:
        orchestrate_tts("Oi [emotion:feliz].", default_speaker_id="speaker_1")

    assert "tag invalida" in str(excinfo.value).lower()


def test_orchestration_segments_preserve_speaker_and_voice_mapping():
    plan = orchestrate_tts(
        "Speaker 1: " + ("frase curta. " * 30) + "\nSpeaker 2: ok.",
        default_speaker_id="speaker_1",
        speaker_voices={"1": "voice-a", "2": "voice-b"},
        max_segment_chars=120,
    )

    speaker_1_segments = [segment for segment in plan.segments if segment.speaker_number == "1"]
    assert len(speaker_1_segments) > 1
    assert {segment.voice_id for segment in speaker_1_segments} == {"voice-a"}
    assert plan.segments[-1].speaker_number == "2"
    assert plan.segments[-1].voice_id == "voice-b"


def test_tts_generation_does_not_pass_tags_to_engine(monkeypatch):
    from services import vibevoice_tts_1_5b as tts
    from services import voice_profiles

    captured = {}

    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: "voice-real")
    monkeypatch.setattr(voice_profiles, "is_preset", lambda _voice_id: False)

    def fake_native(**kwargs):
        captured["text"] = kwargs["text"]
        return {
            "wav_bytes": b"RIFF0000WAVEfake",
            "engine_key": "tts_1_5b",
            "engine_label": "fake",
            "fallback": False,
        }

    monkeypatch.setattr(tts, "_run_native_vibevoice", fake_native)

    result = tts.generate_voice_1_5b_with_metadata(
        text="Voz 1: Sr. Joao chegou [style:narracao].",
        model_key="tts_1_5b",
        failure_policy="fail",
    )

    assert result["wav_bytes"] == b"RIFF0000WAVEfake"
    assert "[" not in captured["text"]
    assert "senhor Joao chegou" in captured["text"]
