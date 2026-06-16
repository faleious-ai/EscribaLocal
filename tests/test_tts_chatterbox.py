import pytest
from pathlib import Path
from services import voice_profiles
from services.vibevoice_tts_1_5b import VoiceUnavailableError, generate_voice_1_5b_with_metadata
from services.chatterbox_adapter import ChatterboxUnavailableError, chatterbox_engine
from services.resource_arbiter import arbiter


def test_chatterbox_without_dependency_fails(monkeypatch):
    import importlib.util
    orig_find_spec = importlib.util.find_spec
    
    def mock_find_spec(name, *args, **kwargs):
        if name == "chatterbox":
            return None
        return orig_find_spec(name, *args, **kwargs)
        
    monkeypatch.setattr(importlib.util, "find_spec", mock_find_spec)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda vid: {"id": vid})
    monkeypatch.setattr(voice_profiles, "reference_path", lambda vid: Path(__file__))
    
    chatterbox_engine.unload()
    
    with pytest.raises(ChatterboxUnavailableError) as excinfo:
        generate_voice_1_5b_with_metadata(
            text="Olá",
            model_key="chatterbox-tts-pt-br",
            voice_id="11111111-2222-3333-4444-555555555555",
        )
        
    assert "biblioteca 'chatterbox-tts' ausente" in str(excinfo.value).lower()


def test_chatterbox_missing_voice_fails(monkeypatch):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)
    
    import sys
    import types
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")
    
    class FakeTTS:
        @classmethod
        def from_pretrained(cls, repo_id, device):
            return cls()
        def generate(self, text, audio_prompt_path, **kwargs):
            return [0.0] * 24000
            
    fake_mtl.ChatterboxMultilingualTTS = FakeTTS
    sys.modules["chatterbox"] = fake_chatterbox
    sys.modules["chatterbox.mtl_tts"] = fake_mtl
    
    chatterbox_engine.unload()
    
    def raise_not_found(vid):
        raise voice_profiles.VoiceNotFound("Voz não encontrada")
        
    monkeypatch.setattr(voice_profiles, "resolve_voice_id", lambda vid: vid)
    monkeypatch.setattr(voice_profiles, "get_voice", raise_not_found)
    
    with pytest.raises(VoiceUnavailableError):
        generate_voice_1_5b_with_metadata(
            text="Olá",
            model_key="chatterbox-tts-pt-br",
            voice_id="inexistente",
        )


def test_chatterbox_success(monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)
    
    import sys
    import types
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")
    
    class FakeTTS:
        sr = 24000
        @classmethod
        def from_pretrained(cls, repo_id, device):
            inst = cls()
            inst.device = device
            return inst
        def generate(self, text, audio_prompt_path, **kwargs):
            return [0.1, -0.1] * 12000
            
    fake_mtl.ChatterboxMultilingualTTS = FakeTTS
    sys.modules["chatterbox"] = fake_chatterbox
    sys.modules["chatterbox.mtl_tts"] = fake_mtl
    
    chatterbox_engine.unload()
    
    voice_id = "11111111-2222-3333-4444-555555555555"
    ref_wav = tmp_path / "reference.wav"
    ref_wav.write_bytes(b"0" * 44)
    
    monkeypatch.setattr(voice_profiles, "resolve_voice_id", lambda vid: voice_id)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda vid: {"id": voice_id})
    monkeypatch.setattr(voice_profiles, "reference_path", lambda vid: ref_wav)
    
    result = generate_voice_1_5b_with_metadata(
        text="Olá do Chatterbox.",
        model_key="chatterbox-tts-pt-br",
        voice_id=voice_id,
        failure_policy="fail",
    )
    
    assert result["wav_bytes"]
    assert result["engine_key"] == "chatterbox-tts-pt-br"
    assert result["engine_label"] == "Chatterbox PT-BR"
    
    assert chatterbox_engine.is_loaded() is True
    status = next(s for s in arbiter.status() if s["engine"] == "tts_chatterbox")
    assert status["loaded"] is True
    
    arbiter.unload_engine("tts_chatterbox")
    assert chatterbox_engine.is_loaded() is False


