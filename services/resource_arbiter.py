"""Arbitragem de VRAM entre as engines de IA (servidor single-GPU, 6GB).

Whisper large-v3 em float16 (~3.3GB) e VibeVoice ASR em NF4 (~4.5GB) não
cabem juntos na RTX 3050 de 6GB — sem arbitragem o resultado é OOM silencioso.
Cada engine se registra aqui no import do seu módulo e chama
``arbiter.prepare_load(engine)`` antes de carregar pesos na GPU.

Políticas:
- ``exclusive`` (default): descarrega as demais engines antes de carregar.
- ``manual``: nunca descarrega sozinho; se a VRAM livre não comporta a
  estimativa da engine, falha com mensagem clara orientando o usuário.

A política pode ser definida pela variável de ambiente ESCRIBA_VRAM_POLICY
até o config store (Lote 6) assumir essa responsabilidade.
"""
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from services.app_logging import record_app_event

logger = logging.getLogger("EscribaLocal.ResourceArbiter")

VALID_POLICIES = ("exclusive", "manual")


class VramInsufficientError(RuntimeError):
    """VRAM livre não comporta a engine na política manual."""


@dataclass(frozen=True)
class EngineRegistration:
    engine: str
    label: str
    is_loaded: Callable[[], bool]
    unload: Callable[[], None]
    est_vram_mb: Callable[[], float]
    current_model: Callable[[], Optional[str]]


def _get_free_vram_mb() -> Optional[float]:
    """VRAM livre no device (nível de dispositivo, inclui alocações CT2)."""
    try:
        import torch

        if torch.cuda.is_available():
            free_bytes, _total = torch.cuda.mem_get_info()
            return free_bytes / 1e6
    except Exception as exc:
        logger.debug("Falha ao ler VRAM livre: %s", exc)
    return None


class ResourceArbiter:
    def __init__(self):
        self._registry: Dict[str, EngineRegistration] = {}
        self._lock = threading.RLock()
        policy = os.environ.get("ESCRIBA_VRAM_POLICY", "exclusive").strip().lower()
        self._policy = policy if policy in VALID_POLICIES else "exclusive"

    # ------------------------------------------------------------- registro

    def register_engine(
        self,
        engine: str,
        label: str,
        is_loaded: Callable[[], bool],
        unload: Callable[[], None],
        est_vram_mb: Callable[[], float],
        current_model: Callable[[], Optional[str]] = lambda: None,
    ) -> None:
        with self._lock:
            self._registry[engine] = EngineRegistration(
                engine=engine, label=label, is_loaded=is_loaded,
                unload=unload, est_vram_mb=est_vram_mb, current_model=current_model,
            )

    def unregister_engine(self, engine: str) -> None:
        with self._lock:
            self._registry.pop(engine, None)

    # -------------------------------------------------------------- política

    @property
    def policy(self) -> str:
        return self._policy

    def set_policy(self, policy: str) -> None:
        if policy not in VALID_POLICIES:
            raise ValueError(f"Política inválida: {policy}. Use uma de {VALID_POLICIES}.")
        self._policy = policy
        record_app_event("vram_policy_changed", policy=policy)

    # -------------------------------------------------------------- consultas

    def status(self) -> List[Dict[str, Any]]:
        """Snapshot de todas as engines registradas (carregadas ou não)."""
        with self._lock:
            registrations = list(self._registry.values())
        snapshot = []
        for reg in registrations:
            try:
                loaded = bool(reg.is_loaded())
            except Exception:
                loaded = False
            try:
                est_vram = float(reg.est_vram_mb()) if loaded else 0.0
            except Exception:
                est_vram = 0.0
            try:
                current = reg.current_model() if loaded else None
            except Exception:
                current = None
            snapshot.append({
                "engine": reg.engine,
                "label": reg.label,
                "loaded": loaded,
                "current_model": current,
                "est_vram_mb": est_vram,
            })
        return snapshot

    def get_loaded(self) -> List[Dict[str, Any]]:
        return [engine for engine in self.status() if engine["loaded"]]

    # ---------------------------------------------------------------- ações

    def unload_engine(self, engine: str) -> bool:
        """Descarrega uma engine. Retorna False se ela não estava carregada.
        Levanta KeyError para engine desconhecida."""
        with self._lock:
            reg = self._registry.get(engine)
            if reg is None:
                raise KeyError(engine)
        if not reg.is_loaded():
            return False
        logger.info("Descarregando engine '%s' (%s)...", engine, reg.label)
        reg.unload()
        record_app_event("engine_unloaded", engine=engine, label=reg.label)
        return True

    def unload_all(self, except_engine: Optional[str] = None) -> List[str]:
        unloaded = []
        for entry in self.get_loaded():
            name = entry["engine"]
            if name == except_engine:
                continue
            try:
                if self.unload_engine(name):
                    unloaded.append(name)
            except KeyError:
                continue
        return unloaded

    def prepare_load(self, engine: str, est_vram_mb: Optional[float] = None) -> Dict[str, Any]:
        """Chamar antes de carregar pesos na GPU.

        exclusive: descarrega as demais engines carregadas.
        manual: valida a VRAM livre contra a estimativa e falha com
        orientação clara se não couber.
        """
        if self._policy == "exclusive":
            unloaded = self.unload_all(except_engine=engine)
            if unloaded:
                record_app_event(
                    "vram_arbiter_unloaded",
                    before_loading=engine,
                    unloaded=unloaded,
                    policy="exclusive",
                )
                logger.info(
                    "Política exclusive: engines %s descarregadas antes de carregar '%s'.",
                    unloaded, engine,
                )
            return {"policy": "exclusive", "unloaded": unloaded}

        # manual
        needed = est_vram_mb
        if needed is None:
            with self._lock:
                reg = self._registry.get(engine)
            if reg is not None:
                try:
                    needed = float(reg.est_vram_mb())
                except Exception:
                    needed = None
        free_mb = _get_free_vram_mb()
        if needed and free_mb is not None and needed > free_mb:
            loaded = self.get_loaded()
            others = ", ".join(
                f"{e['label']} (~{e['est_vram_mb']:.0f}MB)" for e in loaded if e["engine"] != engine
            ) or "nenhuma"
            raise VramInsufficientError(
                f"VRAM insuficiente para carregar '{engine}': necessário ~{needed:.0f}MB, "
                f"livre ~{free_mb:.0f}MB. Engines carregadas: {others}. "
                f"Descarregue-as no painel 'Modelos e Memória' ou use a política 'exclusive'."
            )
        return {"policy": "manual", "unloaded": [], "free_mb": free_mb}


arbiter = ResourceArbiter()
