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
