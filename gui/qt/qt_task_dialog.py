"""
PySide6 任务编辑对话框

用于创建或编辑任务信息，并绑定窗口。
"""

from typing import List, Optional, Dict

from PySide6.QtCore import Qt
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
from gui.qt.styles import get_dark_theme


class QtTaskDialog(QDialog):
    """任务编辑对话框"""

    WINDOW_COLUMNS = ["选择", "窗口标题", "进程", "句柄"]

    STATUS_OPTIONS = [
        ("待办", TaskStatus.TODO),
        ("进行中", TaskStatus.IN_PROGRESS),
        ("已阻塞", TaskStatus.BLOCKED),
        ("待审查", TaskStatus.REVIEW),
        ("已完成", TaskStatus.COMPLETED),
        ("已暂停", TaskStatus.PAUSED),
    ]

    PRIORITY_OPTIONS = [
        ("普通", 0),
        ("低", 1),
        ("中", 2),
        ("高", 3),
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

    def _setup_ui(self):
        self.setWindowTitle("任务")
        self.setModal(True)
        self.resize(640, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        # 任务信息
        info_group = QGroupBox("任务信息")
        info_layout = QFormLayout(info_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("请输入任务名称")
        info_layout.addRow("任务名称:", self.name_input)

        status_row = QHBoxLayout()
        self.status_combo = QComboBox()
        for label, value in self.STATUS_OPTIONS:
            self.status_combo.addItem(label, value)
        status_row.addWidget(self.status_combo)

        self.priority_combo = QComboBox()
        for label, value in self.PRIORITY_OPTIONS:
            self.priority_combo.addItem(label, value)
        status_row.addWidget(QLabel("优先级:"))
        status_row.addWidget(self.priority_combo)
        status_row.addStretch()

        info_layout.addRow("状态:", status_row)

        layout.addWidget(info_group)

        # 窗口绑定
        windows_group = QGroupBox("绑定窗口")
        windows_layout = QVBoxLayout(windows_group)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_row.addWidget(QLabel("🔍 搜索:"))
        self.window_search = QLineEdit()
        self.window_search.setPlaceholderText("输入窗口标题或进程名")
        self.window_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.window_search, 1)

        clear_btn = QPushButton("×")
        clear_btn.setFixedWidth(22)
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)

        refresh_btn = QPushButton("刷新窗口列表")
        refresh_btn.clicked.connect(self._refresh_window_list)
        search_row.addWidget(refresh_btn)

        self.filter_count_label = QLabel("")
        self.filter_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        search_row.addWidget(self.filter_count_label)

        windows_layout.addLayout(search_row)

        self.window_table = QTableWidget(0, len(self.WINDOW_COLUMNS))
        self.window_table.setHorizontalHeaderLabels(self.WINDOW_COLUMNS)
        self.window_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.window_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.window_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.window_table.setAlternatingRowColors(True)
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

        windows_layout.addWidget(QLabel("已选择窗口:"))
        self.windows_list = QListWidget()
        self.windows_list.setFixedHeight(80)
        self.windows_list.itemDoubleClicked.connect(self._on_selected_window_double_clicked)
        windows_layout.addWidget(self.windows_list)

        button_row = QHBoxLayout()
        self.add_window_btn = QPushButton("添加选择")
        self.remove_window_btn = QPushButton("移除选择")
        button_row.addWidget(self.add_window_btn)
        button_row.addWidget(self.remove_window_btn)
        button_row.addStretch()

        self.add_window_btn.clicked.connect(self._add_selected_window)
        self.remove_window_btn.clicked.connect(self._remove_selected_window)

        windows_layout.addLayout(button_row)
        layout.addWidget(windows_group, 1)

        # 操作按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_add_dialog(self) -> bool:
        """显示添加任务对话框"""
        self._editing_task = None
        self._selected_windows = []
        self._selected_hwnds.clear()
        self._reset_fields()
        self.setWindowTitle("添加任务")
        self._apply_dialog_position()
        self._refresh_window_list()
        return self.exec() == QDialog.Accepted

    def show_edit_dialog(self, task: Task) -> bool:
        """显示编辑任务对话框"""
        self._editing_task = task
        self._load_task(task)
        self.setWindowTitle(f"编辑任务 - {task.name}")
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
        self.status_combo.setCurrentIndex(0)
        self.priority_combo.setCurrentIndex(0)
        self.window_search.setText("")
        self._refresh_windows_list()

    def _load_task(self, task: Task):
        self.name_input.setText(task.name)

        # 状态
        status_index = 0
        for idx, (_, status) in enumerate(self.STATUS_OPTIONS):
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
        window_hwnds = [w.hwnd for w in self._selected_windows]

        if not name:
            QMessageBox.warning(self, "提示", "请输入任务名称")
            return

        # 名称重复检查
        for task in self.task_manager.tasks:
            if task.name == name:
                if self._editing_task and task.id == self._editing_task.id:
                    continue
                QMessageBox.warning(self, "提示", f"任务名称 '{name}' 已存在")
                return

        if self._editing_task:
            success = self.task_manager.edit_task(
                self._editing_task.id,
                name=name,
                description=description,
                status=status,
                window_hwnds=window_hwnds,
                priority=priority
            )
            if not success:
                QMessageBox.warning(self, "错误", "任务更新失败")
                return
        else:
            task = self.task_manager.add_task(
                name=name,
                description=description,
                window_hwnds=window_hwnds
            )
            if not task:
                QMessageBox.warning(self, "错误", "任务创建失败")
                return
            self.task_manager.edit_task(
                task.id,
                status=status,
                priority=priority
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
        selected_item = QTableWidgetItem("✓" if window.hwnd in self._selected_hwnds else "")
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
                item.setText("✓" if window.hwnd in self._selected_hwnds else "")

    def _update_filter_count(self):
        total = len(self._filtered_windows)
        selected = len(self._selected_hwnds)
        if self.window_search.text().strip():
            self.filter_count_label.setText(f"已选择 {selected} | 显示 {total}")
        else:
            self.filter_count_label.setText(f"已选择 {selected} | 共 {total}")

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
