"""Lote 6 — testes do config store e dos perfis."""
import json

from services import config_store
from services.resource_arbiter import arbiter


def _profile_body(beam_size=3, name="Meu Perfil"):
    return {
        "name": name,
        "base_preset": None,
        "notes": "perfil de teste",
        "engine_params": {
            "whisper": {"model": "small", "device": "cpu", "compute_type": "int8", "beam_size": beam_size},
            "vibevoice_asr": {},
            "tts": {},
        },
    }


# ----------------------------------------------------------------- settings

def test_get_config_creates_defaults(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    settings = response.json()
    assert settings["vram_policy"] == "exclusive"
    assert settings["first_run_completed"] is False
    assert settings["defaults"]["whisper"]["model"] == "large-v3-turbo"
    assert config_store.SETTINGS_PATH.exists()


def test_put_config_roundtrip_and_vram_policy_side_effect(client):
    settings = client.get("/api/config").json()
    settings["defaults"]["whisper"]["beam_size"] = 7
    settings["vram_policy"] = "manual"

    response = client.put("/api/config", json=settings)
    assert response.status_code == 200

    reloaded = client.get("/api/config").json()
    assert reloaded["defaults"]["whisper"]["beam_size"] == 7
    assert reloaded["vram_policy"] == "manual"
    # Efeito colateral: o árbitro de VRAM passa a usar a política dos settings.
    assert arbiter.policy == "manual"


def test_put_config_invalid_rejected(client):
    settings = client.get("/api/config").json()
    settings["defaults"]["whisper"]["beam_size"] = 99
    assert client.put("/api/config", json=settings).status_code == 422

    settings = client.get("/api/config").json()
    settings["vram_policy"] = "agressiva"
    assert client.put("/api/config", json=settings).status_code == 422


def test_corrupted_settings_recreated_with_backup(client):
    client.get("/api/config")  # cria o arquivo
    config_store.SETTINGS_PATH.write_text("{isso nao e json", encoding="utf-8")
    config_store._settings_cache["settings"] = None
    config_store._settings_cache["mtime"] = None

    settings = config_store.get_settings()
    assert settings.vram_policy == "exclusive"  # defaults recriados
    backup = config_store.SETTINGS_PATH.with_suffix(".json.corrupted.bak")
    assert backup.exists()
    assert json.loads(config_store.SETTINGS_PATH.read_text(encoding="utf-8"))["version"] == 1


# ------------------------------------------------------------------ perfis

def test_profiles_crud_and_apply(client):
    # criar
    response = client.put("/api/profiles/meu-perfil", json=_profile_body(beam_size=3))
    assert response.status_code == 200
    assert response.json()["slug"] == "meu-perfil"

    # listar e buscar
    profiles = client.get("/api/profiles").json()["profiles"]
    assert any(p["slug"] == "meu-perfil" for p in profiles)
    profile = client.get("/api/profiles/meu-perfil").json()
    assert profile["engine_params"]["whisper"]["beam_size"] == 3

    # aplicar: defaults ativos passam a ser os do perfil
    settings = client.post("/api/profiles/meu-perfil/apply").json()
    assert settings["active_profile"] == "meu-perfil"
    assert settings["defaults"]["whisper"]["model"] == "small"
    assert settings["defaults"]["whisper"]["beam_size"] == 3

    # atualizar preserva created_at
    created_at = profile["created_at"]
    update = client.put("/api/profiles/meu-perfil", json=_profile_body(beam_size=4))
    assert update.json()["created_at"] == created_at
    assert update.json()["engine_params"]["whisper"]["beam_size"] == 4

    # remover: limpa active_profile e some da listagem
    assert client.delete("/api/profiles/meu-perfil").status_code == 200
    assert client.get("/api/profiles/meu-perfil").status_code == 404
    assert client.get("/api/config").json()["active_profile"] is None


def test_profile_slug_sanitized(client):
    response = client.put("/api/profiles/Meu Perfil X", json=_profile_body(name="Meu Perfil X"))
    assert response.status_code == 200
    assert response.json()["slug"] == "meu-perfil-x"
    # arquivo criado dentro da pasta de perfis, com nome sanitizado
    assert (config_store.PROFILES_DIR / "meu-perfil-x.json").exists()


def test_profile_invalid_slug_rejected(client):
    response = client.put("/api/profiles/...", json=_profile_body())
    assert response.status_code == 400


def test_apply_unknown_profile_404(client):
    assert client.post("/api/profiles/fantasma/apply").status_code == 404
