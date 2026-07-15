import pytest

from services.tts_orchestration import TtsOrchestrationError, orchestrate_tts, parse_script, validate_script_library, build_render_plan


def test_render_plan_is_ordered_and_serializable():
    ast = parse_script("[calmo]\nOlá 2.\n[/calmo]\nTchau.")
    plan = build_render_plan(ast, voice_id="voice-a", reference="ref.wav")
    assert [job.order for job in plan.jobs] == [0, 1]
    assert plan.jobs[0].style_id == "calmo"
    assert plan.jobs[0].original_text == "Olá 2."
    assert plan.manifest()["jobs"][1]["normalized_text"] == "Tchau."
    assert [job.job_id for job in plan.jobs] == [job.job_id for job in build_render_plan(ast, voice_id="voice-a", reference="ref.wav").jobs]


def test_render_plan_preserves_original_and_uses_expanded_normalized_text():
    plan = build_render_plan(parse_script("A reunião é em 03/08/2026."), voice_id="voice-a")
    assert plan.jobs[0].original_text == "A reunião é em 03/08/2026."
    assert plan.jobs[0].normalized_text == "A reunião é em três de agosto de dois mil e vinte e seis."


def test_render_plan_carries_pause_and_event_timeline_metadata():
    plan = build_render_plan(
        parse_script("Olá.\n[pausa 100ms]\n[respiracao profunda]\nTchau."),
        voice_id="voice-a",
    )
    assert plan.jobs[1].pause_before_ms == 100
    assert plan.jobs[1].events_before == ("breath_short",)


def test_render_plan_preserves_sections_order_and_manifest_version():
    ast = parse_script("## Abertura\nPrimeiro.\n## Encerramento\n[serio]\nSegundo 2.\n[/serio]")
    plan = build_render_plan(ast, voice_id="voice-a", reference="refs/neutral.wav")
    assert plan.version == 1
    assert [job.order for job in plan.jobs] == [0, 1]
    assert [job.section_title for job in plan.jobs] == ["Abertura", "Encerramento"]
    assert plan.jobs[0].section_id != plan.jobs[1].section_id
    assert plan.manifest()["jobs"][1]["section_title"] == "Encerramento"
    assert plan.jobs[1].normalized_text == "Segundo dois."


