"""Lote 4 — testes da arbitragem de VRAM entre engines."""
import pytest

from services import resource_arbiter
from services.resource_arbiter import ResourceArbiter, VramInsufficientError
from services.resource_arbiter import arbiter as global_arbiter


class FakeEngine:
    def __init__(self, name: str, loaded: bool = False, vram: float = 1000.0):
        self.name = name
        self.loaded = loaded
        self.vram = vram
        self.unload_calls = 0

    def register(self, arb: ResourceArbiter):
        arb.register_engine(
            engine=self.name,
            label=f"Fake {self.name}",
            is_loaded=lambda: self.loaded,
            unload=self._unload,
            est_vram_mb=lambda: self.vram,
            current_model=lambda: "fake-model",
        )

    def _unload(self):
        self.unload_calls += 1
        self.loaded = False


# ------------------------------------------------------------- unidade

def test_exclusive_unloads_others_not_self():
    arb = ResourceArbiter()
    arb.set_policy("exclusive")
    engine_a = FakeEngine("a", loaded=True)
    engine_b = FakeEngine("b", loaded=True)
    engine_a.register(arb)
    engine_b.register(arb)

    result = arb.prepare_load("a")

    assert result["unloaded"] == ["b"]
    assert engine_b.unload_calls == 1
    assert engine_a.unload_calls == 0
    assert engine_a.loaded is True and engine_b.loaded is False


def test_manual_insufficient_raises_with_clear_message(monkeypatch):
    arb = ResourceArbiter()
    arb.set_policy("manual")
    target = FakeEngine("alvo", vram=4500.0)
    other = FakeEngine("outra", loaded=True, vram=3000.0)
    target.register(arb)
    other.register(arb)
    monkeypatch.setattr(resource_arbiter, "_get_free_vram_mb", lambda: 1000.0)

    with pytest.raises(VramInsufficientError) as excinfo:
        arb.prepare_load("alvo")

    message = str(excinfo.value)
    assert "VRAM insuficiente" in message
    assert "Fake outra" in message  # diz quem está ocupando
    assert other.unload_calls == 0  # manual nunca descarrega sozinho


def test_manual_sufficient_passes(monkeypatch):
    arb = ResourceArbiter()
    arb.set_policy("manual")
    FakeEngine("alvo", vram=2000.0).register(arb)
    monkeypatch.setattr(resource_arbiter, "_get_free_vram_mb", lambda: 5000.0)

    result = arb.prepare_load("alvo")
    assert result["unloaded"] == []
    assert result["policy"] == "manual"


def test_manual_without_vram_info_passes(monkeypatch):
    arb = ResourceArbiter()
    arb.set_policy("manual")
    FakeEngine("alvo", vram=99999.0).register(arb)
    monkeypatch.setattr(resource_arbiter, "_get_free_vram_mb", lambda: None)
    assert arb.prepare_load("alvo")["unloaded"] == []


def test_unload_engine_unknown_and_not_loaded():
    arb = ResourceArbiter()
    with pytest.raises(KeyError):
        arb.unload_engine("fantasma")
    idle = FakeEngine("idle", loaded=False)
    idle.register(arb)
    assert arb.unload_engine("idle") is False
    assert idle.unload_calls == 0


def test_unload_all_with_exception():
    arb = ResourceArbiter()
    engine_a = FakeEngine("a", loaded=True)
    engine_b = FakeEngine("b", loaded=True)
    engine_a.register(arb)
    engine_b.register(arb)
    unloaded = arb.unload_all(except_engine="a")
    assert unloaded == ["b"]
    assert engine_a.loaded is True


def test_set_policy_validation():
    arb = ResourceArbiter()
    with pytest.raises(ValueError):
        arb.set_policy("agressiva")
    arb.set_policy("manual")
    assert arb.policy == "manual"


def test_status_resilient_to_broken_engine():
    arb = ResourceArbiter()

    def broken():
        raise RuntimeError("engine quebrada")

    arb.register_engine("quebrada", "Quebrada", is_loaded=broken, unload=lambda: None,
                        est_vram_mb=lambda: 0.0)
    status = arb.status()
    assert status[0]["loaded"] is False  # falha vira "não carregada", nunca exceção


# --------------------------------------------------------------- rotas

@pytest.fixture()
def fake_loaded_engine():
    engine = FakeEngine("fake_test_engine", loaded=True, vram=1234.0)
    engine.register(global_arbiter)
    yield engine
    global_arbiter.unregister_engine("fake_test_engine")


def test_loaded_endpoint_lists_engines(client, fake_loaded_engine):
    data = client.get("/api/models/loaded").json()
    assert data["policy"] in ("exclusive", "manual")
    engines = {e["engine"]: e for e in data["engines"]}

    # Engines reais registradas no import dos serviços.
    assert {"whisper", "vibevoice_asr", "tts_1_5b", "tts_large", "tts_realtime"} <= set(engines)

    fake = engines["fake_test_engine"]
    assert fake["loaded"] is True
    assert fake["est_vram_mb"] == 1234.0
    assert fake["current_model"] == "fake-model"


def test_unload_endpoint(client, fake_loaded_engine):
    response = client.post("/api/models/unload", json={"engine": "fake_test_engine"})
    assert response.status_code == 200
    assert response.json()["unloaded"] == ["fake_test_engine"]
    assert fake_loaded_engine.loaded is False

    # Idempotente: descarregar de novo retorna lista vazia, sem erro.
    again = client.post("/api/models/unload", json={"engine": "fake_test_engine"})
    assert again.status_code == 200
    assert again.json()["unloaded"] == []


def test_unload_unknown_engine_404(client):
    response = client.post("/api/models/unload", json={"engine": "fantasma"})
    assert response.status_code == 404


def test_unload_requires_engine_or_all(client):
    response = client.post("/api/models/unload", json={})
    assert response.status_code == 400


def test_unload_all_endpoint(client, fake_loaded_engine):
    response = client.post("/api/models/unload", json={"all": True})
    assert response.status_code == 200
    assert "fake_test_engine" in response.json()["unloaded"]
