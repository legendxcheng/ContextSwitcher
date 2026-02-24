"""
PySide6 设置对话框

提供通知、热键与窗口行为等设置。
"""

from typing import List
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout, QDialogButtonBox, QMessageBox,
    QLineEdit, QPushButton, QFileDialog
)

from core.task_manager import TaskManager
from utils.config import get_config
from utils.hotkey_conflict_detector import get_conflict_detector
from utils.dialog_position_manager import get_dialog_position_manager
from gui.qt.styles import get_dark_theme


class QtSettingsDialog(QDialog):
    """设置对话框"""

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

    def _setup_ui(self):
        self.setWindowTitle("应用设置")
        self.setModal(True)
        self.resize(520, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 通知设置
        notify_group = QGroupBox("通知设置")
        notify_layout = QFormLayout(notify_group)

        self.idle_time_spin = QSpinBox()
        self.idle_time_spin.setRange(1, 1440)
        self.idle_time_spin.setSuffix(" 分钟")
        notify_layout.addRow("待机提醒时间:", self.idle_time_spin)

        layout.addWidget(notify_group)

        # 任务切换器设置
        switcher_group = QGroupBox("任务切换器设置")
        switcher_layout = QVBoxLayout(switcher_group)

        self.switcher_enabled = QCheckBox("启用任务切换器")
        self.switcher_enabled.stateChanged.connect(self._update_switcher_enabled_state)
        switcher_layout.addWidget(self.switcher_enabled)

        modifiers_row = QHBoxLayout()
        modifiers_row.addWidget(QLabel("修饰键:"))
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
        key_row.addWidget(QLabel("触发键:"))
        self.switcher_key = QComboBox()
        self.switcher_key.addItems(["space", "tab", "enter"])
        self.switcher_key.currentTextChanged.connect(self._on_hotkey_changed)
        key_row.addWidget(self.switcher_key)
        key_row.addStretch()
        switcher_layout.addLayout(key_row)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("自动关闭延迟:"))
        self.auto_close_spin = QDoubleSpinBox()
        self.auto_close_spin.setRange(0.5, 10.0)
        self.auto_close_spin.setSingleStep(0.5)
        self.auto_close_spin.setSuffix(" 秒")
        delay_row.addWidget(self.auto_close_spin)
        delay_row.addStretch()
        switcher_layout.addLayout(delay_row)

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("当前组合:"))
        self.hotkey_preview = QLabel("-")
        preview_row.addWidget(self.hotkey_preview)
        preview_row.addStretch()
        switcher_layout.addLayout(preview_row)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("冲突检测:"))
        self.conflict_status = QLabel("-")
        conflict_row.addWidget(self.conflict_status)
        conflict_row.addStretch()
        switcher_layout.addLayout(conflict_row)

        layout.addWidget(switcher_group)

        # Wave 集成设置
        wave_group = QGroupBox("Wave 集成")
        wave_layout = QFormLayout(wave_group)
        wave_path_row = QHBoxLayout()
        self.wave_exe_input = QLineEdit()
        self.wave_exe_input.setPlaceholderText("Wave.exe 完整路径")
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_wave_exe)
        wave_path_row.addWidget(self.wave_exe_input, 1)
        wave_path_row.addWidget(browse_btn)
        wave_layout.addRow("Wave.exe 路径:", wave_path_row)
        layout.addWidget(wave_group)

        # 窗口行为设置
        window_group = QGroupBox("窗口行为")
        window_layout = QFormLayout(window_group)
        self.always_on_top = QCheckBox("始终置顶")
        self.remember_position = QCheckBox("记住窗口位置")
        window_layout.addRow(self.always_on_top)
        window_layout.addRow(self.remember_position)
        layout.addWidget(window_group)

        # 目标设置
        productivity_group = QGroupBox("专注目标")
        productivity_layout = QFormLayout(productivity_group)
        self.daily_goal_spin = QSpinBox()
        self.daily_goal_spin.setRange(1, 1440)
        self.daily_goal_spin.setSuffix(" 分钟")
        productivity_layout.addRow("每日目标:", self.daily_goal_spin)
        layout.addWidget(productivity_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)
        layout.addWidget(buttons)

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
        wave_config = self.config.get("integrations.wave", {})

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
        self.wave_exe_input.setText(wave_config.get("exe_path", ""))

        self._update_switcher_enabled_state()

    def _restore_defaults(self):
        defaults = self.config.default_config

        self.idle_time_spin.setValue(defaults["monitoring"]["idle_time_warning_minutes"])
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
        self.wave_exe_input.setText(defaults["integrations"]["wave"]["exe_path"])

        self._update_hotkey_preview()
        self._update_conflict_status()
        self._update_switcher_enabled_state()

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
            return "未设置"

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
            self.conflict_status.setText("已禁用")
            self.conflict_status.setStyleSheet("color: #808080;")
            return

        modifiers = self._get_modifiers()
        result = self.conflict_detector.check_hotkey_conflicts(modifiers)

        if result["severity"] == "error":
            text = "❌ 系统冲突，无法使用"
            color = "#D13438"
        elif result["severity"] == "warning":
            text = "⚠️ 存在潜在冲突"
            color = "#FF8C00"
        else:
            if result.get("warnings"):
                text = f"⚠️ {result['warnings'][0]}"
                color = "#FF8C00"
            else:
                text = "✅ 无冲突"
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
            QMessageBox.warning(self, "设置错误", "启用任务切换器时，至少需要选择一个修饰键")
            return

        if switcher_enabled:
            conflict = self.conflict_detector.check_hotkey_conflicts(modifiers)
            if conflict["severity"] == "error":
                QMessageBox.warning(self, "快捷键冲突", "检测到系统级冲突，请更换修饰键")
                return
            if conflict["severity"] == "warning":
                conflicts_text = "\n".join(conflict.get("conflicts", []))
                message = f"检测到潜在冲突:\n{conflicts_text}\n\n是否仍要保存?"
                result = QMessageBox.question(self, "快捷键冲突", message)
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

        wave_path = self.wave_exe_input.text().strip()
        if wave_path and not os.path.isfile(wave_path):
            QMessageBox.warning(self, "设置错误", "Wave.exe 路径无效，请检查后再保存")
            return

        wave_config = self.config.get("integrations.wave", {})
        wave_config["exe_path"] = wave_path

        if not self.config.save():
            QMessageBox.warning(self, "保存失败", "无法保存配置文件")
            return

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

    def _browse_wave_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Wave.exe",
            "",
            "Wave.exe (Wave.exe);;可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if path:
            self.wave_exe_input.setText(path)


__all__ = ["QtSettingsDialog"]