def test_render_plan_ids_are_stable_and_semantically_sensitive():
    base = parse_script("## Abertura\n[calmo intensidade=0.7]\nOla.\n[/calmo]")
    identical_a = build_render_plan(base, voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id
    identical_b = build_render_plan(base, voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id
    variants = [
        build_render_plan(parse_script("## Outra\n[calmo intensidade=0.7]\nOla.\n[/calmo]"), voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id,
        build_render_plan(base, voice_id="voice-b", reference="refs/a.wav").jobs[0].job_id,
        build_render_plan(parse_script("## Abertura\n[serio intensidade=0.7]\nOla.\n[/serio]"), voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id,
        build_render_plan(base, voice_id="voice-a", reference="refs/b.wav").jobs[0].job_id,
        build_render_plan(parse_script("## Abertura\n[calmo intensidade=0.8]\nOla.\n[/calmo]"), voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id,
        build_render_plan(parse_script("## Abertura\n[calmo intensidade=0.7]\nTchau.\n[/calmo]"), voice_id="voice-a", reference="refs/a.wav").jobs[0].job_id,
    ]
    assert identical_a == identical_b
    assert all(job_id != identical_a for job_id in variants)


def test_render_plan_order_changes_job_identity():
    first = build_render_plan(parse_script("Um.\nDois."), voice_id="voice-a").jobs
    swapped = build_render_plan(parse_script("Dois.\nUm."), voice_id="voice-a").jobs
    assert first[0].job_id != swapped[1].job_id
    assert first[1].job_id != swapped[0].job_id


def test_render_plan_section_identity_ignores_unrelated_blank_lines():
    compact = build_render_plan(parse_script("## Abertura\nOla."), voice_id="voice-a").jobs[0]
    spaced = build_render_plan(parse_script("\n\n## Abertura\n\nOla."), voice_id="voice-a").jobs[0]
    assert compact.section_id == spaced.section_id
    assert compact.job_id == spaced.job_id


def test_render_plan_rejects_absolute_reference():
    with pytest.raises(TtsOrchestrationError, match="referencia relativa"):
        build_render_plan(parse_script("Ola."), voice_id="voice-a", reference="C:/voices/ref.wav")


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


def test_render_plan_resolves_two_speakers_two_voices_and_styles(monkeypatch, tmp_path):
    from services import voice_profiles

    profiles = {
        "voice-a": {
            "reference": {"path": "reference.wav"},
            "styles": {"items": [{
                "style_id": "acolhedor", "aliases": ["calmo"], "active": True,
                "parameters": {"intensidade": 0.4, "natural": True},
                "engine_compatibility": {"tts_1_5b": "supported"},
                "reference": {"status": "missing"},
            }]},
        },
        "voice-b": {
            "reference": {"path": "reference.wav"},
            "styles": {"items": [{
                "style_id": "serio", "aliases": ["calmo"], "active": True,
                "parameters": {"ritmo": "lento"},
                "engine_compatibility": {"tts_1_5b": "supported"},
                "reference": {"status": "missing"},
            }]},
        },
    }
    monkeypatch.setattr(voice_profiles, "get_voice", lambda voice: profiles[voice])

    ast = parse_script(
        "[calmo falante=ana intensidade=0.8 ativo=false]\nOi.\n[/calmo]\n"
        "[calmo falante=carlos]\nOla.\n[/calmo]"
    )
    plan = build_render_plan(ast, voice_id="voice-a", speaker_voices={"ana": "voice-a", "carlos": "voice-b"})

    assert [(job.speaker_id, job.voice_id, job.style_id) for job in plan.jobs] == [
        ("ana", "voice-a", "acolhedor"),
        ("carlos", "voice-b", "serio"),
    ]
    assert plan.jobs[0].parameters == {"intensidade": 0.8, "natural": True, "ativo": False}
    assert "falante" not in plan.jobs[0].parameters
    assert plan.jobs[0].reference == "reference.wav"
    assert plan.manifest()["jobs"][1]["speaker_id"] == "carlos"


def test_render_plan_allows_shared_voice_and_style_switch(monkeypatch):
    from services import voice_profiles

    profile = {
        "reference": {"path": "reference.wav"},
        "styles": {"items": [
            {"style_id": "acolhedor", "aliases": [], "active": True, "parameters": {}, "reference": {"status": "missing"}},
            {"style_id": "serio", "aliases": [], "active": True, "parameters": {}, "reference": {"status": "missing"}},
        ]},
    }
    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice: profile)
    ast = parse_script(
        "[acolhedor falante=ana]\nOi.\n[/acolhedor]\n"
        "[serio falante=carlos]\nOla.\n[/serio]"
    )
    plan = build_render_plan(ast, voice_id="voice-a", speaker_voices={"ana": "voice-a", "carlos": "voice-a"})

    assert [job.voice_id for job in plan.jobs] == ["voice-a", "voice-a"]
    assert [job.speaker_id for job in plan.jobs] == ["ana", "carlos"]
    assert [job.style_id for job in plan.jobs] == ["acolhedor", "serio"]
    assert plan.jobs[0].job_id != plan.jobs[1].job_id


def test_render_plan_prefers_ready_style_reference(monkeypatch, tmp_path):
    from services import voice_profiles

    media = tmp_path / "reference.wav"
    media.write_bytes(b"wav")
    profile = {
        "reference": {"path": "reference.wav"},
        "styles": {"items": [{
            "style_id": "acolhedor", "aliases": [], "active": True, "parameters": {},
            "reference": {"status": "ready", "path": "reference.wav"},
        }]},
    }
    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice: profile)
    monkeypatch.setattr(voice_profiles, "style_reference_path", lambda _voice, _style: media)

    job = build_render_plan(
        parse_script("[acolhedor falante=ana]\nOi.\n[/acolhedor]"),
        voice_id="voice-a",
        speaker_voices={"ana": "voice-a"},
    ).jobs[0]
    assert job.reference == "styles/acolhedor/reference.wav"


def test_render_plan_fails_without_mapping_voice_style_or_media(monkeypatch, tmp_path):
    from services import voice_profiles

    with pytest.raises(TtsOrchestrationError, match="Speaker sem voz"):
        build_render_plan(
            parse_script("[calmo falante=ana]\nOi.\n[/calmo]"),
            voice_id="voice-a",
            speaker_voices={},
        )

    monkeypatch.setattr(voice_profiles, "get_voice", lambda voice: (_ for _ in ()).throw(KeyError(voice)))
    with pytest.raises(TtsOrchestrationError, match="Voz inexistente"):
        build_render_plan(
            parse_script("[calmo falante=ana]\nOi.\n[/calmo]"),
            voice_id="voice-a",
            speaker_voices={"ana": "missing"},
        )

    profile = {
        "reference": {"path": "reference.wav"},
        "styles": {"items": [{
            "style_id": "calmo", "active": True, "parameters": {},
            "reference": {"status": "ready", "path": "reference.wav"},
        }]},
    }
    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice: profile)
    monkeypatch.setattr(voice_profiles, "style_reference_path", lambda _voice, _style: tmp_path / "missing.wav")
    with pytest.raises(TtsOrchestrationError, match="ausente"):
        build_render_plan(
            parse_script("[calmo falante=ana]\nOi.\n[/calmo]"),
            voice_id="voice-a",
            speaker_voices={"ana": "voice-a"},
        )


def test_render_plan_rejects_inactive_and_incompatible_styles(monkeypatch):
    from services import voice_profiles

    profiles = iter([
        {"reference": {"path": "reference.wav"}, "styles": {"items": [{"style_id": "calmo", "active": False}]}},
        {"reference": {"path": "reference.wav"}, "styles": {"items": [{
            "style_id": "calmo", "active": True,
            "engine_compatibility": {"tts_1_5b": "blocked"},
            "reference": {"status": "missing"},
        }]}},
    ])
    monkeypatch.setattr(voice_profiles, "get_voice", lambda _voice: next(profiles))
    ast = parse_script("[calmo falante=ana]\nOi.\n[/calmo]")

    with pytest.raises(TtsOrchestrationError, match="inexistente ou inativo"):
        build_render_plan(ast, voice_id="voice-a", speaker_voices={"ana": "voice-a"})
    with pytest.raises(TtsOrchestrationError, match="incompat"):
        build_render_plan(ast, voice_id="voice-a", speaker_voices={"ana": "voice-a"})
