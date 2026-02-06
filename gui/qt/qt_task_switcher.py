"""
PySide6 任务切换器弹窗

大尺寸弹窗、键盘导航、自动超时切换。
"""

import time
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox
)

from core.task_manager import TaskManager, Task, TaskStatus
from utils.dialog_position_manager import get_dialog_position_manager
from utils.config import get_config
from gui.qt.styles import get_dark_theme


class QtTaskSwitcher(QDialog):
    """任务切换器对话框"""

    STATUS_TEXT = {
        "todo": "待办",
        "in_progress": "进行中",
        "blocked": "已阻塞",
        "review": "待审查",
        "completed": "已完成",
        "paused": "已暂停",
    }

    def __init__(self, task_manager: TaskManager):
        super().__init__(None)
        self.task_manager = task_manager
        self._config = get_config()
        self._switcher_config = {}
        self._auto_close_delay = 2.0
        self._window_size = (800, 700)
        self._enabled = True

        self.tasks: List[Task] = []
        self.selected_index = 0
        self._switch_success = False
        self._auto_executed = False
        self._start_time = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_timer_tick)

        self._setup_ui()
        self.setStyleSheet(get_dark_theme())

        self._load_config()
    def _setup_ui(self):
        self.setWindowTitle("任务切换器")
        self.setModal(True)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setWindowOpacity(0.95)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel("任务切换器")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget, 1)

        bottom_row = QHBoxLayout()
        self.countdown_label = QLabel("")
        self.countdown_label.setStyleSheet("color: #FF8C00;")
        bottom_row.addWidget(self.countdown_label)
        bottom_row.addStretch()
        hint = QLabel("↑↓选择 | 回车确认 | 数字键1-9")
        hint.setStyleSheet("color: #808080;")
        bottom_row.addWidget(hint)
        layout.addLayout(bottom_row)

    def show_switcher(self, main_window_position: Optional[Tuple[int, int]] = None) -> bool:
        self._load_config()

        if not self._enabled:
            print("任务切换器功能已禁用")
            return False

        self.tasks = self.task_manager.get_all_tasks()
        if not self.tasks:
            self._show_no_tasks_message()
            return False

        self._build_task_list()
        self._apply_dialog_position(main_window_position)

        self._switch_success = False
        self._auto_executed = False
        self._start_time = time.time()
        self._timer.start()

        try:
            result = self.exec()
        finally:
            self._timer.stop()

        if result == QDialog.Accepted:
            return self._switch_success
        return False

    def _apply_dialog_position(self, main_window_position: Optional[Tuple[int, int]]):
        window_size = self._window_size
        self.resize(*window_size)

        position = get_dialog_position_manager().get_switcher_dialog_position(
            window_size, main_window_position
        )
        self.move(position[0], position[1])

    def _build_task_list(self):
        self.list_widget.clear()

        for idx, task in enumerate(self.tasks):
            status_value = task.status.value if isinstance(task.status, TaskStatus) else task.status
            status_text = self.STATUS_TEXT.get(status_value, status_value)
            window_count = len(task.bound_windows)
            item_text = f"{idx + 1}. {task.name}   [{status_text}]   窗口: {window_count}"
            item = QListWidgetItem(item_text)
            self.list_widget.addItem(item)

        self.selected_index = 0
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_selection_changed(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.selected_index = row
            self._reset_timer()

    def _on_item_double_clicked(self, _item: QListWidgetItem):
        self._execute_selected_task()

    def _reset_timer(self):
        self._start_time = time.time()

    def _on_timer_tick(self):
        if self._auto_executed:
            return

        elapsed = time.time() - self._start_time
        remaining = max(0.0, self._auto_close_delay - elapsed)
        self.countdown_label.setText(f"自动切换: {remaining:.1f}s")

        if remaining <= 0:
            self._auto_executed = True
            self._execute_selected_task(auto=True)

    def _execute_selected_task(self, auto: bool = False):
        if not (0 <= self.selected_index < len(self.tasks)):
            self.reject()
            return

        success = self.task_manager.switch_to_task(self.selected_index)
        self._switch_success = success

        if success:
            self.accept()
        else:
            if not auto:
                QMessageBox.warning(self, "切换失败", "无法切换到所选任务")
            self.reject()

    def _show_no_tasks_message(self):
        QMessageBox.information(self, "任务切换器", "还没有任何任务，请先在主窗口添加任务。")

    def _load_config(self):
        self._switcher_config = self._config.get_task_switcher_config()
        self._auto_close_delay = self._switcher_config.get("auto_close_delay", 2.0)
        window_size = self._switcher_config.get("window_size", [800, 700])
        if isinstance(window_size, (list, tuple)) and len(window_size) == 2:
            self._window_size = (int(window_size[0]), int(window_size[1]))
        else:
            self._window_size = (800, 700)
        self._enabled = self._switcher_config.get("enabled", True)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Escape:
            self.reject()
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected_task()
            return

        if key == Qt.Key_Up:
            row = max(0, self.list_widget.currentRow() - 1)
            self.list_widget.setCurrentRow(row)
            return

        if key == Qt.Key_Down:
            row = min(self.list_widget.count() - 1, self.list_widget.currentRow() + 1)
            self.list_widget.setCurrentRow(row)
            return

        if Qt.Key_1 <= key <= Qt.Key_9:
            index = key - Qt.Key_1
            if index < len(self.tasks):
                self.list_widget.setCurrentRow(index)
                self._execute_selected_task()
            return

        super().keyPressEvent(event)


__all__ = ["QtTaskSwitcher"]
