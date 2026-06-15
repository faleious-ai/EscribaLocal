"""Biblioteca de vozes do 1.5B — testes (builder de embeddings mockado)."""
import io
import json

import numpy as np
import pytest
import scipy.io.wavfile as wavfile

from services import voice_profiles


def make_speech_wav(seconds=4.0, sr=48000, stereo=True) -> bytes:
    """WAV sintético com rajadas de energia (passa no detector de fala)."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 220 * t) * (np.sin(2 * np.pi * 2.0 * t) > -0.3)
    audio[: int(0.3 * sr)] = 0.0   # silêncio inicial p/ testar trim
    audio[-int(0.3 * sr):] = 0.0
    pcm = (audio * 32767).astype(np.int16)
    if stereo:
        pcm = np.stack([pcm, pcm], axis=1)
    buffer = io.BytesIO()
    wavfile.write(buffer, sr, pcm)
    return buffer.getvalue()


@pytest.fixture()
def fake_builder(monkeypatch):
    """Builder de embeddings falso (sem GPU/modelo) com contador de chamadas."""
    import torch

    calls = {"count": 0}

    def builder(reference_path):
        calls["count"] += 1
        return torch.ones(6, 1536, dtype=torch.float32), "rev-teste"

    monkeypatch.setattr(voice_profiles, "_embedding_builder", builder)
    monkeypatch.setattr(voice_profiles, "_revision_getter", lambda: "rev-teste")
    return calls


def _upload(client, name="Minha voz", consent=True, content=None, filename="voz.wav",
            endpoint="/api/tts/voices/upload"):
    return client.post(
        endpoint,
        files={"file": (filename, content if content is not None else make_speech_wav(), "audio/wav")},
        data={"name": name, "consent_confirmed": "true" if consent else "false"},
    )


# ----------------------------------------------------------------- criação

def test_create_voice_by_upload(client, fake_builder):
    response = _upload(client)
    assert response.status_code == 200, response.text
    voice = response.json()["voice"]
    analysis = response.json()["analysis"]

    assert voice["name"] == "Minha voz"
    assert voice["source"] == "upload"
    assert voice["consent_confirmed"] is True
    assert voice["is_preset"] is False
    assert len(voice["reference_hash"]) == 64
    assert analysis["quality_status"] in ("good", "acceptable")
    assert analysis["sample_rate_normalized"] == 24000
    assert voice["model_embeddings"]["vibevoice_1_5b"]["status"] == "ready"
    assert fake_builder["count"] == 1


def test_create_voice_by_recording(client, fake_builder):
    response = _upload(client, name="Gravada", filename="gravacao.webm",
                       content=make_speech_wav(), endpoint="/api/tts/voices/record")
    # .webm com conteúdo WAV: o ffmpeg decodifica pelo conteúdo, não extensão.
    assert response.status_code == 200, response.text
    assert response.json()["voice"]["source"] == "recording"


def test_consent_is_mandatory(client, fake_builder):
    response = _upload(client, consent=False)
    assert response.status_code == 422
    assert "autoriza" in json.dumps(response.json(), ensure_ascii=False).lower()


def test_invalid_file_rejected(client, fake_builder):
    response = _upload(client, content=b"isto nao e audio de verdade" * 10)
    assert response.status_code == 422

    response = _upload(client, filename="voz.xyz")
    assert response.status_code == 422


def test_reference_is_mono_24khz(client, fake_builder):
    voice = _upload(client).json()["voice"]
    sr, data = wavfile.read(str(voice_profiles.reference_path(voice["id"])))
    assert sr == 24000
    assert data.ndim == 1  # mono
    # trim removeu silêncio das pontas (original 4.0s com 0.6s de silêncio)
    assert len(data) / sr < 3.9


# ------------------------------------------------------- listagem/persistência

def test_list_only_custom_real_voices(client, fake_builder):
    _upload(client, name="Voz A")
    _upload(client, name="Voz B")
    data = client.get("/api/tts/voices").json()

    assert data["presets"] == []
    assert sorted(v["name"] for v in data["custom"]) == ["Voz A", "Voz B"]
    assert data["total_disk_bytes"] > 0


def test_profile_persists_on_disk(client, fake_builder, isolated_voices):
    voice = _upload(client, name="Persistente").json()["voice"]
    # Reinício simulado: nada em memória — recarrega direto do disco.
    profile = json.loads((isolated_voices / voice["id"] / "profile.json").read_text(encoding="utf-8"))
    assert profile["name"] == "Persistente"
    assert client.get(f"/api/tts/voices/{voice['id']}").json()["name"] == "Persistente"


def test_no_absolute_paths_in_public_responses(client, fake_builder, isolated_voices):
    _upload(client, name="Privada")
    payload = json.dumps(client.get("/api/tts/voices").json())
    assert str(isolated_voices) not in payload
    assert ":\\\\" not in payload and ":\\" not in payload.replace("\\\\", "\\")


# ------------------------------------------------------------------- gestão

def test_rename_and_delete(client, fake_builder, isolated_voices):
    voice = _upload(client, name="Original").json()["voice"]

    renamed = client.patch(f"/api/tts/voices/{voice['id']}", json={"name": "Renomeada"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renomeada"

    deleted = client.delete(f"/api/tts/voices/{voice['id']}")
    assert deleted.status_code == 200
    assert not (isolated_voices / voice["id"]).exists()
    assert client.get(f"/api/tts/voices/{voice['id']}").status_code == 404


def test_delete_preset_rejected(client):
    response = client.delete("/api/tts/voices/preset_windows_1")
    assert response.status_code in (404, 422)


def test_delete_voice_in_use_blocked(client, fake_builder):
    voice = _upload(client).json()["voice"]
    with voice_profiles.voice_in_use([voice["id"]]):
        response = client.delete(f"/api/tts/voices/{voice['id']}")
        assert response.status_code == 409
    assert client.delete(f"/api/tts/voices/{voice['id']}").status_code == 200


def test_set_default(client, fake_builder):
    voice_a = _upload(client, name="A").json()["voice"]
    voice_b = _upload(client, name="B").json()["voice"]
    client.post(f"/api/tts/voices/{voice_a['id']}/set-default")
    client.post(f"/api/tts/voices/{voice_b['id']}/set-default")

    custom = {v["name"]: v for v in client.get("/api/tts/voices").json()["custom"]}
    assert custom["B"]["is_default"] is True
    assert custom["A"]["is_default"] is False
    assert voice_profiles.get_default_voice_id() == voice_b["id"]


def test_path_traversal_blocked(client):
    assert client.get("/api/tts/voices/..%2F..%2Fsegredo").status_code == 404
    with pytest.raises(voice_profiles.VoiceNotFound):
        voice_profiles._voice_dir("../fora")
    with pytest.raises(voice_profiles.VoiceNotFound):
        voice_profiles.reference_path("nome bonito")


# --------------------------------------------------------------- embeddings

def test_embeddings_reused_until_reference_changes(client, fake_builder):
    voice = _upload(client).json()["voice"]
    assert fake_builder["count"] == 1  # eager na criação

    voice_profiles.load_embeddings(voice["id"])
    assert fake_builder["count"] == 1  # cache em disco válido: não reconstrói

    # Troca a referência: hash muda -> embeddings ficam stale -> reconstrói.
    import hashlib
    ref = voice_profiles.reference_path(voice["id"])
    new_wav = make_speech_wav(seconds=2.5, sr=24000, stereo=False)
    ref.write_bytes(new_wav)
    profile = voice_profiles._load_profile(voice["id"])
    profile["reference_hash"] = hashlib.sha256(ref.read_bytes()).hexdigest()
    voice_profiles._save_profile(profile)

    voice_profiles.load_embeddings(voice["id"])
    assert fake_builder["count"] == 2


def test_embeddings_invalidated_by_model_revision(client, fake_builder, monkeypatch):
    voice = _upload(client).json()["voice"]
    assert fake_builder["count"] == 1
    monkeypatch.setattr(voice_profiles, "_revision_getter", lambda: "rev-nova")
    voice_profiles.load_embeddings(voice["id"])
    assert fake_builder["count"] == 2


def test_rebuild_endpoint(client, fake_builder):
    voice = _upload(client).json()["voice"]
    response = client.post(f"/api/tts/voices/{voice['id']}/rebuild")
    assert response.status_code == 200
    assert response.json()["embeddings"]["status"] == "ready"
    assert fake_builder["count"] == 2


# ----------------------------------------------- integração com o serviço 1.5B

def test_custom_voice_never_calls_sapi(client, fake_builder, monkeypatch):
    import torch

    from services import vibevoice_tts_1_5b as tts

    voice = _upload(client).json()["voice"]

    def sapi_must_not_run(*args, **kwargs):
        raise AssertionError("SAPI5 foi chamado com voz personalizada selecionada!")

    monkeypatch.setattr(tts, "_voice_reference_waveform", sapi_must_not_run)
    monkeypatch.setattr(tts, "get_model_revision", lambda mk="tts_1_5b": "rev-teste")
    tts._voice_embeds_cache.clear()

    fake_entry = {"device": "cpu", "model": None, "processor": None, "gen_cfg": None}
    embeds = tts._embeds_for_voice(fake_entry, "tts_1_5b", voice["id"])
    assert tuple(embeds.shape) == (6, 1536)
    assert embeds.dtype == torch.bfloat16


def test_missing_custom_voice_is_clear_error(monkeypatch):
    from services import vibevoice_tts_1_5b as tts

    monkeypatch.setattr(tts, "get_model_revision", lambda mk="tts_1_5b": "rev-teste")
    fake_entry = {"device": "cpu", "model": None, "processor": None, "gen_cfg": None}
    with pytest.raises(tts.VoiceUnavailableError):
        tts._embeds_for_voice(fake_entry, "tts_1_5b",
                              "11111111-2222-3333-4444-555555555555")


def test_speaker_voice_mapping_distinct(client, fake_builder):
    from services.vibevoice_tts_1_5b import _resolve_speaker_voice_map

    voice_a = _upload(client, name="A").json()["voice"]
    voice_b = _upload(client, name="B").json()["voice"]

    mapping = _resolve_speaker_voice_map(
        ["1", "2"], "speaker_1", None, {"1": voice_a["id"], "2": voice_b["id"]},
    )
    assert mapping == {"1": voice_a["id"], "2": voice_b["id"]}

    # Sem mapeamento e sem voz padrão real, a geração falha em vez de cair para
    # presets Windows.
    from services.vibevoice_tts_1_5b import VoiceUnavailableError
    with pytest.raises(VoiceUnavailableError):
        _resolve_speaker_voice_map(["1", "2"], "speaker_1", None, None)

    client.post(f"/api/tts/voices/{voice_a['id']}/set-default")
    default_mapping = _resolve_speaker_voice_map(["1", "2"], "speaker_1", None, None)
    assert default_mapping == {"1": voice_a["id"], "2": voice_a["id"]}


def test_generate_endpoint_passes_real_params(client, main_module, monkeypatch):
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return {"wav_bytes": b"RIFFfake", "engine_key": "tts_1_5b",
                "engine_label": "fake", "fallback": False}

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fake_generate)
    response = client.post("/api/tts/generate", data={
        "text": "Olá.", "tts_model": "tts_1_5b",
        "voice_id": "11111111-2222-3333-4444-555555555555",
        "speaker_voices": json.dumps({"1": "22222222-3333-4444-5555-666666666666"}),
        "cfg_scale": "2.2", "n_diffusion_steps": "14", "max_frames": "300",
        "seed": "7", "failure_policy": "fail", "device": "cpu",
    })
    assert response.status_code == 200
    assert captured["cfg_scale"] == 2.2
    assert captured["n_diffusion_steps"] == 14
    assert captured["max_frames"] == 300
    assert captured["seed"] == 7
    assert captured["failure_policy"] == "fail"
    assert captured["device"] == "cpu"
    assert captured["voice_id"] == "11111111-2222-3333-4444-555555555555"
    assert captured["speaker_voices"] == {"1": "22222222-3333-4444-5555-666666666666"}


def test_realtime_model_blocked(client):
    response = client.post("/api/tts/generate", data={
        "text": "Olá.", "tts_model": "realtime_0_5b",
    })
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "tts_realtime_unavailable"
    assert "worker isolado" in detail["message"].lower()


# ------------------------------------------------------------ export/import

def test_export_import_roundtrip(client, fake_builder):
    voice = _upload(client, name="Exportável").json()["voice"]
    exported = client.get(f"/api/tts/voices/{voice['id']}/export")
    assert exported.status_code == 200

    imported = client.post(
        "/api/tts/voices/import",
        files={"file": ("voz.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 200
    new_voice = imported.json()["voice"]
    assert new_voice["id"] != voice["id"]
    assert new_voice["name"] == "Exportável"
    assert new_voice["model_embeddings"]["vibevoice_1_5b"]["status"] == "pending"