def test_chatterbox_long_text_is_generated_in_multiple_chunks(monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)

    import sys
    import types
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")

    class FakeTTS:
        sr = 24000
        calls = []

        @classmethod
        def from_pretrained(cls, repo_id, device):
            return cls()

        def generate(self, text, audio_prompt_path, **kwargs):
            self.calls.append(text)
            return [0.1, -0.1] * 4000

    fake_mtl.ChatterboxMultilingualTTS = FakeTTS
    monkeypatch.setitem(sys.modules, "chatterbox", fake_chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", fake_mtl)

    chatterbox_engine.unload()

    voice_id = "11111111-2222-3333-4444-555555555555"
    ref_wav = tmp_path / "reference.wav"
    ref_wav.write_bytes(b"0" * 44)

    monkeypatch.setattr(voice_profiles, "resolve_voice_id", lambda vid: voice_id)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda vid: {"id": voice_id})
    monkeypatch.setattr(voice_profiles, "reference_path", lambda vid: ref_wav)

    long_text = (
        "Primeira frase bem longa para forçar a divisão do Chatterbox em blocos menores com bastante conteúdo adicional para passar do limite configurado. "
        "Segunda frase bem longa para continuar o teste de segmentação automática sem perder conteúdo e ainda manter um texto suficientemente comprido para mais de um bloco. "
        "Terceira frase adicional para garantir que o texto ultrapasse com folga o limite de chunking aplicado ao caminho do Chatterbox."
    )

    result = generate_voice_1_5b_with_metadata(
        text=long_text,
        model_key="chatterbox-tts-pt-br",
        voice_id=voice_id,
        failure_policy="fail",
    )

    assert result["wav_bytes"]
    assert len(FakeTTS.calls) >= 2

    chatterbox_engine.unload()


def test_chatterbox_very_long_single_sentence_is_split_by_words(monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)

    import sys
    import types
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")

    class FakeTTS:
        sr = 24000
        calls = []

        @classmethod
        def from_pretrained(cls, repo_id, device):
            return cls()

        def generate(self, text, audio_prompt_path, **kwargs):
            self.calls.append(text)
            return [0.1, -0.1] * 2000

    fake_mtl.ChatterboxMultilingualTTS = FakeTTS
    monkeypatch.setitem(sys.modules, "chatterbox", fake_chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", fake_mtl)

    chatterbox_engine.unload()

    voice_id = "11111111-2222-3333-4444-555555555555"
    ref_wav = tmp_path / "reference.wav"
    ref_wav.write_bytes(b"0" * 44)

    monkeypatch.setattr(voice_profiles, "resolve_voice_id", lambda vid: voice_id)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda vid: {"id": voice_id})
    monkeypatch.setattr(voice_profiles, "reference_path", lambda vid: ref_wav)

    long_sentence = " ".join(["palavra"] * 90)

    result = generate_voice_1_5b_with_metadata(
        text=long_sentence,
        model_key="chatterbox-tts-pt-br",
        voice_id=voice_id,
        failure_policy="fail",
    )

    assert result["wav_bytes"]
    assert len(FakeTTS.calls) >= 2
    assert all(len(call) <= 320 for call in FakeTTS.calls)

    chatterbox_engine.unload()


def test_chatterbox_from_pretrained_supports_device_first_signature(monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)
    monkeypatch.setattr("services.chatterbox_adapter.torch.cuda.is_available", lambda: False)

    import sys
    import types
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")

    class FakeTTS:
        sr = 24000
        calls = []

        @classmethod
        def from_pretrained(cls, device, repo_id=None):
            cls.calls.append({"device": device, "repo_id": repo_id})
            inst = cls()
            inst.device = device
            inst.repo_id = repo_id
            return inst

        def generate(self, text, audio_prompt_path, **kwargs):
            return [0.1, -0.1] * 12000

    fake_mtl.ChatterboxMultilingualTTS = FakeTTS
    monkeypatch.setitem(sys.modules, "chatterbox", fake_chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", fake_mtl)

    chatterbox_engine.unload()

    voice_id = "11111111-2222-3333-4444-555555555555"
    ref_wav = tmp_path / "reference.wav"
    ref_wav.write_bytes(b"0" * 44)

    monkeypatch.setattr(voice_profiles, "resolve_voice_id", lambda vid: voice_id)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda vid: {"id": voice_id})
    monkeypatch.setattr(voice_profiles, "reference_path", lambda vid: ref_wav)

    result = generate_voice_1_5b_with_metadata(
        text="Ola do Chatterbox.",
        model_key="chatterbox-tts-pt-br",
        voice_id=voice_id,
        failure_policy="fail",
    )

    assert result["wav_bytes"]
    assert FakeTTS.calls == [
        {"device": "cpu", "repo_id": "ResembleAI/Chatterbox-Multilingual-pt-br"}
    ]

    chatterbox_engine.unload()
