"""
PySide6 设置对话框

提供通知、热键与窗口行为等设置。
"""

from typing import List
import os

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QDialogButtonBox, QMessageBox,
    QLineEdit, QPushButton, QFileDialog, QPlainTextEdit, QApplication
)

from core.task_manager import TaskManager
from utils.config import get_config
from utils.hotkey_conflict_detector import get_conflict_detector
from utils.dialog_position_manager import get_dialog_position_manager
from utils.localization import SYSTEM_LANGUAGE, get_localizer, tr
from gui.qt.styles import get_dark_theme


class QtSettingsDialog(QDialog):
    """设置对话框"""

    HERDR_SIDEBAR_CONFIG = """[ui.sidebar.spaces]
rows = [
  [\"state_icon\", \"workspace\"],
  [\"$cs_task\", \"$cs_task_status\"],
  [\"$cs_task_id\"],
  [\"$cs_task_summary\"]
]"""

    def __init__(self, parent, task_manager: TaskManager):
        super().__init__(parent)
        self.task_manager = task_manager
        self.config = get_config()
        self.conflict_detector = get_conflict_detector()

        self._setup_ui()
        self.setStyleSheet(get_dark_theme())

        self._load_settings()
        self._update_hotkey_preview()
        self._update_conflict_status()
        get_localizer().subscribe(self._on_language_changed)

    def _setup_ui(self):
        self.setModal(True)
        self.resize(560, 640)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 语言
        self.language_group = QGroupBox()
        language_layout = QFormLayout(self.language_group)
        self.language_combo = QComboBox()
        self.language_label = QLabel()
        language_layout.addRow(self.language_label, self.language_combo)
        layout.addWidget(self.language_group)

        # 通知设置
        self.notify_group = QGroupBox()
        notify_layout = QFormLayout(self.notify_group)

        self.idle_time_spin = QSpinBox()
        self.idle_time_spin.setRange(1, 1440)
        self.idle_time_label = QLabel()
        notify_layout.addRow(self.idle_time_label, self.idle_time_spin)

        layout.addWidget(self.notify_group)

        # 任务切换器设置
        self.switcher_group = QGroupBox()
        switcher_layout = QVBoxLayout(self.switcher_group)

        self.switcher_enabled = QCheckBox()
        self.switcher_enabled.stateChanged.connect(self._update_switcher_enabled_state)
        switcher_layout.addWidget(self.switcher_enabled)

        modifiers_row = QHBoxLayout()
        self.modifiers_label = QLabel()
        modifiers_row.addWidget(self.modifiers_label)
        self.mod_ctrl = QCheckBox("Ctrl")
        self.mod_alt = QCheckBox("Alt")
        self.mod_shift = QCheckBox("Shift")
        self.mod_win = QCheckBox("Win")
        for cb in (self.mod_ctrl, self.mod_alt, self.mod_shift, self.mod_win):
            cb.stateChanged.connect(self._on_hotkey_changed)
            modifiers_row.addWidget(cb)
        modifiers_row.addStretch()
        switcher_layout.addLayout(modifiers_row)

        key_row = QHBoxLayout()
        self.trigger_key_label = QLabel()
        key_row.addWidget(self.trigger_key_label)
        self.switcher_key = QComboBox()
        self.switcher_key.addItems(["space", "tab", "enter"])
        self.switcher_key.currentTextChanged.connect(self._on_hotkey_changed)
        key_row.addWidget(self.switcher_key)
        key_row.addStretch()
        switcher_layout.addLayout(key_row)

        delay_row = QHBoxLayout()
        self.auto_close_label = QLabel()
        delay_row.addWidget(self.auto_close_label)
        self.auto_close_spin = QDoubleSpinBox()
        self.auto_close_spin.setRange(0.5, 10.0)
        self.auto_close_spin.setSingleStep(0.5)
        delay_row.addWidget(self.auto_close_spin)
        delay_row.addStretch()
        switcher_layout.addLayout(delay_row)

        preview_row = QHBoxLayout()
        self.preview_label = QLabel()
        preview_row.addWidget(self.preview_label)
        self.hotkey_preview = QLabel("-")
        preview_row.addWidget(self.hotkey_preview)
        preview_row.addStretch()
        switcher_layout.addLayout(preview_row)

        conflict_row = QHBoxLayout()
        self.conflict_label = QLabel()
        conflict_row.addWidget(self.conflict_label)
        self.conflict_status = QLabel("-")
        conflict_row.addWidget(self.conflict_status)
        conflict_row.addStretch()
        switcher_layout.addLayout(conflict_row)

        layout.addWidget(self.switcher_group)

        # Herdr 集成设置
        self.herdr_group = QGroupBox()
        herdr_layout = QFormLayout(self.herdr_group)
        herdr_path_row = QHBoxLayout()
        self.herdr_exe_input = QLineEdit()
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self._browse_herdr_exe)
        herdr_path_row.addWidget(self.herdr_exe_input, 1)
        herdr_path_row.addWidget(self.browse_btn)
        self.herdr_path_label = QLabel()
        herdr_layout.addRow(self.herdr_path_label, herdr_path_row)

        self.herdr_monitoring_enabled = QCheckBox()
        self.herdr_monitoring_enabled.stateChanged.connect(self._update_herdr_enabled_state)
        herdr_layout.addRow(self.herdr_monitoring_enabled)

        self.herdr_notify_blocked = QCheckBox()
        self.herdr_notify_done = QCheckBox()
        herdr_layout.addRow(self.herdr_notify_blocked)
        herdr_layout.addRow(self.herdr_notify_done)

        self.herdr_metadata_sync = QCheckBox()
        herdr_layout.addRow(self.herdr_metadata_sync)

        sidebar_row = QVBoxLayout()
        self.herdr_sidebar_config = QPlainTextEdit()
        self.herdr_sidebar_config.setReadOnly(True)
        self.herdr_sidebar_config.setPlainText(self.HERDR_SIDEBAR_CONFIG)
        self.herdr_sidebar_config.setMaximumHeight(92)
        self.copy_sidebar_btn = QPushButton()
        self.copy_sidebar_btn.clicked.connect(self._copy_herdr_sidebar_config)
        sidebar_row.addWidget(self.herdr_sidebar_config)
        sidebar_row.addWidget(self.copy_sidebar_btn)
        self.sidebar_snippet_label = QLabel()
        herdr_layout.addRow(self.sidebar_snippet_label, sidebar_row)
        layout.addWidget(self.herdr_group)

        # 窗口行为设置
        self.window_group = QGroupBox()
        window_layout = QFormLayout(self.window_group)
        self.always_on_top = QCheckBox()
        self.remember_position = QCheckBox()
        window_layout.addRow(self.always_on_top)
        window_layout.addRow(self.remember_position)
        layout.addWidget(self.window_group)

        # 目标设置
        self.productivity_group = QGroupBox()
        productivity_layout = QFormLayout(self.productivity_group)
        self.daily_goal_spin = QSpinBox()
        self.daily_goal_spin.setRange(1, 1440)
        self.daily_goal_label = QLabel()
        productivity_layout.addRow(self.daily_goal_label, self.daily_goal_spin)
        layout.addWidget(self.productivity_group)

        # 按钮
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults
        )
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addWidget(self.buttons)

        self._retranslate_ui()

    def show_settings_dialog(self) -> bool:
        self._apply_dialog_position()
        return self.exec() == QDialog.Accepted

    def _apply_dialog_position(self):
        dialog_size = (self.width(), self.height())
        main_position = None
        if self.parent() is not None:
            try:
                pos = self.parent().pos()
                main_position = (pos.x(), pos.y())
            except Exception:
                main_position = None

        position = get_dialog_position_manager().get_settings_dialog_position(
            dialog_size, main_position
        )
        self.move(position[0], position[1])

    def _load_settings(self):
        monitoring = self.config.get_monitoring_config()
        hotkeys = self.config.get_hotkeys_config()
        switcher_config = self.config.get_task_switcher_config()
        window_config = self.config.get_window_config()
        productivity = self.config.get_productivity_config()
        herdr_config = self.config.get("integrations.herdr", {})

        language_preference = get_localizer().preference
        language_index = self.language_combo.findData(language_preference)
        self.language_combo.setCurrentIndex(max(0, language_index))

        self.idle_time_spin.setValue(monitoring.get("idle_time_warning_minutes", 10))
        self.switcher_enabled.setChecked(hotkeys.get("switcher_enabled", True))

        modifiers = hotkeys.get("switcher_modifiers", ["ctrl", "alt"])
        self.mod_ctrl.setChecked("ctrl" in modifiers)
        self.mod_alt.setChecked("alt" in modifiers)
        self.mod_shift.setChecked("shift" in modifiers)
        self.mod_win.setChecked("win" in modifiers)

        self.switcher_key.setCurrentText(hotkeys.get("switcher_key", "space"))
        self.auto_close_spin.setValue(switcher_config.get("auto_close_delay", 2.0))

        self.always_on_top.setChecked(window_config.get("always_on_top", True))
        self.remember_position.setChecked(window_config.get("remember_position", True))

        self.daily_goal_spin.setValue(productivity.get("daily_goal_minutes", 120))
        self.herdr_exe_input.setText(herdr_config.get("exe_path", ""))
        self.herdr_monitoring_enabled.setChecked(herdr_config.get("monitoring_enabled", True))
        self.herdr_notify_blocked.setChecked(herdr_config.get("notify_on_blocked", True))
        self.herdr_notify_done.setChecked(herdr_config.get("notify_on_done", True))
        self.herdr_metadata_sync.setChecked(herdr_config.get("metadata_sync_enabled", True))

        self._update_switcher_enabled_state()
        self._update_herdr_enabled_state()

    def _restore_defaults(self):
        defaults = self.config.default_config

        self.idle_time_spin.setValue(defaults["monitoring"]["idle_time_warning_minutes"])
        language_index = self.language_combo.findData(defaults["app"]["language"])
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.switcher_enabled.setChecked(defaults["hotkeys"]["switcher_enabled"])
        modifiers = defaults["hotkeys"]["switcher_modifiers"]

        self.mod_ctrl.setChecked("ctrl" in modifiers)
        self.mod_alt.setChecked("alt" in modifiers)
        self.mod_shift.setChecked("shift" in modifiers)
        self.mod_win.setChecked("win" in modifiers)

        self.switcher_key.setCurrentText(defaults["hotkeys"]["switcher_key"])
        self.auto_close_spin.setValue(defaults["task_switcher"]["auto_close_delay"])

        self.always_on_top.setChecked(defaults["window"]["always_on_top"])
        self.remember_position.setChecked(defaults["window"]["remember_position"])

        self.daily_goal_spin.setValue(defaults["productivity"]["daily_goal_minutes"])
        self.herdr_exe_input.setText(defaults["integrations"]["herdr"]["exe_path"])
        herdr_defaults = defaults["integrations"]["herdr"]
        self.herdr_monitoring_enabled.setChecked(herdr_defaults["monitoring_enabled"])
        self.herdr_notify_blocked.setChecked(herdr_defaults["notify_on_blocked"])
        self.herdr_notify_done.setChecked(herdr_defaults["notify_on_done"])
        self.herdr_metadata_sync.setChecked(herdr_defaults["metadata_sync_enabled"])

        self._update_hotkey_preview()
        self._update_conflict_status()
        self._update_switcher_enabled_state()
        self._update_herdr_enabled_state()

    def _update_herdr_enabled_state(self):
        enabled = self.herdr_monitoring_enabled.isChecked()
        self.herdr_notify_blocked.setEnabled(enabled)
        self.herdr_notify_done.setEnabled(enabled)

    def _copy_herdr_sidebar_config(self):
        QApplication.clipboard().setText(self.HERDR_SIDEBAR_CONFIG)

    def _update_switcher_enabled_state(self):
        enabled = self.switcher_enabled.isChecked()
        for widget in (
            self.mod_ctrl, self.mod_alt, self.mod_shift, self.mod_win,
            self.switcher_key, self.auto_close_spin
        ):
            widget.setEnabled(enabled)
        self._update_hotkey_preview()
        self._update_conflict_status()

    def _on_hotkey_changed(self):
        self._update_hotkey_preview()
        self._update_conflict_status()

    def _get_modifiers(self) -> List[str]:
        modifiers = []
        if self.mod_ctrl.isChecked():
            modifiers.append("ctrl")
        if self.mod_alt.isChecked():
            modifiers.append("alt")
        if self.mod_shift.isChecked():
            modifiers.append("shift")
        if self.mod_win.isChecked():
            modifiers.append("win")
        return modifiers

    def _format_hotkey_preview(self, modifiers: List[str], key: str) -> str:
        if not modifiers or not key:
            return tr("settings.hotkey_unset")

        display = []
        mapping = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
        for mod in modifiers:
            display.append(mapping.get(mod, mod))
        display.append(key.title())
        return "+".join(display)

    def _update_hotkey_preview(self):
        modifiers = self._get_modifiers()
        key = self.switcher_key.currentText()
        self.hotkey_preview.setText(self._format_hotkey_preview(modifiers, key))

    def _update_conflict_status(self):
        if not self.switcher_enabled.isChecked():
            self.conflict_status.setText(tr("settings.conflict_disabled"))
            self.conflict_status.setStyleSheet("color: #808080;")
            return

        modifiers = self._get_modifiers()
        result = self.conflict_detector.check_hotkey_conflicts(modifiers)

        if result["severity"] == "error":
            text = tr("settings.conflict_system")
            color = "#D13438"
        elif result["severity"] == "warning":
            text = tr("settings.conflict_possible")
            color = "#FF8C00"
        else:
            if result.get("warnings"):
                text = f"⚠️ {result['warnings'][0]}"
                color = "#FF8C00"
            else:
                text = tr("settings.conflict_none")
                color = "#107C10"

        self.conflict_status.setText(text)
        self.conflict_status.setStyleSheet(f"color: {color};")

    def _on_save(self):
        idle_time = self.idle_time_spin.value()
        auto_close_delay = self.auto_close_spin.value()

        switcher_enabled = self.switcher_enabled.isChecked()
        modifiers = self._get_modifiers()
        switcher_key = self.switcher_key.currentText()

        if switcher_enabled and not modifiers:
            QMessageBox.warning(
                self,
                tr("settings.error_title"),
                tr("settings.modifier_required"),
            )
            return

        if switcher_enabled:
            conflict = self.conflict_detector.check_hotkey_conflicts(modifiers)
            if conflict["severity"] == "error":
                QMessageBox.warning(
                    self,
                    tr("settings.conflict_title"),
                    tr("settings.system_conflict_message"),
                )
                return
            if conflict["severity"] == "warning":
                conflicts_text = "\n".join(conflict.get("conflicts", []))
                message = tr(
                    "settings.potential_conflict_message",
                    conflicts=conflicts_text,
                )
                result = QMessageBox.question(
                    self, tr("settings.conflict_title"), message
                )
                if result != QMessageBox.Yes:
                    return

        # 更新配置
        monitoring = self.config.get_monitoring_config()
        monitoring["idle_time_warning_minutes"] = idle_time

        hotkeys = self.config.get_hotkeys_config()
        hotkeys["switcher_enabled"] = switcher_enabled
        hotkeys["switcher_modifiers"] = modifiers
        hotkeys["switcher_key"] = switcher_key

        switcher_config = self.config.get_task_switcher_config()
        switcher_config["auto_close_delay"] = auto_close_delay

        window_config = self.config.get_window_config()
        window_config["always_on_top"] = self.always_on_top.isChecked()
        window_config["remember_position"] = self.remember_position.isChecked()

        productivity = self.config.get_productivity_config()
        productivity["daily_goal_minutes"] = self.daily_goal_spin.value()

        language_preference = self.language_combo.currentData() or SYSTEM_LANGUAGE

        herdr_path = self.herdr_exe_input.text().strip()
        if herdr_path and not os.path.isfile(herdr_path):
            QMessageBox.warning(
                self,
                tr("settings.error_title"),
                tr("settings.herdr_path_invalid"),
            )
            return

        self.config.config.setdefault("app", {})["language"] = language_preference

        herdr_config = self.config.get("integrations.herdr", {})
        herdr_config["exe_path"] = herdr_path
        herdr_config["monitoring_enabled"] = self.herdr_monitoring_enabled.isChecked()
        herdr_config["notify_on_blocked"] = self.herdr_notify_blocked.isChecked()
        herdr_config["notify_on_done"] = self.herdr_notify_done.isChecked()
        herdr_config["metadata_sync_enabled"] = self.herdr_metadata_sync.isChecked()

        if not self.config.save():
            QMessageBox.warning(
                self,
                tr("settings.save_failed_title"),
                tr("settings.save_failed_message"),
            )
            return

        get_localizer().set_language(language_preference, QLocale.system().name())
        self._reload_system_components()
        self.accept()

    def _reload_system_components(self):
        try:
            hotkey_manager = None
            if hasattr(self.task_manager, "hotkey_manager"):
                hotkey_manager = self.task_manager.hotkey_manager

            if not hotkey_manager:
                try:
                    import main
                    if hasattr(main, "hotkey_manager"):
                        hotkey_manager = main.hotkey_manager
                except Exception:
                    hotkey_manager = None

            if hotkey_manager:
                hotkey_manager.reload_config()
                print("✓ 热键管理器已重载")
            else:
                print("⚠️ 未找到热键管理器，跳过重载")

        except Exception as exc:
            print(f"⚠️ 重载系统组件时出错: {exc}")

    def _browse_herdr_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.select_herdr"),
            "",
            tr("common.file_filters.executables"),
        )
        if path:
            self.herdr_exe_input.setText(path)

    def _on_language_changed(self, _language: str) -> None:
        self._retranslate_ui()
        self._update_hotkey_preview()
        self._update_conflict_status()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings.title"))
        self.language_group.setTitle(tr("settings.language_group"))
        self.language_label.setText(tr("settings.display_language"))

        selected_language = self.language_combo.currentData()
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(tr("language.follow_system"), SYSTEM_LANGUAGE)
        for language in get_localizer().available_languages():
            self.language_combo.addItem(language.native_name, language.code)
        selected_index = self.language_combo.findData(
            selected_language or get_localizer().preference
        )
        self.language_combo.setCurrentIndex(max(0, selected_index))
        self.language_combo.blockSignals(False)

        self.notify_group.setTitle(tr("settings.notifications_group"))
        self.idle_time_label.setText(tr("settings.idle_reminder"))
        self.idle_time_spin.setSuffix(tr("settings.minutes_suffix"))
        self.switcher_group.setTitle(tr("settings.switcher_group"))
        self.switcher_enabled.setText(tr("settings.enable_switcher"))
        self.modifiers_label.setText(tr("settings.modifiers"))
        self.trigger_key_label.setText(tr("settings.trigger_key"))
        self.auto_close_label.setText(tr("settings.auto_close_delay"))
        self.auto_close_spin.setSuffix(tr("settings.seconds_suffix"))
        self.preview_label.setText(tr("settings.current_combination"))
        self.conflict_label.setText(tr("settings.conflict_check"))
        self.herdr_group.setTitle(tr("settings.herdr_group"))
        self.herdr_exe_input.setPlaceholderText(tr("settings.herdr_path_placeholder"))
        self.browse_btn.setText(tr("settings.browse"))
        self.herdr_path_label.setText(tr("settings.herdr_path"))
        self.herdr_monitoring_enabled.setText(tr("settings.monitor_agents"))
        self.herdr_notify_blocked.setText(tr("settings.notify_blocked"))
        self.herdr_notify_done.setText(tr("settings.notify_done"))
        self.herdr_metadata_sync.setText(tr("settings.sync_metadata"))
        self.herdr_sidebar_config.setToolTip(tr("settings.sidebar_tooltip"))
        self.copy_sidebar_btn.setText(tr("settings.copy_sidebar"))
        self.sidebar_snippet_label.setText(tr("settings.sidebar_snippet"))
        self.window_group.setTitle(tr("settings.window_group"))
        self.always_on_top.setText(tr("settings.always_on_top"))
        self.remember_position.setText(tr("settings.remember_position"))
        self.productivity_group.setTitle(tr("settings.focus_group"))
        self.daily_goal_label.setText(tr("settings.daily_goal"))
        self.daily_goal_spin.setSuffix(tr("settings.minutes_suffix"))
        self.buttons.button(QDialogButtonBox.Ok).setText(tr("common.buttons.ok"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("common.buttons.cancel"))
        self.buttons.button(QDialogButtonBox.RestoreDefaults).setText(
            tr("common.buttons.restore_defaults")
        )


__all__ = ["QtSettingsDialog"]
