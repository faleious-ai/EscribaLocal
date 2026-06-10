"""Patches de compatibilidade de runtime, aplicados uma única vez por processo.

Centraliza os ajustes que antes estavam duplicados em main.py,
vibevoice_service.py, vibevoice_tts_1_5b.py e vibevoice_realtime_0_5b.py.
Todos os módulos que dependem destes patches devem chamar
``apply_runtime_patches()`` no momento do import — a função é idempotente.
"""
import logging

logger = logging.getLogger("EscribaLocal.RuntimePatches")

_applied = False


def apply_runtime_patches() -> None:
    """Aplica todos os patches de compatibilidade. Seguro chamar várias vezes."""
    global _applied
    if _applied:
        return
    _applied = True
    _patch_torch_float8()
    _patch_bitsandbytes_params4bit()


def _patch_torch_float8() -> None:
    # O transformers 5.x referencia torch.float8_e8m0fnu, que não existe no
    # torch 2.5.x; sem este alias o import do transformers falha.
    import torch

    if not hasattr(torch, "float8_e8m0fnu"):
        setattr(torch, "float8_e8m0fnu", torch.float32)
        logger.info("Patch aplicado: torch.float8_e8m0fnu -> torch.float32")


def _patch_bitsandbytes_params4bit() -> None:
    # O transformers 5.x passa o kwarg interno _is_hf_initialized para
    # Params4bit.__new__, que o bitsandbytes 0.49.x não aceita; sem o patch o
    # carregamento quantizado em 4-bit (NF4) do VibeVoice ASR quebra.
    try:
        import bitsandbytes as bnb
    except Exception as exc:  # bitsandbytes é opcional fora de CUDA
        logger.info("bitsandbytes indisponível; patch Params4bit não aplicado: %s", exc)
        return

    original_new = bnb.nn.Params4bit.__new__
    if getattr(original_new, "_escriba_patched", False):
        return

    def patched_new(cls, *args, **kwargs):
        kwargs.pop("_is_hf_initialized", None)
        return original_new(cls, *args, **kwargs)

    patched_new._escriba_patched = True
    bnb.nn.Params4bit.__new__ = patched_new
    logger.info("Patch aplicado: bitsandbytes Params4bit.__new__ (_is_hf_initialized)")
