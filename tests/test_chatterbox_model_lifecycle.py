from pathlib import Path

import pytest

from services import model_manager, voice_profiles
from services.chatterbox_adapter import (
    ChatterboxUnavailableError,
    _LocalChatterboxRuntime,
    chatterbox_engine,
)
from services.vibevoice_tts_1_5b import VoiceUnavailableError, generate_voice_1_5b_with_metadata


@pytest.fixture()
def tmp_hf_cache(tmp_path, monkeypatch):
    hf_cache = tmp_path / "hf-cache"
    monkeypatch.setattr(model_manager, "get_hf_cache_dir", lambda: hf_cache)
    return hf_cache


def _install_fake_hf_model(cache_dir: Path, repo_id: str, filenames: tuple[str, ...]) -> Path:
    repo_dir = cache_dir / ("models--" + repo_id.replace("/", "--"))
    snapshot = repo_dir / "snapshots" / "fake"
    snapshot.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        (snapshot / filename).write_bytes(b"0")
    return repo_dir


def test_chatterbox_requires_base_checkpoint_in_catalog_status(tmp_hf_cache):
    spec = model_manager.get_spec("chatterbox-tts-pt-br")

    _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/Chatterbox-Multilingual-pt-br",
        ("t3_pt_br.safetensors", "s3gen_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json"),
    )

    status = model_manager.get_install_status(spec)
    assert status["installed"] is False
    assert status["partial"] is True
    assert status["dependency_status"] == "missing-base-checkpoints"

    _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/chatterbox",
        ("ve.pt", "s3gen.pt"),
    )

    status = model_manager.get_install_status(spec)
    assert status["installed"] is True
    assert status["partial"] is False
    assert status["dependency_status"] == "ready"


def test_delete_chatterbox_removes_language_pack_and_base_checkpoint(tmp_hf_cache):
    spec = model_manager.get_spec("chatterbox-tts-pt-br")
    lang_repo = _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/Chatterbox-Multilingual-pt-br",
        ("t3_pt_br.safetensors", "s3gen_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json"),
    )
    base_repo = _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/chatterbox",
        ("ve.pt", "s3gen.pt"),
    )

    result = model_manager.delete_model(spec.id)

    assert result["removed"] == spec.id
    assert not lang_repo.exists()
    assert not base_repo.exists()


def test_chatterbox_generation_rejects_missing_real_voice_before_model_load(monkeypatch):
    chatterbox_engine.unload()
    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: None)
    monkeypatch.setattr(chatterbox_engine, "_ensure_model", lambda: (_ for _ in ()).throw(AssertionError("nao deve carregar modelo")))

    with pytest.raises(VoiceUnavailableError) as excinfo:
        generate_voice_1_5b_with_metadata(
            text="Ola.",
            model_key="chatterbox-tts-pt-br",
        )

    assert "voz de referencia" in str(excinfo.value).lower()


def test_chatterbox_generation_fails_clearly_when_base_checkpoint_is_missing(monkeypatch, tmp_hf_cache):
    import importlib.util
    import sys
    import types

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)
    monkeypatch.setattr("services.chatterbox_adapter.torch.cuda.is_available", lambda: False)
    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: None)

    fake_chatterbox = types.ModuleType("chatterbox")
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")

    class FakeRealTTS:
        __module__ = "chatterbox.mtl_tts"

    fake_mtl.ChatterboxMultilingualTTS = FakeRealTTS
    monkeypatch.setitem(sys.modules, "chatterbox", fake_chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", fake_mtl)
    monkeypatch.setattr(voice_profiles, "get_voice", lambda voice_id: {"id": voice_id})

    tmp_hf_cache.mkdir(parents=True, exist_ok=True)
    ref_wav = tmp_hf_cache / "reference.wav"
    ref_wav.write_bytes(b"0" * 44)
    monkeypatch.setattr(voice_profiles, "reference_path", lambda voice_id: ref_wav)

    _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/Chatterbox-Multilingual-pt-br",
        ("t3_pt_br.safetensors", "s3gen_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json"),
    )

    chatterbox_engine.unload()

    with pytest.raises(ChatterboxUnavailableError) as excinfo:
        generate_voice_1_5b_with_metadata(
            text="Ola.",
            model_key="chatterbox-tts-pt-br",
            voice_id="11111111-2222-3333-4444-555555555555",
            failure_policy="fail",
        )

    assert "dependencias base" in str(excinfo.value).lower()


