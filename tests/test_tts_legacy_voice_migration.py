import json
from pathlib import Path

from services import config_store


VOICE_A = "11111111-2222-3333-4444-555555555555"
VOICE_B = "22222222-3333-4444-5555-666666666666"
MISSING_VOICE = "33333333-4444-5555-6666-777777777777"


def _settings_payload() -> dict:
    return config_store.SettingsModel().model_dump()


def _write_settings(raw: dict) -> None:
    config_store.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config_store.SETTINGS_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    config_store._settings_cache = {"settings": None, "mtime": None}


def _read_settings_raw() -> dict:
    return json.loads(config_store.SETTINGS_PATH.read_text(encoding="utf-8"))


def _write_voice(voices_dir: Path, voice_id: str, *, is_default: bool = False) -> None:
    voice_dir = voices_dir / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "profile.json").write_text(
        json.dumps({
            "id": voice_id,
            "name": f"Voz {voice_id[:4]}",
            "source": "upload",
            "language": "pt-BR",
            "created_at": "2026-06-16T00:00:00-0300",
            "updated_at": "2026-06-16T00:00:00-0300",
            "duration_seconds": 5.0,
            "sample_rate": 24000,
            "consent_confirmed": True,
            "is_preset": False,
            "is_default": is_default,
            "reference_hash": "a" * 64,
            "analysis": {},
            "validation": None,
            "model_embeddings": {},
        }),
        encoding="utf-8",
    )


def test_legacy_preset_windows_config_is_cleared_without_real_voice():
    raw = _settings_payload()
    raw["defaults"]["tts"]["voice_id"] = "preset_windows_1"
    raw["defaults"]["tts"]["speaker_voices"] = {"1": "speaker_1"}
    _write_settings(raw)

    config_store.get_settings()

    migrated = _read_settings_raw()
    assert migrated["defaults"]["tts"]["voice_id"] == ""
    assert migrated["defaults"]["tts"]["speaker_voices"] == {}


def test_legacy_speaker_identity_config_uses_single_unambiguous_real_voice(isolated_voices):
    _write_voice(isolated_voices, VOICE_A, is_default=True)
    raw = _settings_payload()
    raw["defaults"]["tts"]["voice_id"] = "speaker_1"
    raw["defaults"]["tts"]["speaker_voices"] = {
        "1": "preset_windows_1",
        "2": VOICE_A,
    }
    _write_settings(raw)

    config_store.get_settings()

    migrated = _read_settings_raw()
    assert migrated["defaults"]["tts"]["voice_id"] == VOICE_A
    assert migrated["defaults"]["tts"]["speaker_voices"] == {"1": VOICE_A, "2": VOICE_A}


def test_real_voice_config_is_preserved_and_missing_voice_is_cleared(isolated_voices):
    _write_voice(isolated_voices, VOICE_A, is_default=True)
    raw = _settings_payload()
    raw["defaults"]["tts"]["voice_id"] = VOICE_A
    raw["defaults"]["tts"]["speaker_voices"] = {
        "1": VOICE_A,
        "2": MISSING_VOICE,
    }
    _write_settings(raw)

    config_store.get_settings()

    migrated = _read_settings_raw()
    assert migrated["defaults"]["tts"]["voice_id"] == VOICE_A
    assert migrated["defaults"]["tts"]["speaker_voices"] == {"1": VOICE_A}


def test_legacy_voice_config_migration_is_idempotent(isolated_voices):
    _write_voice(isolated_voices, VOICE_A, is_default=True)
    _write_voice(isolated_voices, VOICE_B, is_default=False)
    raw = _settings_payload()
    raw["defaults"]["tts"]["voice_id"] = "preset_windows_2"
    raw["defaults"]["tts"]["speaker_voices"] = {"1": "speaker_1", "2": MISSING_VOICE}
    _write_settings(raw)

    config_store.get_settings()
    first_run = config_store.SETTINGS_PATH.read_text(encoding="utf-8")
    config_store._settings_cache = {"settings": None, "mtime": None}
    config_store.get_settings()
    second_run = config_store.SETTINGS_PATH.read_text(encoding="utf-8")

    assert first_run == second_run
    migrated = json.loads(second_run)
    assert migrated["defaults"]["tts"]["voice_id"] == VOICE_A
    assert migrated["defaults"]["tts"]["speaker_voices"] == {"1": VOICE_A}


def test_voice_library_has_localstorage_legacy_migration():
    source = Path("static/js/voice_library.js").read_text(encoding="utf-8")

    assert "migrateLegacyVoiceSettings" in source
    assert "LEGACY_VOICE_IDS" in source
    assert "preset_windows_1" in source
    assert "speaker_1" in source
    assert "localStorage.setItem(STORAGE_KEY" in source
