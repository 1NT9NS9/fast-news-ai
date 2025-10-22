import json
from pathlib import Path

import pytest

import bot.services.storage as storage_module


@pytest.fixture
def storage_env(monkeypatch, tmp_path):
    data_file = tmp_path / "user_data.json"
    data_file.write_text(
        json.dumps(
            {
                "123": {
                    "folders": {"default": ["@initial"]},
                    "active_folder": "default",
                }
            }
        )
    )

    backup_dir = tmp_path / "backups" / "user_data"
    backup_dir.mkdir(parents=True)

    monkeypatch.setattr(storage_module, "USER_DATA_FILE", str(data_file))
    monkeypatch.setattr(storage_module, "USER_DATA_BACKUP_DIR", str(backup_dir))

    storage = storage_module.StorageService()
    storage._last_backup_time = storage_module.datetime.now().timestamp()
    storage._backup_debounce_seconds = 9999

    return storage, backup_dir, data_file


@pytest.mark.asyncio
async def test_restore_user_data_from_valid_backup(storage_env):
    storage, backup_dir, data_file = storage_env
    backup_name = "user_data_20250101_010101.json"
    backup_path = backup_dir / backup_name
    expected_payload = {
        "321": {
            "folders": {"default": ["@restored"]},
            "active_folder": "default",
        }
    }
    backup_path.write_text(json.dumps(expected_payload))

    restored = await storage.restore_user_data_from_backup(str(backup_path))

    assert restored == expected_payload
    assert json.loads(data_file.read_text()) == expected_payload


@pytest.mark.asyncio
async def test_restore_rejects_path_traversal(storage_env, tmp_path):
    storage, backup_dir, _ = storage_env
    outside_backup = tmp_path / "user_data_20250101_010101.json"
    outside_backup.write_text(json.dumps({"bad": True}))

    with pytest.raises(ValueError):
        await storage.restore_user_data_from_backup(str(outside_backup))

    malicious_relative = Path("..") / backup_dir.name / outside_backup.name
    with pytest.raises(ValueError):
        await storage.restore_user_data_from_backup(str(malicious_relative))


@pytest.mark.asyncio
async def test_restore_rejects_invalid_backup_filename(storage_env):
    storage, backup_dir, _ = storage_env
    sneaky_backup = backup_dir / "user_data_latest.json"
    sneaky_backup.write_text(json.dumps({"bad": True}))

    with pytest.raises(ValueError):
        await storage.restore_user_data_from_backup(str(sneaky_backup))
