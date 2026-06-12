"""Hotfix TTS — regressão do isolamento do hub e dos patches do fork.

O import de ``main`` (fixture main_module) já executa uma sessão custom no
startup (módulos TTS), então estes testes validam o estado APÓS essa sessão.
"""
from importlib.metadata import version


def test_standard_hub_not_polluted_by_fork(main_module):
    """Regressão: o huggingface_hub vendored do fork vazava para o processo e
    quebrava o transformers padrão (erro 'is_offline_mode' no VibeVoice ASR)."""
    import huggingface_hub

    assert "custom_transformers" not in (huggingface_hub.__file__ or ""), (
        "o huggingface_hub vendored do fork vazou para fora da sessão custom"
    )
    assert huggingface_hub.__version__ == version("huggingface_hub")
    assert hasattr(huggingface_hub, "is_offline_mode")


def test_standard_transformers_outside_session(main_module):
    import transformers

    assert "custom_transformers" not in (transformers.__file__ or "")
    assert transformers.__version__ == version("transformers")


def test_fork_session_uses_vendored_hub_and_restores(main_module):
    from services.transformers_loader import use_custom_transformers

    with use_custom_transformers():
        import transformers as fork_tf
        assert "custom_transformers" in fork_tf.__file__
        import huggingface_hub as fork_hub
        assert "custom_transformers" in (fork_hub.__file__ or ""), (
            "dentro da sessão custom o fork deve usar o hub vendored dele"
        )

    import huggingface_hub
    assert "custom_transformers" not in (huggingface_hub.__file__ or "")


def test_fork_patches_fix_official_checkpoint_config(main_module):
    """O config.json oficial traz head_ffn_ratio=3.0 (float) e head_layers;
    o patch precisa entregar dimensões int para o nn.Linear."""
    from services.transformers_loader import apply_vibevoice_fork_patches, use_custom_transformers

    with use_custom_transformers():
        apply_vibevoice_fork_patches()
        apply_vibevoice_fork_patches()  # idempotente
        from transformers.models.vibevoice.configuration_vibevoice import VibeVoiceDiffusionHeadConfig

        config = VibeVoiceDiffusionHeadConfig(hidden_size=1536, head_ffn_ratio=3.0, head_layers=4)
        assert config.head_ffn_ratio == 3
        assert isinstance(config.head_ffn_ratio, int)
        assert config.intermediate_size == 4608
        assert isinstance(config.intermediate_size, int)
        assert config.num_head_layers == 4
