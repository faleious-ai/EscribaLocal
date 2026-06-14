"""Lote 5 — testes do monitor de hardware (NVML + fallbacks)."""
from services import hardware

# Contrato: chaves antigas (frontend depende) + novas aditivas.
LEGACY_KEYS = {"available", "name", "vram_total_mb", "vram_allocated_mb", "vram_cached_mb"}
NEW_KEYS = {"driver_version", "cuda_version", "temperature_c", "gpu_utilization_percent"}


def test_gpu_status_shape():
    status = hardware.get_gpu_status()
    assert LEGACY_KEYS <= set(status.keys())
    assert NEW_KEYS <= set(status.keys())
    assert isinstance(status["available"], bool)
    assert isinstance(status["name"], str)


def test_fallback_when_nvml_unavailable(monkeypatch):
    monkeypatch.setattr(hardware, "_gpu_status_from_nvml", lambda: None)
    status = hardware.get_gpu_status()
    # O fallback (torch/nvidia-smi) preserva o mesmo shape.
    assert LEGACY_KEYS <= set(status.keys())
    assert NEW_KEYS <= set(status.keys())


def test_nvml_failure_is_cached(monkeypatch):
    # Depois de uma falha de init, o NVML não deve ser tentado de novo.
    monkeypatch.setattr(hardware, "_nvml_handle", None)
    monkeypatch.setattr(hardware, "_nvml_failed", True)
    assert hardware._get_nvml_handle() is None


def test_system_status_endpoint_contract(client):
    gpu = client.get("/api/system-status").json()["gpu"]
    assert LEGACY_KEYS <= set(gpu.keys())
    assert NEW_KEYS <= set(gpu.keys())
