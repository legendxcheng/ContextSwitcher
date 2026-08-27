"""
PySide6 任务编辑对话框

用于创建或编辑任务信息，并绑定窗口。
"""

from typing import List, Optional, Dict

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QPushButton, QDialogButtonBox,
    QGroupBox, QFormLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)

from core.task_manager import TaskManager, Task, TaskStatus
from core.window_manager import WindowInfo
from utils.search_helper import SearchHelper
from utils.window_priority import WindowPriorityManager
from utils.dialog_position_manager import get_dialog_position_manager
from utils.localization import get_localizer, tr
from gui.qt.styles import get_dark_theme, get_icon


class QtTaskDialog(QDialog):
    """任务编辑对话框"""

    STATUS_OPTIONS = [
        TaskStatus.TODO,
        TaskStatus.IN_PROGRESS,
        TaskStatus.BLOCKED,
        TaskStatus.REVIEW,
        TaskStatus.COMPLETED,
        TaskStatus.PAUSED,
    ]

    PRIORITY_OPTIONS = [
        ("normal", 0),
        ("low", 1),
        ("medium", 2),
        ("high", 3),
    ]

    def __init__(self, parent, task_manager: TaskManager):
        super().__init__(parent)
        self.task_manager = task_manager
        self.window_manager = task_manager.window_manager
        self.search_helper = SearchHelper()
        self.priority_manager = WindowPriorityManager()
        self._editing_task: Optional[Task] = None
        self._selected_windows: List[WindowInfo] = []
        self._selected_hwnds: set[int] = set()
        self._all_windows: List[WindowInfo] = []
        self._filtered_windows: List[WindowInfo] = []
        self._search_results: Dict[int, object] = {}

        self._setup_ui()
        self.setStyleSheet(get_dark_theme())
        get_localizer().subscribe(self._on_language_changed)

    def _setup_ui(self):
        self.setModal(True)
        self.resize(640, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        # 任务信息
        self.info_group = QGroupBox()
        info_layout = QFormLayout(self.info_group)

        self.name_input = QLineEdit()
        self.name_label = QLabel()
        info_layout.addRow(self.name_label, self.name_input)

        self.herdr_workspace_input = QLineEdit()
        self.workspace_label = QLabel()
        info_layout.addRow(self.workspace_label, self.herdr_workspace_input)

        status_row = QHBoxLayout()
        self.status_combo = QComboBox()
        for value in self.STATUS_OPTIONS:
            self.status_combo.addItem("", value)
        status_row.addWidget(self.status_combo)

        self.priority_combo = QComboBox()
        for _, value in self.PRIORITY_OPTIONS:
            self.priority_combo.addItem("", value)
        self.priority_label = QLabel()
        status_row.addWidget(self.priority_label)
        status_row.addWidget(self.priority_combo)
        status_row.addStretch()

        self.status_label = QLabel()
        info_layout.addRow(self.status_label, status_row)

        layout.addWidget(self.info_group)

        # 窗口绑定
        self.windows_group = QGroupBox()
        windows_layout = QVBoxLayout(self.windows_group)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self.search_label = QLabel()
        search_row.addWidget(self.search_label)
        self.window_search = QLineEdit()
        self.window_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.window_search, 1)

        clear_btn = QPushButton()
        clear_btn.setFixedWidth(22)
        clear_btn.setIcon(get_icon("close"))
        clear_btn.setIconSize(QSize(11, 11))
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)

        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self._refresh_window_list)
        search_row.addWidget(self.refresh_btn)

        self.filter_count_label = QLabel("")
        self.filter_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        search_row.addWidget(self.filter_count_label)

        windows_layout.addLayout(search_row)

        self.window_table = QTableWidget(0, 4)
        self.window_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.window_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.window_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.window_table.setAlternatingRowColors(True)
        self.window_table.setIconSize(QSize(12, 12))
        self.window_table.itemDoubleClicked.connect(self._on_window_double_clicked)
        self.window_table.verticalHeader().setDefaultSectionSize(20)
        self.window_table.verticalHeader().setMinimumSectionSize(18)

        header = self.window_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setFixedHeight(20)

        windows_layout.addWidget(self.window_table, 1)

        self.selected_windows_label = QLabel()
        windows_layout.addWidget(self.selected_windows_label)
        self.windows_list = QListWidget()
        self.windows_list.setFixedHeight(80)
        self.windows_list.itemDoubleClicked.connect(self._on_selected_window_double_clicked)
        windows_layout.addWidget(self.windows_list)

        button_row = QHBoxLayout()
        self.add_window_btn = QPushButton()
        self.remove_window_btn = QPushButton()
        button_row.addWidget(self.add_window_btn)
        button_row.addWidget(self.remove_window_btn)
        button_row.addStretch()

        self.add_window_btn.clicked.connect(self._add_selected_window)
        self.remove_window_btn.clicked.connect(self._remove_selected_window)

        windows_layout.addLayout(button_row)
        layout.addWidget(self.windows_group, 1)

        # 操作按钮
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._retranslate_ui()

    def show_add_dialog(self) -> bool:
        """显示添加任务对话框"""
        self._editing_task = None
        self._selected_windows = []
        self._selected_hwnds.clear()
        self._reset_fields()
        self.setWindowTitle(tr("task_dialog.add_title"))
        self._apply_dialog_position()
        self._refresh_window_list()
        return self.exec() == QDialog.Accepted

    def show_edit_dialog(self, task: Task) -> bool:
        """显示编辑任务对话框"""
        self._editing_task = task
        self._load_task(task)
        self.setWindowTitle(tr("task_dialog.edit_title", task=task.name))
        self._apply_dialog_position()
        self._refresh_window_list()
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

        position = get_dialog_position_manager().get_task_dialog_position(
            dialog_size, main_position
        )
        self.move(position[0], position[1])

    def _reset_fields(self):
        self.name_input.setText("")
        self.herdr_workspace_input.setText("")
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.window_search.setText("")
        self._refresh_windows_list()

    def _load_task(self, task: Task):
        self.name_input.setText(task.name)
        self.herdr_workspace_input.setText(getattr(task, "herdr_workspace", "") or "")

        # 状态
        status_index = 0
        for idx, status in enumerate(self.STATUS_OPTIONS):
            if status == task.status:
                status_index = idx
                break
        self.status_combo.setCurrentIndex(status_index)

        # 优先级
        priority_index = 0
        for idx, (_, value) in enumerate(self.PRIORITY_OPTIONS):
            if value == getattr(task, "priority", 0):
                priority_index = idx
                break
        self.priority_combo.setCurrentIndex(priority_index)

        # 已绑定窗口
        selected_windows = []
        for bound_window in task.bound_windows:
            if bound_window.is_valid:
                info = self.task_manager.window_manager.get_window_info(bound_window.hwnd)
                if info:
                    selected_windows.append(info)
        self._selected_windows = selected_windows
        self._selected_hwnds = {w.hwnd for w in selected_windows}
        self._refresh_windows_list()

    def _refresh_windows_list(self):
        self.windows_list.clear()
        for window in self._selected_windows:
            self.windows_list.addItem(f"{window.title} ({window.process_name})")
        self._update_table_selection_marks()

    def _add_selected_window(self):
        row = self.window_table.currentRow()
        if row < 0 or row >= len(self._filtered_windows):
            return
        window = self._filtered_windows[row]
        if window.hwnd in self._selected_hwnds:
            return
        self._selected_windows.append(window)
        self._selected_hwnds.add(window.hwnd)
        self._refresh_windows_list()

    def _remove_selected_window(self):
        current_row = self.windows_list.currentRow()
        self._remove_selected_window_at(current_row)

    def _on_selected_window_double_clicked(self, item):
        row = self.windows_list.row(item)
        self._remove_selected_window_at(row)

    def _remove_selected_window_at(self, row: int):
        if row < 0:
            return
        if 0 <= row < len(self._selected_windows):
            removed = self._selected_windows.pop(row)
            self._selected_hwnds.discard(removed.hwnd)
        self._refresh_windows_list()

    def _on_save(self):
        name = self.name_input.text().strip()
        if self._editing_task:
            description = self._editing_task.description or ""
        else:
            description = ""
        status = self.status_combo.currentData()
        priority = self.priority_combo.currentData()
        herdr_workspace = self.herdr_workspace_input.text().strip()
        window_hwnds = [w.hwnd for w in self._selected_windows]

        if not name:
            QMessageBox.warning(
                self,
                tr("task_dialog.prompt_title"),
                tr("task_dialog.name_required"),
            )
            return

        # 名称重复检查
        for task in self.task_manager.tasks:
            if task.name == name:
                if self._editing_task and task.id == self._editing_task.id:
                    continue
                QMessageBox.warning(
                    self,
                    tr("task_dialog.prompt_title"),
                    tr("task_dialog.name_exists", name=name),
                )
                return

        if self._editing_task:
            success = self.task_manager.edit_task(
                self._editing_task.id,
                name=name,
                description=description,
                status=status,
                window_hwnds=window_hwnds,
                priority=priority,
                herdr_workspace=herdr_workspace
            )
            if not success:
                QMessageBox.warning(
                    self,
                    tr("task_dialog.error_title"),
                    tr("task_dialog.update_failed"),
                )
                return
        else:
            task = self.task_manager.add_task(
                name=name,
                description=description,
                window_hwnds=window_hwnds
            )
            if not task:
                QMessageBox.warning(
                    self,
                    tr("task_dialog.error_title"),
                    tr("task_dialog.create_failed"),
                )
                return
            self.task_manager.edit_task(
                task.id,
                status=status,
                priority=priority,
                herdr_workspace=herdr_workspace
            )

        self.accept()

    def _on_search_changed(self, _text: str):
        self._apply_filter_and_sort()

    def _clear_search(self):
        self.window_search.setText("")
        self._apply_filter_and_sort()

    def _refresh_window_list(self):
        try:
            self.window_manager.invalidate_cache()
            self._all_windows = self.window_manager.enumerate_windows()
            self._apply_filter_and_sort()
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")

    def _apply_filter_and_sort(self):
        query = self.window_search.text().strip()
        if query:
            search_results = self.search_helper.search_windows(self._all_windows, query)
            self._search_results = {result.item.hwnd: result for result in search_results}
            filtered = [result.item for result in search_results]
        else:
            self._search_results = {}
            filtered = list(self._all_windows)

        try:
            active_info = self.window_manager.get_active_windows_info()
            priorities = self.priority_manager.calculate_window_priorities(
                filtered, active_info, self._search_results
            )
            self._filtered_windows = [priority.window for priority in priorities]
        except Exception:
            self._filtered_windows = filtered

        self._populate_table()

    def _populate_table(self):
        self.window_table.setRowCount(len(self._filtered_windows))
        for row, window in enumerate(self._filtered_windows):
            self._set_table_row(row, window)
        self._update_table_selection_marks()
        self._update_filter_count()

    def _set_table_row(self, row: int, window: WindowInfo):
        selected_item = QTableWidgetItem()
        if window.hwnd in self._selected_hwnds:
            selected_item.setIcon(get_icon("check"))
        selected_item.setTextAlignment(Qt.AlignCenter)
        selected_item.setData(Qt.UserRole, window.hwnd)
        self.window_table.setItem(row, 0, selected_item)

        title_item = QTableWidgetItem(window.title)
        self.window_table.setItem(row, 1, title_item)

        process_item = QTableWidgetItem(window.process_name)
        self.window_table.setItem(row, 2, process_item)

        hwnd_item = QTableWidgetItem(str(window.hwnd))
        hwnd_item.setTextAlignment(Qt.AlignCenter)
        self.window_table.setItem(row, 3, hwnd_item)

    def _update_table_selection_marks(self):
        for row, window in enumerate(self._filtered_windows):
            item = self.window_table.item(row, 0)
            if item:
                item.setText("")
                item.setIcon(
                    get_icon("check") if window.hwnd in self._selected_hwnds else QIcon()
                )

    def _update_filter_count(self):
        total = len(self._filtered_windows)
        selected = len(self._selected_hwnds)
        if self.window_search.text().strip():
            self.filter_count_label.setText(
                tr("common.counts.selected_visible", selected=selected, total=total)
            )
        else:
            self.filter_count_label.setText(
                tr("common.counts.selected_total", selected=selected, total=total)
            )

    def _on_language_changed(self, _language: str) -> None:
        self._retranslate_ui()
        self._update_filter_count()

    def _retranslate_ui(self) -> None:
        if self._editing_task is None:
            self.setWindowTitle(tr("task_dialog.title"))
        else:
            self.setWindowTitle(
                tr("task_dialog.edit_title", task=self._editing_task.name)
            )
        self.info_group.setTitle(tr("task_dialog.info_group"))
        self.name_input.setPlaceholderText(tr("task_dialog.name_placeholder"))
        self.name_label.setText(tr("task_dialog.name_label"))
        self.herdr_workspace_input.setPlaceholderText(
            tr("task_dialog.workspace_placeholder")
        )
        self.workspace_label.setText(tr("task_dialog.workspace_label"))
        self.status_label.setText(tr("common.labels.status"))
        self.priority_label.setText(tr("common.labels.priority"))
        for index, status in enumerate(self.STATUS_OPTIONS):
            self.status_combo.setItemText(index, tr(f"status.{status.value}"))
        for index, (key, _) in enumerate(self.PRIORITY_OPTIONS):
            self.priority_combo.setItemText(index, tr(f"priority.{key}"))
        self.windows_group.setTitle(tr("task_dialog.windows_group"))
        self.search_label.setText(tr("common.labels.search"))
        self.window_search.setPlaceholderText(
            tr("task_dialog.window_search_placeholder")
        )
        self.refresh_btn.setText(tr("task_dialog.refresh_windows"))
        self.window_table.setHorizontalHeaderLabels([
            tr("task_dialog.columns.select"),
            tr("task_dialog.columns.title"),
            tr("task_dialog.columns.process"),
            tr("task_dialog.columns.handle"),
        ])
        self.selected_windows_label.setText(tr("common.labels.selected_windows"))
        self.add_window_btn.setText(tr("task_dialog.add_selection"))
        self.remove_window_btn.setText(tr("task_dialog.remove_selection"))
        self.buttons.button(QDialogButtonBox.Save).setText(tr("common.buttons.save"))
        self.buttons.button(QDialogButtonBox.Cancel).setText(tr("common.buttons.cancel"))

    def _on_window_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self._filtered_windows):
            window = self._filtered_windows[row]
            if window.hwnd in self._selected_hwnds:
                return
            self._selected_windows.append(window)
            self._selected_hwnds.add(window.hwnd)
            self._refresh_windows_list()


__all__ = ["QtTaskDialog"]
