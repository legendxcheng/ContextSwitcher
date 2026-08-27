import ast
import json
import os
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.config import Config
from utils.localization import Localizer, get_localizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = PROJECT_ROOT / "locales"


def _flatten(payload, prefix=""):
    result = {}
    for name, value in payload.items():
        if name == "_meta":
            continue
        key = f"{prefix}.{name}" if prefix else name
        if isinstance(value, dict):
            result.update(_flatten(value, key))
        else:
            result[key] = value
    return result


def _format_fields(template):
    return {
        field_name.split(".", 1)[0].split("[", 1)[0]
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }


class TestLocalizer(unittest.TestCase):
    def setUp(self):
        self.localizer = Localizer(LOCALES_DIR)

    def test_discovers_bundled_languages_and_normalizes_locale_codes(self):
        self.assertEqual(
            ["en-US", "zh-CN"],
            [language.code for language in self.localizer.available_languages()],
        )
        self.assertEqual("en-US", self.localizer.set_language("en_GB"))
        self.assertEqual("zh-CN", self.localizer.set_language("zh_CN"))

    def test_system_language_and_unsupported_language_fallback(self):
        self.assertEqual(
            "en-US",
            self.localizer.set_language("system", system_language="en-GB"),
        )
        self.assertEqual("zh-CN", self.localizer.set_language("fr-FR"))

    def test_translation_formats_parameters_and_notifies_live_listeners(self):
        observed = []

        class Listener:
            def changed(self, language):
                observed.append(language)

        listener = Listener()
        self.localizer.subscribe(listener.changed)
        self.localizer.set_language("en-US")

        self.assertEqual(["en-US"], observed)
        self.assertEqual(
            "Switched to: Demo",
            self.localizer.translate("main.messages.switched", task="Demo"),
        )

    def test_catalogs_have_identical_keys_and_format_placeholders(self):
        catalogs = {}
        for path in LOCALES_DIR.glob("*.json"):
            catalogs[path.stem] = _flatten(
                json.loads(path.read_text(encoding="utf-8"))
            )

        fallback = catalogs["zh-CN"]
        for locale_name, catalog in catalogs.items():
            self.assertEqual(
                set(fallback),
                set(catalog),
                f"Translation keys differ for {locale_name}",
            )
            for key, template in fallback.items():
                self.assertEqual(
                    _format_fields(template),
                    _format_fields(catalog[key]),
                    f"Format placeholders differ for {locale_name}:{key}",
                )

    def test_literal_translation_keys_used_by_python_exist(self):
        fallback = _flatten(
            json.loads((LOCALES_DIR / "zh-CN.json").read_text(encoding="utf-8"))
        )
        used_keys = set()
        source_paths = [PROJECT_ROOT / "main.py"]
        for directory in ("core", "gui", "utils"):
            source_paths.extend((PROJECT_ROOT / directory).rglob("*.py"))

        for path in source_paths:
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"), filename=str(path)
            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "tr":
                    key = node.args[0]
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        used_keys.add(key.value)

        self.assertEqual(set(), used_keys - set(fallback))


class TestLanguageConfigMigration(unittest.TestCase):
    def test_new_install_follows_system_language(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            with patch.object(Config, "_get_user_config_dir", return_value=config_dir):
                config = Config()
            self.assertEqual("system", config.get("app.language"))

    def test_existing_config_without_language_stays_chinese(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "config.json").write_text(
                json.dumps({"app": {"first_run": False}}),
                encoding="utf-8",
            )
            with patch.object(Config, "_get_user_config_dir", return_value=config_dir):
                config = Config()
            self.assertEqual("zh-CN", config.get("app.language"))


try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from core.task_manager import TaskManager
    from gui.qt.qt_main_window import QtMainWindow
    from gui.qt.qt_settings_dialog import QtSettingsDialog
    from gui.qt.qt_task_dialog import QtTaskDialog
    from gui.qt.qt_task_switcher import QtTaskSwitcher
    from gui.qt.qt_welcome_dialog import QtWelcomeDialog
    from gui.qt.qt_window_selector import QtWindowSelector
    from gui.qt.widgets.system_tray import SystemTrayIcon

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not available")
class TestLiveQtRetranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        get_localizer().set_language("zh-CN")

    def test_open_settings_dialog_retranslates_immediately(self):
        get_localizer().set_language("zh-CN")
        dialog = QtSettingsDialog(None, TaskManager())
        self.assertEqual("应用设置", dialog.windowTitle())

        get_localizer().set_language("en-US")
        self.app.processEvents()

        self.assertEqual("Application Settings", dialog.windowTitle())
        self.assertEqual("Notifications", dialog.notify_group.title())
        english_index = dialog.language_combo.findData("en-US")
        self.assertEqual(
            "English (United States)", dialog.language_combo.itemText(english_index)
        )
        dialog.close()

    def test_major_qt_surfaces_retranslate_without_recreation(self):
        get_localizer().set_language("zh-CN")
        manager = TaskManager()
        main_window = QtMainWindow(manager)
        task_dialog = QtTaskDialog(main_window, manager)
        switcher = QtTaskSwitcher(manager)
        welcome = QtWelcomeDialog(main_window)
        selector = QtWindowSelector(manager.window_manager, main_window)
        tray = SystemTrayIcon()

        get_localizer().set_language("en-US")
        self.app.processEvents()

        self.assertEqual("Today:", main_window.today_label.text())
        self.assertEqual(
            "Task",
            main_window.task_table.horizontalHeaderItem(
                main_window.task_table.TASK_COLUMN
            ).text(),
        )
        self.assertEqual("Task Details", task_dialog.info_group.title())
        self.assertEqual("Task Switcher", switcher.windowTitle())
        self.assertEqual("Skip", welcome.skip_btn.text())
        self.assertEqual("Preview", selector.preview_group.title())
        self.assertEqual("Show Window", tray.show_action.text())

        main_window.cleanup()
        for widget in (task_dialog, switcher, welcome, selector, main_window):
            widget.close()
        tray.hide()


if __name__ == "__main__":
    unittest.main()
