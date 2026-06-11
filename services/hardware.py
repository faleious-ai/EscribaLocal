"""Monitor de hardware da GPU.

Cascata de leitura: NVML (pynvml, handle cacheado — sem subprocess) →
nvidia-smi via subprocess (código original do main.py) → torch. O shape do
dict retornado é o mesmo que o /api/system-status sempre expôs, acrescido de
campos aditivos: driver_version, cuda_version, temperature_c e
gpu_utilization_percent.
"""
import logging
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("EscribaLocal.Hardware")

_nvml_lock = threading.Lock()
_nvml_handle = None
_nvml_failed = False


def _decode(value) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _get_nvml_handle():
    """Inicializa o NVML uma única vez e cacheia o handle do device 0."""
    global _nvml_handle, _nvml_failed
    with _nvml_lock:
        if _nvml_handle is not None:
            return _nvml_handle
        if _nvml_failed:
            return None
        try:
            import pynvml

            pynvml.nvmlInit()
            _nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            logger.info("NVML inicializado: %s", _decode(pynvml.nvmlDeviceGetName(_nvml_handle)))
            return _nvml_handle
        except Exception as exc:
            logger.info("NVML indisponível (%s); usando fallback nvidia-smi/torch.", exc)
            _nvml_failed = True
            return None


def _gpu_status_from_nvml() -> Optional[Dict[str, Any]]:
    handle = _get_nvml_handle()
    if handle is None:
        return None
    try:
        import pynvml

        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        status: Dict[str, Any] = {
            "available": True,
            "name": _decode(pynvml.nvmlDeviceGetName(handle)),
            "vram_allocated_mb": round(memory.used / (1024 ** 2), 1),
            "vram_cached_mb": 0.0,
            "vram_total_mb": round(memory.total / (1024 ** 2), 1),
            "driver_version": None,
            "cuda_version": None,
            "temperature_c": None,
            "gpu_utilization_percent": None,
        }
        try:
            status["driver_version"] = _decode(pynvml.nvmlSystemGetDriverVersion())
        except Exception:
            pass
        try:
            cuda_raw = int(pynvml.nvmlSystemGetCudaDriverVersion())
            status["cuda_version"] = f"{cuda_raw // 1000}.{(cuda_raw % 1000) // 10}"
        except Exception:
            pass
        try:
            status["temperature_c"] = int(
                pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            )
        except Exception:
            pass
        try:
            status["gpu_utilization_percent"] = int(
                pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            )
        except Exception:
            pass
        return status
    except Exception as exc:
        logger.warning("Falha na leitura NVML; usando fallback: %s", exc)
        return None


def get_gpu_vram_real() -> Optional[Tuple[float, float]]:
    """(usada_mb, total_mb) via nvidia-smi. Fallback quando o NVML falha;
    necessária porque o CTranslate2 aloca VRAM fora do PyTorch."""
    cmd = "nvidia-smi"
    nvsmi_path = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if not shutil.which(cmd) and os.path.exists(nvsmi_path):
        cmd = nvsmi_path

    try:
        # startupinfo evita que uma janela preta do cmd pisque no Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        output = subprocess.check_output(
            [cmd, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            startupinfo=startupinfo,
            text=True,
        )
        parts = output.strip().split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        pass
    return None


def _gpu_status_from_torch() -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "available": False,
        "name": "Nenhuma GPU detectada",
        "vram_total_mb": 0,
        "vram_allocated_mb": 0,
        "vram_cached_mb": 0,
        "driver_version": None,
        "cuda_version": None,
        "temperature_c": None,
        "gpu_utilization_percent": None,
    }
    try:
        import torch

        if not torch.cuda.is_available():
            return status
        device_id = torch.cuda.current_device()
        status["available"] = True
        status["name"] = torch.cuda.get_device_name(device_id)
        status["cuda_version"] = getattr(torch.version, "cuda", None)

        real_vram = get_gpu_vram_real()
        if real_vram:
            used_mb, total_mb = real_vram
            status["vram_allocated_mb"] = round(used_mb, 1)
            status["vram_total_mb"] = round(total_mb, 1)
        else:
            status["vram_allocated_mb"] = round(torch.cuda.memory_allocated(device_id) / (1024 ** 2), 1)
            status["vram_cached_mb"] = round(torch.cuda.memory_reserved(device_id) / (1024 ** 2), 1)
            status["vram_total_mb"] = round(
                torch.cuda.get_device_properties(device_id).total_memory / (1024 ** 2), 1
            )
    except Exception as exc:
        logger.warning("Erro ao ler informações da GPU via torch: %s", exc)
        status["available"] = True
        status["name"] = "NVIDIA GPU (CUDA Ativo)"
    return status


def get_gpu_status() -> Dict[str, Any]:
    """Status da GPU com o shape do /api/system-status (+ campos aditivos)."""
    status = _gpu_status_from_nvml()
    if status is not None:
        return status
    return _gpu_status_from_torch()
