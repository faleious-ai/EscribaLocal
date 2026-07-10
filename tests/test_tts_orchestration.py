import pytest

from services.tts_orchestration import TtsOrchestrationError, orchestrate_tts, parse_script, validate_script_library


def test_validator_resolves_style_alias_and_event(monkeypatch):
    from services import voice_profiles

    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice_id: {
        "styles": {"items": [{"style_id": "acolhedor", "aliases": ["calmo"],
                                "active": True, "engine_compatibility": {"tts_1_5b": "supported"}}]},
        "events": {"items": {"breath_short": {"event_id": "breath_short"}}},
    })
    ast = parse_script("[calmo]\nOlá.\n[/calmo]\n[respiracao]")

    resolved = validate_script_library(ast, voice_id="voice-a", engine_key="tts_1_5b")

    assert resolved["styles"] == {"calmo": "acolhedor"}
    assert resolved["events"] == ["breath_short"]


def test_validator_rejects_missing_style_speaker_and_event(monkeypatch):
    from services import voice_profiles

    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice_id: {"styles": {"items": []}, "events": {"items": {}}})

    with pytest.raises(TtsOrchestrationError) as excinfo:
        validate_script_library(parse_script("[inexistente falante=ana]\nOi\n[/inexistente]\n[suspiro]"),
                                voice_id="voice-a", speaker_voices={})

    message = str(excinfo.value).lower()
    assert "speaker sem voz" in message


def test_parser_builds_ast_for_style_pause_event_and_subtitle():
    ast = parse_script(
        "## Abertura\n[calmo falante=ana intensidade=0.7]\nOlá.\n[/calmo]\n[pausa 400ms]\n[respiracao profunda]"
    )

    assert [node.kind for node in ast.nodes] == ["subtitle", "style", "pause", "event"]
    assert ast.nodes[1].parameters == {"falante": "ana", "intensidade": "0.7"}
    assert ast.nodes[1].children[0].text == "Olá."


def test_canonical_tags_do_not_reach_engine_script():
    plan = orchestrate_tts("[calmo falante=ana]\nOlá.\n[/calmo]\n[pausa 400ms]")

    assert plan.engine_script == "Olá."
    assert "[" not in plan.engine_script


def test_canonical_subtitle_pause_and_event_do_not_reach_engine_script():
    plan = orchestrate_tts("## Título\nOlá.\n[pausa 400ms]\n[respiracao profunda]")

    assert plan.engine_script == "Olá."
    assert "[" not in plan.engine_script


@pytest.mark.parametrize("script, expected", [
    ("[calmo]\nOlá.", "sem fechamento na linha 1, coluna 1"),
    ("[pausa rápido]", "duração de pausa inválida na linha 1, coluna 1"),
    ("[/calmo]", "fechamento de estilo inválido na linha 1, coluna 1"),
])
def test_parser_reports_line_and_column_for_invalid_syntax(script, expected):
    with pytest.raises(TtsOrchestrationError) as excinfo:
        parse_script(script)

    assert expected in str(excinfo.value).lower()


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


def test_orchestration_keeps_single_speaker_script_plain():
    plan = orchestrate_tts(
        "Bom dia. Este é um teste simples.",
        default_speaker_id="speaker_1",
    )

    assert plan.engine_script == "Bom dia. Este é um teste simples."
    assert len(plan.segments) == 1
    assert plan.segments[0].speaker_number == "1"


def test_tts_generation_does_not_pass_tags_to_engine(monkeypatch):
    from services import vibevoice_tts_1_5b as tts
    from services import voice_profiles

    captured = {}

    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: "voice-real")

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
