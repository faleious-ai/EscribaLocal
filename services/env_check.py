"""Verificador de ambiente e instalador controlado de dependências.

Checks (com cache de 60s): Python, torch+CUDA, cuDNN, FFmpeg, pacotes do
requirements vs instalados, espaço em disco dos drives relevantes e
alcançabilidade do HuggingFace.

Instalação de pacotes — regras de segurança inegociáveis:
1. **Allowlist estrita**: só nomes presentes em requirements.txt /
   requirements-dev.txt (mais a entrada especial ``torch-cu121``). O comando
   final usa o requirement PINADO do arquivo — nenhuma string do cliente
   chega ao pip.
2. **Dry-run obrigatório** (``pip install --dry-run``) com saída exibida ao
   usuário antes da confirmação.
3. **Pacotes quentes** (torch/transformers/bitsandbytes/accelerate) nunca em
   fluxo automático: exigem confirmação específica e avisam que o app
   precisa reiniciar.
4. A instalação roda como job com saída do pip em streaming e é cancelável.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.app_logging import record_app_event, record_exception_event
from services.job_execution import run_blocking_job
from services.jobs import job_manager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_FILES = (PROJECT_ROOT / "requirements.txt", PROJECT_ROOT / "requirements-dev.txt")

# Pacotes cuja troca pode quebrar o runtime carregado (fork vendored,
# kernels CUDA): nunca instalar sem confirmação específica + reinício.
HOT_PACKAGES = {"torch", "torch-cu121", "transformers", "bitsandbytes", "accelerate"}

# Única entrada que não vem dos requirements: torch com índice CUDA fixo
# (listá-lo no requirements faria o pip trocar pela build CPU do PyPI).
TORCH_CU121_REQUIREMENT = "torch==2.5.1+cu121"
TORCH_CU121_INDEX_URL = "https://download.pytorch.org/whl/cu121"

DISK_WARN_GB = 25.0
DISK_FAIL_GB = 5.0
CHECKS_CACHE_SECONDS = 60.0

_cache_lock = threading.Lock()
_checks_cache: Dict[str, Any] = {"report": None, "at": 0.0}


class PipInstallCancelled(Exception):
    """Sinaliza cancelamento cooperativo da instalacao."""


class PipInstallExitCodeError(Exception):
    """Sinaliza termino do pip com codigo de erro."""

    def __init__(self, return_code: int):
        self.return_code = return_code
        super().__init__(f"pip exit code {return_code}")


class InstallValidationError(Exception):
    """Pedido de instalação fora das regras (pacote desconhecido, sem confirmação...)."""


def _result(name: str, status: str, detail: str, fix: Optional[str] = None) -> Dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix": fix}


# ------------------------------------------------------------------- checks

def check_python() -> Dict[str, Any]:
    version = sys.version.split()[0]
    if sys.version_info >= (3, 10):
        return _result("python", "ok", version)
    return _result("python", "fail", f"{version} (mínimo 3.10)", "Instale o Python 3.12 e recrie o .venv.")


def check_torch_cuda() -> Dict[str, Any]:
    try:
        import torch
    except Exception as exc:
        return _result("torch", "fail", f"torch não importa: {exc}",
                       "Reinstale com: iniciar.bat (instala torch com CUDA)")
    detail = f"torch {torch.__version__}"
    if torch.cuda.is_available():
        detail += f", CUDA {torch.version.cuda}, {torch.cuda.get_device_name(0)}"
        return _result("torch", "ok", detail)
    return _result("torch", "warn", detail + " — CUDA indisponível (modo CPU)",
                   "Verifique o driver NVIDIA; reinstale torch cu121 pelo painel de ambiente.")


def check_cudnn() -> Dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return _result("cudnn", "warn", "Sem CUDA; cuDNN não se aplica.")
        if torch.backends.cudnn.is_available():
            return _result("cudnn", "ok", f"versão {torch.backends.cudnn.version()}")
        return _result("cudnn", "warn", "cuDNN indisponível", "Reinstale o torch com CUDA.")
    except Exception as exc:
        return _result("cudnn", "warn", f"não verificável: {exc}")


def check_ffmpeg() -> Dict[str, Any]:
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        output = subprocess.check_output([exe, "-version"], text=True, timeout=10,
                                         stderr=subprocess.STDOUT)
        first_line = output.splitlines()[0] if output else "ffmpeg"
        return _result("ffmpeg", "ok", f"{first_line} (bundled imageio-ffmpeg)")
    except Exception as exc:
        return _result("ffmpeg", "fail", f"FFmpeg indisponível: {exc}",
                       "pip install imageio-ffmpeg (pelo painel de ambiente)")


def _installed_version(package_name: str) -> Optional[str]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def _parse_requirements() -> List[Dict[str, Any]]:
    """Lê requirements*.txt e devolve [{name, requirement, file, applicable}]."""
    from packaging.requirements import InvalidRequirement, Requirement

    entries: List[Dict[str, Any]] = []
    for req_file in REQUIREMENTS_FILES:
        if not req_file.exists():
            continue
        for raw_line in req_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                requirement = Requirement(line)
            except InvalidRequirement:
                continue
            applicable = requirement.marker is None or requirement.marker.evaluate()
            entries.append({
                "name": requirement.name,
                "specifier": str(requirement.specifier) or None,
                "requirement": f"{requirement.name}{requirement.specifier}",
                "file": req_file.name,
                "applicable": applicable,
            })
    return entries


def check_packages() -> List[Dict[str, Any]]:
    results = []
    for entry in _parse_requirements():
        if not entry["applicable"]:
            continue
        name = entry["name"]
        installed = _installed_version(name)
        check_name = f"pkg:{name}"
        fix = entry["requirement"]
        if installed is None:
            results.append(_result(check_name, "fail", "não instalado", fix))
            continue
        specifier = entry["specifier"]
        if specifier:
            from packaging.specifiers import SpecifierSet

            if installed not in SpecifierSet(specifier, prereleases=True):
                results.append(_result(
                    check_name, "warn",
                    f"instalado {installed}, requerido {specifier}", fix,
                ))
                continue
        results.append(_result(check_name, "ok", installed))
    return results


def check_disk() -> List[Dict[str, Any]]:
    from services.model_manager import get_hf_cache_dir, get_whisper_cache_dir

    targets = {
        "projeto": PROJECT_ROOT,
        "cache_whisper": get_whisper_cache_dir(),
        "cache_huggingface": get_hf_cache_dir(),
    }
    seen_anchors = set()
    results = []
    for label, path in targets.items():
        probe = Path(path)
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        anchor = Path(probe.anchor or probe)
        if anchor in seen_anchors:
            continue
        seen_anchors.add(anchor)
        try:
            usage = shutil.disk_usage(probe)
        except OSError as exc:
            results.append(_result(f"disk:{label}", "warn", f"não verificável: {exc}"))
            continue
        free_gb = usage.free / (1024 ** 3)
        detail = f"{anchor} {free_gb:.1f}GB livres de {usage.total / (1024 ** 3):.1f}GB"
        if free_gb < DISK_FAIL_GB:
            results.append(_result(f"disk:{label}", "fail", detail,
                                   "Libere espaço (modelos chegam a 19GB) ou remova modelos no painel."))
        elif free_gb < DISK_WARN_GB:
            results.append(_result(f"disk:{label}", "warn", detail,
                                   "Espaço apertado para baixar modelos grandes."))
        else:
            results.append(_result(f"disk:{label}", "ok", detail))
    return results


def check_network_hf() -> Dict[str, Any]:
    started = time.monotonic()
    try:
        request = urllib.request.Request("https://huggingface.co", method="HEAD")
        with urllib.request.urlopen(request, timeout=3.0):
            pass
        latency_ms = round((time.monotonic() - started) * 1000)
        return _result("network_hf", "ok", f"huggingface.co alcançável ({latency_ms}ms)")
    except Exception as exc:
        return _result("network_hf", "warn", f"huggingface.co inacessível: {exc}",
                       "Downloads de modelos não funcionarão; modelos já em cache seguem OK.")


def run_all_checks(refresh: bool = False) -> Dict[str, Any]:
    with _cache_lock:
        cached = _checks_cache["report"]
        if not refresh and cached is not None and time.monotonic() - _checks_cache["at"] < CHECKS_CACHE_SECONDS:
            return cached

    checks: List[Dict[str, Any]] = [check_python(), check_torch_cuda(), check_cudnn(), check_ffmpeg()]
    checks.extend(check_packages())
    checks.extend(check_disk())
    checks.append(check_network_hf())

    statuses = {check["status"] for check in checks}
    overall = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "ok")
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "overall": overall,
        "checks": checks,
    }
    with _cache_lock:
        _checks_cache["report"] = report
        _checks_cache["at"] = time.monotonic()
    record_app_event("environment_checked", overall=overall,
                     fails=sum(1 for c in checks if c["status"] == "fail"),
                     warns=sum(1 for c in checks if c["status"] == "warn"))
    return report


def invalidate_checks_cache() -> None:
    with _cache_lock:
        _checks_cache["report"] = None
        _checks_cache["at"] = 0.0


# --------------------------------------------------------------- instalação

def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def get_allowlist() -> Dict[str, Dict[str, Any]]:
    """Pacotes instaláveis: somente os dos requirements + torch-cu121."""
    allowlist: Dict[str, Dict[str, Any]] = {}
    for entry in _parse_requirements():
        canonical = _canonical(entry["name"])
        allowlist[canonical] = {
            "requirement": entry["requirement"],
            "hot": canonical in HOT_PACKAGES,
            "extra_args": [],
        }
    allowlist["torch-cu121"] = {
        "requirement": TORCH_CU121_REQUIREMENT,
        "hot": True,
        "extra_args": ["--index-url", TORCH_CU121_INDEX_URL],
    }
    return allowlist


def plan_install(packages: List[str]) -> Dict[str, Any]:
    """Valida o pedido contra a allowlist e monta o comando exato.

    O comando usa exclusivamente requirements pinados dos arquivos do
    projeto — nomes fora da allowlist são rejeitados, nunca repassados.
    """
    if not packages:
        raise InstallValidationError("Nenhum pacote informado.")
    allowlist = get_allowlist()
    requirements: List[str] = []
    extra_args: List[str] = []
    hot: List[str] = []
    for requested in packages:
        canonical = _canonical(str(requested))
        entry = allowlist.get(canonical)
        if entry is None:
            raise InstallValidationError(
                f"Pacote fora da lista permitida: {requested!r}. "
                f"Só é possível instalar dependências declaradas nos requirements do projeto."
            )
        requirements.append(entry["requirement"])
        for arg in entry["extra_args"]:
            if arg not in extra_args:
                extra_args.append(arg)
        if entry["hot"]:
            hot.append(canonical)

    command = [sys.executable, "-m", "pip", "install", *requirements, *extra_args,
               "--disable-pip-version-check"]
    return {
        "packages": requirements,
        "command": command,
        "command_display": " ".join(command),
        "hot_packages": hot,
        "requires_restart": bool(hot),
    }


def run_dry_run(packages: List[str]) -> Dict[str, Any]:
    """pip install --dry-run com o mesmo comando do plano (sem alterar nada)."""
    plan = plan_install(packages)
    command = list(plan["command"])
    command.insert(command.index("install") + 1, "--dry-run")
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        lines = (completed.stdout + completed.stderr).splitlines()
        return {"ok": completed.returncode == 0, "command_display": " ".join(command),
                "output_lines": lines[-80:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "command_display": " ".join(command),
                "output_lines": ["Tempo esgotado no dry-run (180s)."]}


def start_install_job(packages: List[str], confirm: bool, confirm_hot: bool = False) -> Dict[str, Any]:
    if not confirm:
        raise InstallValidationError("Instalação exige confirmação explícita (confirm: true).")
    plan = plan_install(packages)
    if plan["hot_packages"] and not confirm_hot:
        raise InstallValidationError(
            "Os pacotes "
            + ", ".join(plan["hot_packages"])
            + " afetam o runtime de IA (CUDA/fork vendored) e exigem confirmação específica "
              "(confirm_hot: true). O servidor precisará ser reiniciado após a instalação."
        )

    job = job_manager.create(kind="pip_install", params={
        "packages": plan["packages"],
        "hot_packages": plan["hot_packages"],
        "command_display": plan["command_display"],
    })

    def worker():
        process_holder: Dict[str, Any] = {"process": None}

        def run_install(publish, cancel_event):
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            process = subprocess.Popen(
                plan["command"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                startupinfo=startupinfo,
            )
            process_holder["process"] = process
            publish({"type": "pip_output", "line": "$ " + plan["command_display"]})
            try:
                for line in process.stdout:
                    if cancel_event.is_set():
                        process.kill()
                        raise PipInstallCancelled()
                    publish({"type": "pip_output", "line": line.rstrip()})
                return_code = process.wait()
            except Exception:
                try:
                    process.kill()
                except OSError:
                    pass
                raise

            if cancel_event.is_set():
                raise PipInstallCancelled()
            invalidate_checks_cache()
            if return_code != 0:
                raise PipInstallExitCodeError(return_code)
            return {"requires_restart": plan["requires_restart"]}

        def install_done(summary):
            done_message = "Instalação concluída."
            if summary["requires_restart"]:
                done_message += " REINICIE o servidor para os pacotes entrarem em vigor."
            return {"type": "done", "message": done_message}

        def install_cancelled(_exc):
            return {"type": "cancelled", "message": "Instalação cancelada (pip interrompido)."}

        def install_error(exc):
            record_exception_event("pip_install_error", exc, packages=plan["packages"])

        def install_error_event(exc):
            if isinstance(exc, PipInstallExitCodeError):
                return {"type": "error", "message": f"pip terminou com código {exc.return_code}."}
            return {"type": "error", "message": str(exc)}

        def before_finish(_job, final_state, _error_message):
            process = process_holder.get("process")
            if process is None:
                return
            if final_state.value == "cancelled" and process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass

        run_blocking_job(
            job,
            run_install,
            cancelled_exceptions=(PipInstallCancelled,),
            success_event_factory=install_done,
            cancelled_event_factory=install_cancelled,
            error_event_factory=install_error_event,
            result_summary_factory=lambda summary: summary,
            on_exception=install_error,
            before_finish=before_finish,
        )

    threading.Thread(target=worker, daemon=True, name="pip-install").start()
    record_app_event("pip_install_started", job_id=job.job_id, packages=plan["packages"],
                     hot=plan["hot_packages"])
    return {"job_id": job.job_id, "command_display": plan["command_display"],
            "requires_restart": plan["requires_restart"]}
