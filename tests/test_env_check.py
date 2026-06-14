"""Lote 8 — testes do verificador de ambiente e da instalação controlada."""
import sys
import time

import pytest

from services import env_check


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    env_check.invalidate_checks_cache()
    # Testes padrão não tocam rede: o check de HF é substituído por um fake.
    monkeypatch.setattr(
        env_check, "check_network_hf",
        lambda: {"name": "network_hf", "status": "ok", "detail": "fake", "fix": None},
    )
    yield
    env_check.invalidate_checks_cache()


def _wait_terminal(client, job_id, timeout=15.0):
    deadline = time.monotonic() + timeout
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = client.get(f"/api/jobs/{job_id}").json()
        if snapshot["state"] in ("completed", "failed", "cancelled"):
            return snapshot
        time.sleep(0.1)
    raise AssertionError(f"job não terminou: {snapshot}")


# -------------------------------------------------------------------- checks

def test_run_all_checks_report_shape():
    report = env_check.run_all_checks()
    assert report["overall"] in ("ok", "warn", "fail")
    names = [check["name"] for check in report["checks"]]
    assert "python" in names and "torch" in names and "ffmpeg" in names
    assert any(name.startswith("pkg:") for name in names)
    assert any(name.startswith("disk:") for name in names)
    for check in report["checks"]:
        assert {"name", "status", "detail", "fix"} <= set(check.keys())
        assert check["status"] in ("ok", "warn", "fail")


def test_checks_cache_and_refresh():
    first = env_check.run_all_checks()
    second = env_check.run_all_checks()
    assert first is second  # cache de 60s devolve o mesmo objeto
    third = env_check.run_all_checks(refresh=True)
    assert third is not first


def test_check_packages_missing_and_mismatch(monkeypatch):
    versions = {"fastapi": None, "uvicorn": "0.1.0"}
    real_version = env_check._installed_version

    def fake_version(name):
        if name in versions:
            return versions[name]
        return real_version(name)

    monkeypatch.setattr(env_check, "_installed_version", fake_version)
    results = {check["name"]: check for check in env_check.check_packages()}

    assert results["pkg:fastapi"]["status"] == "fail"
    assert "fastapi==" in results["pkg:fastapi"]["fix"]
    assert results["pkg:uvicorn"]["status"] == "warn"
    assert "0.1.0" in results["pkg:uvicorn"]["detail"]


def test_environment_endpoint(client):
    report = client.get("/api/environment").json()
    assert report["overall"] in ("ok", "warn", "fail")
    assert len(report["checks"]) > 5


# ----------------------------------------------------------------- allowlist

def test_plan_install_uses_pinned_requirement():
    plan = env_check.plan_install(["fastapi"])
    assert any(req.startswith("fastapi==") for req in plan["packages"])
    assert plan["hot_packages"] == []
    assert plan["requires_restart"] is False
    assert "pip" in plan["command_display"]


def test_plan_install_canonicalizes_names():
    plan = env_check.plan_install(["FastAPI"])
    assert any(req.startswith("fastapi==") for req in plan["packages"])


def test_plan_install_rejects_unknown_and_injection():
    with pytest.raises(env_check.InstallValidationError):
        env_check.plan_install(["pacote-malicioso"])
    with pytest.raises(env_check.InstallValidationError):
        env_check.plan_install(["fastapi; import os"])
    with pytest.raises(env_check.InstallValidationError):
        env_check.plan_install(["fastapi --index-url http://evil"])
    with pytest.raises(env_check.InstallValidationError):
        env_check.plan_install([])


def test_plan_install_hot_packages_flagged():
    plan = env_check.plan_install(["transformers"])
    assert plan["hot_packages"] == ["transformers"]
    assert plan["requires_restart"] is True

    torch_plan = env_check.plan_install(["torch-cu121"])
    assert "torch==2.5.1+cu121" in torch_plan["packages"]
    assert "--index-url" in torch_plan["command"]
    assert env_check.TORCH_CU121_INDEX_URL in torch_plan["command"]


def test_dry_run_inserts_flag(monkeypatch):
    captured = {}

    class FakeCompleted:
        returncode = 0
        stdout = "Would install fastapi-0.136.3"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompleted()

    monkeypatch.setattr(env_check.subprocess, "run", fake_run)
    result = env_check.run_dry_run(["fastapi"])
    assert result["ok"] is True
    install_index = captured["command"].index("install")
    assert captured["command"][install_index + 1] == "--dry-run"


# --------------------------------------------------------------------- rotas

def test_install_requires_confirm(client):
    response = client.post("/api/environment/install", json={"packages": ["fastapi"]})
    assert response.status_code == 400
    assert "confirma" in response.json()["detail"].lower()


def test_install_hot_requires_specific_confirmation(client):
    response = client.post(
        "/api/environment/install",
        json={"packages": ["transformers"], "confirm": True},
    )
    assert response.status_code == 400
    assert "confirm_hot" in response.json()["detail"]
    assert "reinici" in response.json()["detail"].lower()


def test_install_unknown_package_rejected(client):
    response = client.post(
        "/api/environment/install",
        json={"packages": ["pacote-do-mal"], "confirm": True},
    )
    assert response.status_code == 400


def test_install_plan_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        env_check, "run_dry_run",
        lambda packages: {"ok": True, "command_display": "fake", "output_lines": ["Would install fastapi"]},
    )
    response = client.post("/api/environment/install/plan", json={"packages": ["fastapi"]})
    assert response.status_code == 200
    plan = response.json()
    assert plan["dry_run"]["ok"] is True
    assert any(req.startswith("fastapi==") for req in plan["packages"])


def test_install_job_streams_and_completes(client, monkeypatch):
    fake_plan = {
        "packages": ["fastapi==0.136.3"],
        "command": [sys.executable, "-c", "print('linha-1'); print('linha-2')"],
        "command_display": "python -c print",
        "hot_packages": [],
        "requires_restart": False,
    }
    monkeypatch.setattr(env_check, "plan_install", lambda packages: fake_plan)

    response = client.post(
        "/api/environment/install", json={"packages": ["fastapi"], "confirm": True},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    snapshot = _wait_terminal(client, job_id)
    assert snapshot["state"] == "completed"
    assert snapshot["kind"] == "pip_install"


def test_install_job_cancellable(client, monkeypatch):
    fake_plan = {
        "packages": ["fastapi==0.136.3"],
        "command": [sys.executable, "-c",
                    "import time\nfor i in range(200): print(i, flush=True); time.sleep(0.1)"],
        "command_display": "python -c loop",
        "hot_packages": [],
        "requires_restart": False,
    }
    monkeypatch.setattr(env_check, "plan_install", lambda packages: fake_plan)

    response = client.post(
        "/api/environment/install", json={"packages": ["fastapi"], "confirm": True},
    )
    job_id = response.json()["job_id"]
    time.sleep(0.4)  # deixa o processo começar a emitir linhas

    cancel = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel.status_code in (200, 409)

    snapshot = _wait_terminal(client, job_id)
    assert snapshot["state"] == "cancelled"
