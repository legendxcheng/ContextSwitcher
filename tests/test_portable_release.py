import json
import sys
from pathlib import Path
from unittest.mock import patch

from utils.data_storage import DataStorage


class _FakeConfig:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._values = {
            "data.backup_count": 3,
            "data.auto_save": True,
            "data.legacy_migration_completed": False,
        }

    def get_data_dir(self) -> Path:
        return self._data_dir

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value
        return True


def test_frozen_portable_app_migrates_data_from_executable_ancestor(tmp_path):
    current_dir = tmp_path / "appdata" / "ContextSwitcher"
    legacy_dir = tmp_path / "portable-root" / "data"
    executable = tmp_path / "portable-root" / "release" / "app" / "ContextSwitcher.exe"
    current_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)
    executable.parent.mkdir(parents=True)

    legacy_payload = {
        "version": "1.4.0",
        "task_count": 1,
        "tasks": [{"id": "task-1", "name": "Recovered task"}],
    }
    (legacy_dir / "tasks.json").write_text(
        json.dumps(legacy_payload),
        encoding="utf-8",
    )
    (current_dir / "tasks.json").write_text(
        json.dumps({"version": "1.4.0", "task_count": 0, "tasks": []}),
        encoding="utf-8",
    )

    fake_config = _FakeConfig(current_dir)
    with (
        patch("utils.data_storage.get_config", return_value=fake_config),
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "executable", str(executable)),
    ):
        storage = DataStorage()
        storage._legacy_tasks_file = tmp_path / "missing" / "tasks.json"
        tasks = storage.load_tasks()

    assert [task["name"] for task in tasks] == ["Recovered task"]
    assert fake_config.get("data.legacy_migration_completed") is True


def test_windows_batch_build_script_uses_crlf_line_endings():
    script = Path(__file__).resolve().parent.parent / "build_installer.bat"
    lines = script.read_bytes().splitlines(keepends=True)

    assert lines
    assert all(line.endswith(b"\r\n") for line in lines)


def test_build_scripts_share_the_release_app_output_directory():
    project_root = Path(__file__).resolve().parent.parent

    for script_name in ("build.bat", "build_installer.bat"):
        script = (project_root / script_name).read_text(encoding="utf-8").casefold()
        assert 'set "dist=release\\app"' in script
