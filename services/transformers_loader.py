"""Alternância entre o transformers padrão (pip) e o fork vendored.

O fork em ``custom_transformers/`` carrega o VibeVoice TTS e traz também um
``huggingface_hub`` vendored ANTIGO, do qual depende. Os dois grupos de
módulos precisam ser trocados JUNTOS: se o hub vendored vazar para fora da
sessão custom, ele permanece em ``sys.modules`` e quebra o transformers
padrão (ex.: ``cannot import name 'is_offline_mode' from 'huggingface_hub'``
no VibeVoice ASR), além de forçar todo o app a usar um hub desatualizado.
"""
import sys
import os
import contextlib

# Grupos de módulos gerenciados em conjunto nas trocas padrão<->custom.
MANAGED_PREFIXES = ("transformers", "huggingface_hub")

# Caches do estado de sys.modules de cada lado
_custom_modules = {}
_standard_modules = {}


def _custom_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "custom_transformers")


def _managed_snapshot() -> dict:
    return {
        name: module
        for name, module in list(sys.modules.items())
        if any(name == prefix or name.startswith(prefix + ".") for prefix in MANAGED_PREFIXES)
    }


def _is_custom_active() -> bool:
    tf_mod = sys.modules.get("transformers")
    return bool(
        tf_mod is not None
        and getattr(tf_mod, "__file__", None)
        and "custom_transformers" in tf_mod.__file__
    )


@contextlib.contextmanager
def use_custom_transformers():
    global _custom_modules, _standard_modules

    if _is_custom_active():
        yield
        return

    # Guarda os módulos padrão e ativa os do fork
    _standard_modules = _managed_snapshot()
    for name in _standard_modules:
        sys.modules.pop(name, None)
    for name, module in _custom_modules.items():
        sys.modules[name] = module

    custom_path = _custom_path()
    sys.path.insert(0, custom_path)
    try:
        yield
    finally:
        # Guarda os módulos do fork (incl. hub vendored) e restaura os padrão
        _custom_modules = _managed_snapshot()
        for name in _custom_modules:
            sys.modules.pop(name, None)
        if custom_path in sys.path:
            sys.path.remove(custom_path)
        for name, module in _standard_modules.items():
            sys.modules[name] = module


@contextlib.contextmanager
def use_standard_transformers():
    global _custom_modules, _standard_modules

    if not _is_custom_active():
        yield
        return

    _custom_modules = _managed_snapshot()
    for name in _custom_modules:
        sys.modules.pop(name, None)
    for name, module in _standard_modules.items():
        sys.modules[name] = module

    custom_path = _custom_path()
    removed_from_path = False
    if custom_path in sys.path:
        sys.path.remove(custom_path)
        removed_from_path = True

    try:
        yield
    finally:
        _standard_modules = _managed_snapshot()
        for name in _standard_modules:
            sys.modules.pop(name, None)
        if removed_from_path:
            sys.path.insert(0, custom_path)
        for name, module in _custom_modules.items():
            sys.modules[name] = module


def apply_vibevoice_fork_patches() -> None:
    """Patches de compatibilidade do fork com os checkpoints OFICIAIS do HF.

    Chamar com a sessão custom ativa (dentro de ``use_custom_transformers``),
    após importar o transformers do fork. Idempotente.

    1. ``decoder_depths``: o config.json oficial traz ``null`` e o setter do
       fork rejeita o valor — vira no-op (patch que já existia nos módulos TTS).
    2. ``VibeVoiceDiffusionHeadConfig``: o config.json oficial traz
       ``head_ffn_ratio: 3.0`` (float) e a chave ``head_layers`` — o fork
       espera int (dimensões de nn.Linear/chunk) e ``num_head_layers``.
       Sem isso, a carga do VibeVoice-1.5B morre com
       ``TypeError: empty() received an invalid combination of arguments``.
    3. ``VibeVoiceConfig``: o config.json oficial chama o config do LLM de
       ``decoder_config``; o fork espera ``text_config``. Sem o alias, o
       modelo é construído com um Qwen2 default (hidden 4096) e os pesos do
       checkpoint (hidden 1536) não encaixam (size mismatch no embedding).
    """
    from transformers.models.vibevoice_acoustic_tokenizer.configuration_vibevoice_acoustic_tokenizer import (
        VibeVoiceAcousticTokenizerConfig,
    )
    from transformers.models.vibevoice.configuration_vibevoice import (
        VibeVoiceConfig,
        VibeVoiceDiffusionHeadConfig,
    )

    if not getattr(VibeVoiceAcousticTokenizerConfig, "_escriba_decoder_depths_patched", False):
        VibeVoiceAcousticTokenizerConfig.decoder_depths = (
            VibeVoiceAcousticTokenizerConfig.decoder_depths.setter(lambda self, value: None)
        )
        VibeVoiceAcousticTokenizerConfig._escriba_decoder_depths_patched = True

    if not getattr(VibeVoiceDiffusionHeadConfig, "_escriba_head_patched", False):
        original_init = VibeVoiceDiffusionHeadConfig.__init__

        def patched_init(self, *args, **kwargs):
            if "head_layers" in kwargs and "num_head_layers" not in kwargs:
                kwargs["num_head_layers"] = kwargs["head_layers"]
            original_init(self, *args, **kwargs)
            self.head_ffn_ratio = int(self.head_ffn_ratio)
            self.num_head_layers = int(self.num_head_layers)

        VibeVoiceDiffusionHeadConfig.__init__ = patched_init
        VibeVoiceDiffusionHeadConfig._escriba_head_patched = True

    if not getattr(VibeVoiceConfig, "_escriba_text_config_patched", False):
        original_vv_init = VibeVoiceConfig.__init__

        def patched_vv_init(self, *args, **kwargs):
            if "decoder_config" in kwargs and kwargs.get("text_config") is None:
                kwargs["text_config"] = kwargs.pop("decoder_config")
            original_vv_init(self, *args, **kwargs)

        VibeVoiceConfig.__init__ = patched_vv_init
        VibeVoiceConfig._escriba_text_config_patched = True
