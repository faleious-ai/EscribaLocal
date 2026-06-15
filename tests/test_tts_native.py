"""Regressão do motor TTS nativo (funções puras — sem GPU/modelos).

O gate de inteligibilidade (round-trip TTS->Whisper em PT-BR) roda em
scripts/diag_tts_roundtrip.py no hardware real; aqui garantimos que o prompt
nunca regrida do formato do chat_template do checkpoint.
"""
import pytest

from services.vibevoice_tts_1_5b import (
    VIBEVOICE_SYSTEM_PROMPT,
    _frames_cap_for,
    _normalize_script_for_vibevoice,
    _unique_speaker_numbers,
    build_vibevoice_prompt,
)


def test_prompt_single_speaker_with_voice():
    script = "Speaker 1: Olá, mundo."
    prompt = build_vibevoice_prompt(script, {"1": 3})

    assert prompt.startswith(VIBEVOICE_SYSTEM_PROMPT)
    assert " Voice input:\n" in prompt
    assert " Speaker 1:<|vision_start|><|vision_pad|><|vision_pad|><|vision_pad|><|vision_end|>\n" in prompt
    assert " Text input:\n Speaker 1: Olá, mundo.\n" in prompt
    assert prompt.endswith(" Speech output:\n<|vision_start|>")
    assert prompt.count("<|vision_pad|>") == 3


def test_prompt_without_voice_has_no_voice_section():
    prompt = build_vibevoice_prompt("Speaker 1: Oi.", {"1": 0})
    assert " Voice input:" not in prompt
    assert "<|vision_pad|>" not in prompt
    assert prompt.endswith(" Speech output:\n<|vision_start|>")


def test_prompt_multi_speaker_order_preserved():
    script = "Speaker 1: Olá!\nSpeaker 2: Oi, tudo bem?"
    prompt = build_vibevoice_prompt(script, {"1": 2, "2": 4})

    voice_1 = prompt.index(" Speaker 1:<|vision_start|>")
    voice_2 = prompt.index(" Speaker 2:<|vision_start|>")
    assert voice_1 < voice_2
    assert prompt.count("<|vision_pad|>") == 6
    assert " Speaker 1: Olá!\n" in prompt
    assert " Speaker 2: Oi, tudo bem?\n" in prompt


def test_script_normalization_and_speakers():
    script = _normalize_script_for_vibevoice("Voz 2: Olá!\ncontinuação\nSpeaker 1: Oi.", "speaker_1")
    assert script.splitlines() == ["Speaker 2: Olá! continuação", "Speaker 1: Oi."]
    assert _unique_speaker_numbers(script) == ["2", "1"]


def test_frames_cap_bounds():
    assert _frames_cap_for("oi") == 120                      # mínimo
    assert _frames_cap_for(" ".join(["palavra"] * 10)) == 240  # 10*18+60
    assert _frames_cap_for(" ".join(["palavra"] * 10_000)) == 4000  # teto


def test_tts_endpoint_tolerates_unicode_engine_label(client, main_module, monkeypatch):
    """Regressão: rótulo de engine com travessão (U+2014) derrubava o
    /api/tts/generate com 500 ('latin-1' codec can't encode) ao montar os
    headers HTTP da resposta."""
    def fake_generate(**kwargs):
        return {
            "wav_bytes": b"RIFF0000WAVEfake",
            "engine_key": "tts_1_5b",
            "engine_label": "VibeVoice — voz nativa (rótulo unicode)",
            "fallback": False,
        }

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fake_generate)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Olá, mundo.",
            "tts_model": "tts_1_5b",
            "speaker_id": "speaker_1",
            "voice_id": "11111111-2222-3333-4444-555555555555",
        },
    )
    assert response.status_code == 200
    assert response.content == b"RIFF0000WAVEfake"
    assert "voz nativa" in response.headers["x-escriba-tts-engine"]
    assert response.headers["x-escriba-tts-fallback"] == "false"
