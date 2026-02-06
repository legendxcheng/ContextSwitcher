"""
PySide6 窗口选择器

提供窗口选择功能：
- 刷新窗口列表
- 多选支持
- 实时预览选中窗口
- Explorer 路径显示
"""

from typing import List, Optional, Set, Dict

from PySide6.QtCore import Qt, QTimer, QItemSelectionModel
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialogButtonBox, QGroupBox, QFormLayout
)

from core.window_manager import WindowManager, WindowInfo
from core.explorer_helper import ExplorerHelper
from utils.search_helper import SearchHelper
from utils.window_priority import WindowPriorityManager
from utils.dialog_position_manager import get_dialog_position_manager
from gui.qt.styles import get_dark_theme


class QtWindowSelector(QDialog):
    """PySide6 窗口选择器"""

    COLUMN_HEADERS = ["选择", "窗口标题", "进程", "路径", "句柄"]

    def __init__(self, window_manager: WindowManager, parent=None):
        super().__init__(parent)
        self.window_manager = window_manager
        self.explorer_helper = ExplorerHelper()
        self.search_helper = SearchHelper()
        self.priority_manager = WindowPriorityManager()

        self._multiple = True
        self._selected_hwnds: Set[int] = set()
        self._all_windows: List[WindowInfo] = []
        self._filtered_windows: List[WindowInfo] = []
        self._search_results: Dict[int, object] = {}
        self._path_cache: Dict[int, str] = {}

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._refresh_window_list)

        self._setup_ui()
        self.setStyleSheet(get_dark_theme())

    def _setup_ui(self):
        self.setWindowTitle("选择窗口")
        self.setModal(True)
        self.resize(900, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 搜索与控制行
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 搜索:"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入窗口标题或进程名")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_input, 1)

        clear_btn = QPushButton("×")
        clear_btn.setFixedWidth(26)
        clear_btn.clicked.connect(self._clear_search)
        search_row.addWidget(clear_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_window_list)
        search_row.addWidget(refresh_btn)

        self.count_label = QLabel("")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        search_row.addWidget(self.count_label)

        layout.addLayout(search_row)

        # 窗口表格
        self.table = QTableWidget(0, len(self.COLUMN_HEADERS))
        self.table.setHorizontalHeaderLabels(self.COLUMN_HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        layout.addWidget(self.table, 1)

        # 预览区域
        preview_group = QGroupBox("预览")
        preview_layout = QFormLayout(preview_group)
        self.preview_title = QLabel("-")
        self.preview_process = QLabel("-")
        self.preview_hwnd = QLabel("-")
        self.preview_path = QLabel("-")
        self.preview_path.setWordWrap(True)

        preview_layout.addRow("标题:", self.preview_title)
        preview_layout.addRow("进程:", self.preview_process)
        preview_layout.addRow("句柄:", self.preview_hwnd)
        preview_layout.addRow("Explorer路径:", self.preview_path)
        layout.addWidget(preview_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_selector_dialog(
        self,
        parent=None,
        title: str = "选择窗口",
        multiple: bool = True,
        pre_selected: Optional[List[int]] = None
    ) -> Optional[List[WindowInfo]]:
        """显示窗口选择对话框"""
        if parent is not None:
            self.setParent(parent)

        self.setWindowTitle(title)
        self._multiple = multiple
        self.table.setSelectionMode(
            QAbstractItemView.ExtendedSelection if multiple else QAbstractItemView.SingleSelection
        )

        self._selected_hwnds = set(pre_selected or [])

        # 定位
        self._apply_dialog_position(parent)

        # 初次刷新
        self._refresh_window_list()

        # 自动刷新
        self._refresh_timer.start()
        try:
            result = self.exec()
        finally:
            self._refresh_timer.stop()

        if result == QDialog.Accepted:
            return self._get_selected_window_infos()

        return None

    def _apply_dialog_position(self, parent):
        dialog_size = (self.width(), self.height())
        main_position = None
        if parent is not None:
            try:
                pos = parent.pos()
                main_position = (pos.x(), pos.y())
            except Exception:
                main_position = None

        position = get_dialog_position_manager().get_selector_dialog_position(
            dialog_size, main_position
        )
        self.move(position[0], position[1])

    def _refresh_window_list(self):
        try:
            self.window_manager.invalidate_cache()
            self._all_windows = self.window_manager.enumerate_windows()
            self._apply_filter_and_sort()
        except Exception as exc:
            print(f"刷新窗口列表失败: {exc}")

    def _apply_filter_and_sort(self):
        query = self.search_input.text().strip()

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
        self.table.setRowCount(len(self._filtered_windows))

        for row, window in enumerate(self._filtered_windows):
            selected = window.hwnd in self._selected_hwnds
            self._set_table_row(row, window, selected)

        self._apply_selection_to_table()
        self._update_count_label()

    def _set_table_row(self, row: int, window: WindowInfo, selected: bool):
        select_item = QTableWidgetItem("✓" if selected else "")
        select_item.setTextAlignment(Qt.AlignCenter)
        select_item.setData(Qt.UserRole, window.hwnd)
        self.table.setItem(row, 0, select_item)

        title_item = QTableWidgetItem(window.title)
        title_item.setData(Qt.UserRole, window.hwnd)
        self.table.setItem(row, 1, title_item)

        process_item = QTableWidgetItem(window.process_name)
        self.table.setItem(row, 2, process_item)

        path_text = self._get_explorer_path(window)
        path_item = QTableWidgetItem(path_text)
        self.table.setItem(row, 3, path_item)

        hwnd_item = QTableWidgetItem(str(window.hwnd))
        hwnd_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, hwnd_item)

    def _apply_selection_to_table(self):
        if not self.table.selectionModel():
            return

        self.table.blockSignals(True)
        self.table.selectionModel().clearSelection()

        for row, window in enumerate(self._filtered_windows):
            if window.hwnd in self._selected_hwnds:
                index = self.table.model().index(row, 0)
                self.table.selectionModel().select(
                    index, QItemSelectionModel.Select | QItemSelectionModel.Rows
                )

        self.table.blockSignals(False)

    def _on_search_changed(self, text: str):
        if not self._all_windows:
            self._refresh_window_list()
        else:
            self._apply_filter_and_sort()

    def _clear_search(self):
        self.search_input.setText("")
        self._apply_filter_and_sort()

    def _on_selection_changed(self):
        if not self.table.selectionModel():
            return

        selected_rows = self.table.selectionModel().selectedRows()
        selected_row_indexes = {index.row() for index in selected_rows}

        visible_hwnds = {w.hwnd for w in self._filtered_windows}
        selected_visible_hwnds = {self._get_hwnd_for_row(row) for row in selected_row_indexes}
        selected_visible_hwnds = {hwnd for hwnd in selected_visible_hwnds if hwnd is not None}

        if self._multiple:
            for hwnd in list(self._selected_hwnds):
                if hwnd in visible_hwnds and hwnd not in selected_visible_hwnds:
                    self._selected_hwnds.discard(hwnd)
            self._selected_hwnds.update(selected_visible_hwnds)
        else:
            self._selected_hwnds = set(selected_visible_hwnds)

        self._update_selection_marks()
        self._update_preview()
        self._update_count_label()

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        if not self._multiple:
            self.accept()

    def _update_selection_marks(self):
        for row, window in enumerate(self._filtered_windows):
            item = self.table.item(row, 0)
            if item:
                item.setText("✓" if window.hwnd in self._selected_hwnds else "")

    def _update_preview(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered_windows):
            self.preview_title.setText("-")
            self.preview_process.setText("-")
            self.preview_hwnd.setText("-")
            self.preview_path.setText("-")
            return

        window = self._filtered_windows[row]
        self.preview_title.setText(window.title)
        self.preview_process.setText(window.process_name)
        self.preview_hwnd.setText(str(window.hwnd))
        self.preview_path.setText(self._get_explorer_path(window) or "-")

    def _update_count_label(self):
        total = len(self._filtered_windows)
        selected = len(self._selected_hwnds)
        if self.search_input.text().strip():
            label = f"已选择 {selected} | 显示 {total}"
        else:
            label = f"已选择 {selected} | 共 {total}"
        self.count_label.setText(label)

    def _get_hwnd_for_row(self, row: int) -> Optional[int]:
        item = self.table.item(row, 0)
        if not item:
            return None
        hwnd = item.data(Qt.UserRole)
        if hwnd is None:
            try:
                hwnd = int(self.table.item(row, 4).text())
            except Exception:
                hwnd = None
        return hwnd

    def _get_explorer_path(self, window: WindowInfo) -> str:
        hwnd = window.hwnd
        if hwnd in self._path_cache:
            return self._path_cache[hwnd]

        path = ""
        try:
            process_name = (window.process_name or "").lower()
            if process_name == "explorer.exe" or window.class_name == "CabinetWClass":
                path = self.explorer_helper.get_explorer_folder_path(hwnd) or ""
        except Exception:
            path = ""

        self._path_cache[hwnd] = path
        return path

    def _get_selected_window_infos(self) -> List[WindowInfo]:
        selected_windows = []
        for hwnd in self._selected_hwnds:
            info = self.window_manager.get_window_info(hwnd)
            if info:
                selected_windows.append(info)
        return selected_windows


__all__ = ["QtWindowSelector"]
