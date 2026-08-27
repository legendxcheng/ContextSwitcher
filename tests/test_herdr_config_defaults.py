from utils.config import get_config
from gui.qt.qt_settings_dialog import QtSettingsDialog


def test_herdr_monitoring_notification_and_metadata_defaults_are_enabled():
    defaults = get_config().default_config["integrations"]["herdr"]

    assert defaults == {
        "exe_path": "",
        "monitoring_enabled": True,
        "notify_on_blocked": True,
        "notify_on_done": True,
        "metadata_sync_enabled": True,
        "refresh_interval_seconds": 2,
    }


def test_sidebar_fragment_exposes_all_contextswitcher_tokens():
    fragment = QtSettingsDialog.HERDR_SIDEBAR_CONFIG

    for token in ("cs_task", "cs_task_id", "cs_task_status", "cs_task_summary"):
        assert f"${token}" in fragment