def test_chatterbox_falls_back_to_local_runtime_when_wrapper_import_breaks(monkeypatch, tmp_hf_cache):
    import importlib.util
    import sys
    import types

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "chatterbox" else None)
    monkeypatch.setattr("services.chatterbox_adapter.torch.cuda.is_available", lambda: False)
    monkeypatch.setattr(chatterbox_engine, "_try_import_runtime_class", lambda: None)

    _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/Chatterbox-Multilingual-pt-br",
        ("t3_pt_br.safetensors", "s3gen_v3.safetensors", "grapheme_mtl_merged_expanded_v1.json"),
    )
    _install_fake_hf_model(
        tmp_hf_cache,
        "ResembleAI/chatterbox",
        ("ve.pt", "s3gen.pt"),
    )

    load_calls = []

    class FakeVoiceEncoder:
        def load_state_dict(self, state):
            self.state = state

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    class FakeT3:
        hp = type("HP", (), {"speech_cond_prompt_len": 0})()

        def __init__(self, *_args, **_kwargs):
            pass

        def load_state_dict(self, state):
            self.state = state

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    class FakeT3Config:
        @staticmethod
        def multilingual():
            return object()

    class FakeS3Gen:
        def load_state_dict(self, state, strict=True):
            load_calls.append({"state": state, "strict": strict})

        def to(self, device):
            self.device = device
            return self

        def eval(self):
            return self

    class FakeTokenizer:
        def __init__(self, path):
            self.path = path

    fake_s3gen_mod = types.ModuleType("chatterbox.models.s3gen")
    fake_s3gen_mod.S3Gen = FakeS3Gen
    fake_s3gen_mod.S3GEN_SR = 24000
    fake_t3_mod = types.ModuleType("chatterbox.models.t3")
    fake_t3_mod.T3 = FakeT3
    fake_t3_config_mod = types.ModuleType("chatterbox.models.t3.modules.t3_config")
    fake_t3_config_mod.T3Config = FakeT3Config
    fake_tokenizers_mod = types.ModuleType("chatterbox.models.tokenizers")
    fake_tokenizers_mod.MTLTokenizer = FakeTokenizer
    fake_voice_encoder_mod = types.ModuleType("chatterbox.models.voice_encoder")
    fake_voice_encoder_mod.VoiceEncoder = FakeVoiceEncoder
    fake_safetensors_mod = types.ModuleType("safetensors.torch")
    fake_safetensors_mod.load_file = lambda _path: {"model": [{"ok": True}]}

    monkeypatch.setitem(sys.modules, "chatterbox.models.s3gen", fake_s3gen_mod)
    monkeypatch.setitem(sys.modules, "chatterbox.models.t3", fake_t3_mod)
    monkeypatch.setitem(sys.modules, "chatterbox.models.t3.modules.t3_config", fake_t3_config_mod)
    monkeypatch.setitem(sys.modules, "chatterbox.models.tokenizers", fake_tokenizers_mod)
    monkeypatch.setitem(sys.modules, "chatterbox.models.voice_encoder", fake_voice_encoder_mod)
    monkeypatch.setitem(sys.modules, "safetensors.torch", fake_safetensors_mod)
    monkeypatch.setattr(
        "services.chatterbox_adapter.torch.load",
        lambda path, **_kwargs: {"ve": True} if str(path).endswith("ve.pt") else {"model": [{"ok": True}]},
    )

    chatterbox_engine.unload()
    chatterbox_engine._ensure_model()

    assert isinstance(chatterbox_engine.model, _LocalChatterboxRuntime)
    assert load_calls == [{"state": {"ok": True}, "strict": False}]
