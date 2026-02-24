"""
PySide6 主窗口模块

ContextSwitcher 的 PySide6 主窗口实现
"""

import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QComboBox, QHBoxLayout, QVBoxLayout, QFrame,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, Signal, QEvent, QPoint
from PySide6.QtGui import QColor

if TYPE_CHECKING:
    from core.task_manager import TaskManager, Task
    from utils.data_storage import DataStorage
from core.time_tracker import get_time_tracker

from gui.qt.widgets import FramelessWindow, TaskTableWidget
from gui.qt.widgets.system_tray import SystemTrayIcon
from gui.qt.styles import get_dark_theme


class QtMainWindow(FramelessWindow):
    """PySide6 主窗口

    功能：
    - 任务列表显示
    - 添加/编辑/删除操作
    - 搜索和筛选
    - 番茄钟功能
    - 与 TaskManager 集成
    """

    # 信号
    task_selected = Signal(object)  # 任务对象
    add_task_requested = Signal()
    edit_task_requested = Signal(object)  # 任务对象
    delete_task_requested = Signal(object)  # 任务对象
    settings_requested = Signal()

    # 状态筛选映射
    STATUS_FILTER_MAP = {
        "全部": None,
        "进行中": "in_progress",
        "待办": "todo",
        "已完成": "completed",
        "已暂停": "paused",
        "已阻塞": "blocked",
        "待审查": "review",
    }

    def __init__(
        self,
        task_manager: 'TaskManager',
        data_storage: Optional['DataStorage'] = None
    ):
        super().__init__(
            title="ContextSwitcher",
            icon="⚡",
            alpha=0.98,
            idle_alpha=0.6,
            keep_on_top=True
        )

        self.task_manager = task_manager
        self.data_storage = data_storage

        # 状态
        self.running = True
        self.refresh_interval = 2.0  # 秒
        self.last_refresh = 0

        # 筛选状态
        self.current_search = ""
        self.current_status_filter = None
        self.current_sort = "default"
        self.filtered_tasks: List['Task'] = []

        # 番茄钟状态
        self.pomodoro_running = False
        self.pomodoro_seconds = 25 * 60  # 25分钟
        self.pomodoro_remaining = 25 * 60
        self.pomodoro_timer: Optional[QTimer] = None
        self._todo_syncing = False
        self._todo_hover_main = False
        self._todo_hover_popup = False
        self._todo_hide_timer = QTimer(self)
        self._todo_hide_timer.setSingleShot(True)
        self._todo_hide_timer.timeout.connect(self._maybe_hide_todo_popup)

        # 设置样式
        self.setStyleSheet(get_dark_theme())

        # 创建 UI
        self._setup_ui()
        self._ensure_window_size()

        # 设置定时刷新
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._on_refresh_timer)
        self._refresh_timer.start(int(self.refresh_interval * 1000))

        # 初始加载任务
        self._refresh_tasks()

        print("✓ PySide6 主窗口初始化完成")

    def _setup_ui(self):
        """设置 UI"""
        layout = self.get_content_layout()
        layout.setSpacing(2)   # 更紧凑的间距
        layout.setContentsMargins(4, 3, 4, 3)  # 更紧凑的边距

        # 状态行
        status_row = self._create_status_row()
        layout.addLayout(status_row)

        # 搜索行（已移除以节省空间）

        # 任务表格
        self.task_table = self._create_task_table()
        layout.addWidget(self.task_table)

        # 按钮行
        button_row = self._create_button_row()
        layout.addLayout(button_row)

        # 底部状态行
        bottom_row = self._create_bottom_row()
        layout.addLayout(bottom_row)

        # Hover Todo 面板使用独立浮层窗口，显示在主面板下方
        self.todo_popup = self._create_todo_popup()

    def _ensure_window_size(self):
        """确保窗口尺寸足以完整显示内容（适配高 DPI 缩放）"""
        # 让布局先计算 sizeHint
        if self.content_widget.layout():
            self.content_widget.layout().activate()

        self.title_bar.adjustSize()
        self.content_widget.adjustSize()

        content_hint = self.content_widget.sizeHint()
        title_hint = self.title_bar.sizeHint()

        # 预留边框与阴影的空间
        padding = 16
        min_width = max(content_hint.width(), title_hint.width()) + padding
        min_height = title_hint.height() + content_hint.height() + padding

        # 设置一个合理的底线，避免过小导致控件被裁切
        min_width = max(min_width, 360)
        min_height = max(min_height, 360)

        self.setMinimumSize(min_width, min_height)
        if self.width() < min_width or self.height() < min_height:
            self.resize(min_width, min_height)

    def _create_status_row(self) -> QHBoxLayout:
        """创建状态行"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.status_label = None
        layout.addStretch()

        # 指示器
        self.indicator_label = QLabel("●")
        self.indicator_label.setStyleSheet("color: #107C10; font-size: 12pt;")
        self.indicator_label.setToolTip("就绪")
        layout.addWidget(self.indicator_label)

        return layout

    def _create_search_row(self) -> QHBoxLayout:
        """创建搜索行"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 搜索图标
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(search_icon)

        # 搜索框
        self.search_combo = QComboBox()
        self.search_combo.setEditable(True)
        self.search_combo.setPlaceholderText("搜索任务...")
        self.search_combo.setMinimumWidth(90)
        self.search_combo.lineEdit().textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_combo)

        # 状态筛选
        self.status_filter = QComboBox()
        self.status_filter.addItems(list(self.STATUS_FILTER_MAP.keys()))
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        self.status_filter.setMinimumWidth(60)
        layout.addWidget(self.status_filter)

        # 排序
        sort_label = QLabel("排序:")
        sort_label.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["默认", "名称", "状态", "距上次"])
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.sort_combo.setMinimumWidth(55)
        layout.addWidget(self.sort_combo)

        # 刷新按钮
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 22)
        refresh_btn.setProperty("data-size", "small")
        refresh_btn.setToolTip("刷新任务列表")
        refresh_btn.clicked.connect(self._refresh_tasks)
        layout.addWidget(refresh_btn)

        return layout

    def _create_task_table(self) -> TaskTableWidget:
        """创建任务表格"""
        table = TaskTableWidget()
        # 连接选择事件
        table.task_selected.connect(self._on_task_selected)
        table.task_activated.connect(self._on_task_activated)
        return table

    def _on_task_selected(self, row: int):
        """任务被选中"""
        if 0 <= row < len(self.filtered_tasks):
            task = self.filtered_tasks[row]
            self.task_selected.emit(task)

    def _on_task_activated(self, row: int):
        """任务被激活（双击）"""
        if not (0 <= row < len(self.filtered_tasks)):
            return

        if not self.task_manager:
            return

        task = self.filtered_tasks[row]

        # 将筛选后的行映射回任务管理器索引
        task_index = -1
        for index, existing_task in enumerate(self.task_manager.tasks):
            if getattr(existing_task, 'id', None) == getattr(task, 'id', None):
                task_index = index
                break

        if task_index == -1:
            self.set_status("切换失败: 未找到任务索引")
            return

        self.set_status(f"正在切换到: {task.name}")
        success = self.task_manager.switch_to_task(task_index)
        if success:
            self.set_status(f"已切换到: {task.name}")
        else:
            self.set_status(f"切换失败: {task.name}")

    def _create_button_row(self) -> QHBoxLayout:
        """创建按钮行"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        buttons = [
            ("＋", "success", "添加新任务并绑定窗口", self._on_add_task),
            ("✎", "primary", "编辑选中的任务", self._on_edit_task),
            ("✕", "error", "删除选中的任务", self._on_delete_task),
            ("🍅", "error", "番茄钟专注模式", self._on_pomodoro_toggle),
            ("📊", "primary", "查看专注统计", self._on_stats),
            ("⚙", "warning", "打开设置", self._on_settings),
        ]

        for text, style, tooltip, callback in buttons:
            btn = QPushButton(text)
            btn.setProperty("data-style", style)
            btn.setProperty("data-size", "square")
            btn.setToolTip(tooltip)
            btn.setFixedSize(24, 24)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        return layout

    def _create_bottom_row(self) -> QHBoxLayout:
        """创建底部状态行"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # 今日时间
        layout.addWidget(QLabel("今日:"))
        self.today_time_label = QLabel("0m")
        self.today_time_label.setStyleSheet("color: #0078D4;")
        layout.addWidget(self.today_time_label)

        layout.addWidget(QLabel("/"))

        goal_label = QLabel("2h")
        goal_label.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(goal_label)

        # 番茄钟
        self.focus_icon_label = QLabel("🍅")
        self.focus_icon_label.setVisible(False)
        layout.addWidget(self.focus_icon_label)

        self.focus_timer_label = QLabel("--:--")
        self.focus_timer_label.setVisible(False)
        self.focus_timer_label.setStyleSheet("""
            QLabel {
                color: #D13438;
                background-color: #2D2D2D;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.focus_timer_label)

        layout.addStretch()

        # 快捷键提示
        shortcut_label = QLabel("⌨")
        shortcut_label.setStyleSheet("color: #FF8C00;")
        shortcut_label.setToolTip("Ctrl+Alt+Space 切换任务")
        layout.addWidget(shortcut_label)

        # 帮助按钮
        help_btn = QPushButton("?")
        help_btn.setProperty("data-size", "square")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip("显示帮助信息")
        help_btn.clicked.connect(self._on_help)
        layout.addWidget(help_btn)

        return layout

    def _create_todo_panel(self) -> QWidget:
        """创建当前激活任务的 Todo 面板。"""
        panel = QFrame()
        panel.setObjectName("todoPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(4)

        self.todo_title_label = QLabel("Todo")
        self.todo_title_label.setStyleSheet("color: #CCCCCC; font-weight: 600;")
        panel_layout.addWidget(self.todo_title_label)

        self.todo_hint_label = QLabel("请先切换到一个任务")
        self.todo_hint_label.setStyleSheet("color: #8A8A8A;")
        panel_layout.addWidget(self.todo_hint_label)

        self.todo_list = QListWidget()
        self.todo_list.setObjectName("todoList")
        self.todo_list.setMaximumHeight(120)
        self.todo_list.itemChanged.connect(self._on_todo_item_changed)
        panel_layout.addWidget(self.todo_list)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)

        self.todo_clear_completed_button = QPushButton("🧹")
        self.todo_clear_completed_button.setProperty("data-style", "warning")
        self.todo_clear_completed_button.setProperty("data-size", "square")
        self.todo_clear_completed_button.setFixedSize(24, 24)
        self.todo_clear_completed_button.setToolTip("彻底删除所有已完成子任务")
        self.todo_clear_completed_button.clicked.connect(self._on_clear_completed_todo_clicked)
        input_row.addWidget(self.todo_clear_completed_button)

        self.todo_input = QLineEdit()
        self.todo_input.setPlaceholderText("新增子任务...")
        self.todo_input.returnPressed.connect(self._on_add_todo_clicked)
        input_row.addWidget(self.todo_input)

        self.todo_add_button = QPushButton("+")
        self.todo_add_button.setProperty("data-style", "success")
        self.todo_add_button.setProperty("data-size", "square")
        self.todo_add_button.setFixedSize(24, 24)
        self.todo_add_button.clicked.connect(self._on_add_todo_clicked)
        input_row.addWidget(self.todo_add_button)

        panel_layout.addLayout(input_row)

        panel.setStyleSheet("""
            QFrame#todoPanel {
                background-color: #1E1E1E;
                border: 1px solid #404040;
                border-radius: 6px;
            }
            QListWidget#todoList {
                background-color: #151515;
                border: 1px solid #2E2E2E;
                border-radius: 4px;
                color: #F2F2F2;
            }
            QListWidget#todoList::item {
                padding: 4px 2px;
            }
        """)

        self._refresh_todo_panel()
        return panel

    def _create_todo_popup(self) -> QWidget:
        """创建显示在主面板下方的 Todo 浮层窗口。"""
        popup = QWidget(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        popup.setObjectName("todoPopupWindow")
        popup.setAttribute(Qt.WA_ShowWithoutActivating, True)

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)

        self.todo_panel = self._create_todo_panel()
        popup_layout.addWidget(self.todo_panel)
        popup.hide()
        popup.installEventFilter(self)
        self.todo_panel.installEventFilter(self)
        self.todo_list.installEventFilter(self)
        self.todo_input.installEventFilter(self)
        self.todo_add_button.installEventFilter(self)
        self.todo_clear_completed_button.installEventFilter(self)
        return popup

    # ========== 事件处理 ==========

    def _on_refresh_timer(self):
        """定时刷新"""
        current_time = time.time()
        if current_time - self.last_refresh >= self.refresh_interval:
            self._refresh_tasks()
            self._update_today_time()
            self.last_refresh = current_time

    def _on_search_changed(self, text: str):
        """搜索框文本变化"""
        self.current_search = text.lower() if text else ""
        self._apply_filters()

    def _on_filter_changed(self, filter_text: str):
        """筛选变化"""
        self.current_status_filter = self.STATUS_FILTER_MAP.get(filter_text)
        self._apply_filters()

    def _on_sort_changed(self, sort_text: str):
        """排序变化"""
        sort_map = {
            "默认": "default",
            "名称": "name",
            "状态": "status",
            "距上次": "last_active"
        }
        self.current_sort = sort_map.get(sort_text, "default")
        self._apply_filters()

    def _on_add_task(self):
        """添加任务"""
        self.add_task_requested.emit()
        self.set_status("添加任务...")

    def _on_edit_task(self):
        """编辑任务"""
        row = self.task_table.get_selected_row()
        if 0 <= row < len(self.filtered_tasks):
            task = self.filtered_tasks[row]
            self.edit_task_requested.emit(task)
            self.set_status(f"编辑任务: {task.name}")

    def _on_delete_task(self):
        """删除任务"""
        row = self.task_table.get_selected_row()
        if 0 <= row < len(self.filtered_tasks):
            task = self.filtered_tasks[row]
            self.delete_task_requested.emit(task)
            self.set_status(f"删除任务: {task.name}")

    def _on_pomodoro_toggle(self):
        """番茄钟切换"""
        if self.pomodoro_running:
            self._pomodoro_stop()
        else:
            self._pomodoro_start()

    def _on_stats(self):
        """统计"""
        # TODO: 实现统计功能
        self.set_status("统计功能开发中...")

    def _on_settings(self):
        """设置"""
        self.settings_requested.emit()
        self.set_status("打开设置...")

    def _on_help(self):
        """帮助"""
        self.set_status("帮助功能开发中...")

    def _on_add_todo_clicked(self):
        """新增当前激活任务的 Todo 项。"""
        if not self.task_manager:
            return

        current_task = self.task_manager.get_current_task()
        if not current_task:
            self.set_status("请先激活一个任务")
            return

        text = self.todo_input.text().strip()
        if not text:
            return

        if self.task_manager.add_todo_item(current_task.id, text):
            self.todo_input.clear()
            self._refresh_todo_panel()
            self.set_status("已添加子任务")

    def _on_todo_item_changed(self, item: QListWidgetItem):
        """处理 Todo 项勾选状态变化。"""
        if self._todo_syncing or not self.task_manager:
            return

        current_task = self.task_manager.get_current_task()
        if not current_task:
            return

        item_index = item.data(Qt.UserRole)
        if item_index is None:
            item_index = self.todo_list.row(item)

        completed = item.checkState() == Qt.Checked
        updated = self.task_manager.set_todo_item_completed(current_task.id, int(item_index), completed)
        if updated:
            self._apply_todo_item_style(item, completed)

    def _on_clear_completed_todo_clicked(self):
        """彻底删除当前任务中已完成的 Todo。"""
        if not self.task_manager:
            return

        current_task = self.task_manager.get_current_task()
        if not current_task:
            self.set_status("请先激活一个任务")
            return

        removed_count = self.task_manager.remove_completed_todo_items(current_task.id)
        if removed_count <= 0:
            self.set_status("没有可删除的已完成子任务")
            return

        self._refresh_todo_panel()
        self.set_status(f"已删除 {removed_count} 个已完成子任务")

    def _apply_todo_item_style(self, list_item: QListWidgetItem, completed: bool):
        """根据完成状态应用 Todo 项视觉样式。"""
        font = list_item.font()
        font.setStrikeOut(bool(completed))
        list_item.setFont(font)
        list_item.setForeground(QColor("#7F7F7F" if completed else "#F2F2F2"))

    def _refresh_todo_panel(self):
        """刷新 Todo 面板内容（数据源：当前激活任务）。"""
        if not hasattr(self, "todo_list"):
            return

        current_task = self.task_manager.get_current_task() if self.task_manager else None

        self._todo_syncing = True
        self.todo_list.blockSignals(True)
        self.todo_list.clear()

        if not current_task:
            self.todo_title_label.setText("Todo（未激活任务）")
            self.todo_hint_label.setText("请先切换到一个任务")
            self.todo_hint_label.setVisible(True)
            self.todo_list.setEnabled(False)
            self.todo_input.setEnabled(False)
            self.todo_add_button.setEnabled(False)
            self.todo_clear_completed_button.setEnabled(False)
            self.todo_list.blockSignals(False)
            self._todo_syncing = False
            return

        self.todo_title_label.setText(f"Todo · {current_task.name}")
        todo_items = getattr(current_task, "todo_items", []) or []

        if todo_items:
            self.todo_hint_label.setVisible(False)
        else:
            self.todo_hint_label.setText("暂无子任务，输入后按回车或点击 +")
            self.todo_hint_label.setVisible(True)

        for index, item_data in enumerate(todo_items):
            text = str(item_data.get("text", "")).strip()
            if not text:
                continue
            list_item = QListWidgetItem(text)
            list_item.setFlags(
                list_item.flags()
                | Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsUserCheckable
            )
            list_item.setCheckState(Qt.Checked if item_data.get("completed") else Qt.Unchecked)
            list_item.setData(Qt.UserRole, index)
            self._apply_todo_item_style(list_item, bool(item_data.get("completed")))
            self.todo_list.addItem(list_item)

        self.todo_list.setEnabled(True)
        self.todo_input.setEnabled(True)
        self.todo_add_button.setEnabled(True)
        self.todo_clear_completed_button.setEnabled(True)

        self.todo_list.blockSignals(False)
        self._todo_syncing = False

    def _set_todo_panel_visible(self, visible: bool):
        """控制 Todo 浮层显示状态。"""
        if visible:
            self._show_todo_popup()
        else:
            self._hide_todo_popup()

    def _position_todo_popup(self):
        """将 Todo 浮层定位到主窗口正下方。"""
        if not hasattr(self, "todo_popup"):
            return

        anchor_widget = self.content_widget if hasattr(self, "content_widget") else self
        anchor_top_left = anchor_widget.mapToGlobal(QPoint(0, 0))
        anchor_bottom = anchor_widget.mapToGlobal(QPoint(0, anchor_widget.height()))

        popup_width = anchor_widget.width()
        self.todo_popup.setFixedWidth(popup_width)
        self.todo_popup.adjustSize()

        popup_x = anchor_top_left.x()
        popup_y = anchor_bottom.y() + 2
        self.todo_popup.move(popup_x, popup_y)

    def _show_todo_popup(self):
        """显示 Todo 浮层。"""
        if not hasattr(self, "todo_popup"):
            return
        self._refresh_todo_panel()
        self._position_todo_popup()
        self.todo_popup.show()
        self.todo_popup.raise_()

    def _hide_todo_popup(self):
        """隐藏 Todo 浮层。"""
        if hasattr(self, "todo_popup"):
            self.todo_popup.hide()
        self._todo_hover_popup = False

    def _schedule_hide_todo_popup(self):
        """延迟隐藏，允许鼠标从主面板移动到浮层。"""
        if self._todo_hide_timer.isActive():
            self._todo_hide_timer.stop()
        self._todo_hide_timer.start(120)

    def _cancel_hide_todo_popup(self):
        """取消延迟隐藏。"""
        if self._todo_hide_timer.isActive():
            self._todo_hide_timer.stop()

    def _maybe_hide_todo_popup(self):
        """仅当鼠标不在主面板与浮层上时才隐藏。"""
        if self._todo_hover_main or self._todo_hover_popup:
            return
        self._hide_todo_popup()

    # ========== 任务列表管理 ==========

    def _refresh_tasks(self):
        """刷新任务列表"""
        if not self.task_manager:
            return

        # 获取所有任务
        all_tasks = self.task_manager.tasks
        time_tracker = get_time_tracker()
        now = datetime.now()
        for task in all_tasks:
            try:
                stats = time_tracker.get_task_stats(task.id)
                task.today_seconds = stats.today_seconds
                task.last_active_text, task.last_active_seconds = self._build_last_active_display(
                    task, stats.last_session, time_tracker, now
                )
            except Exception:
                task.today_seconds = getattr(task, 'today_seconds', 0)
                task.last_active_text = getattr(task, 'last_active_text', "未开始")
                task.last_active_seconds = getattr(task, 'last_active_seconds', None)

        # 应用筛选
        self._apply_filters_internal(all_tasks)

        # 更新表格
        self.task_table.load_tasks(self.filtered_tasks)
        self._refresh_todo_panel()

    def _apply_filters(self):
        """应用筛选条件"""
        if not self.task_manager:
            return
        self._apply_filters_internal(self.task_manager.tasks)
        self.task_table.load_tasks(self.filtered_tasks)

    def _apply_filters_internal(self, tasks: List['Task']):
        """内部筛选逻辑"""
        filtered = []

        for task in tasks:
            # 状态筛选
            if self.current_status_filter:
                task_status = getattr(task, 'status', None)
                if task_status != self.current_status_filter:
                    continue

            # 搜索筛选
            if self.current_search:
                name = getattr(task, 'name', '').lower()
                desc = getattr(task, 'description', '').lower()
                if self.current_search not in name and self.current_search not in desc:
                    continue

            filtered.append(task)

        # 排序
        self.filtered_tasks = self._sort_tasks(filtered)

    def _sort_tasks(self, tasks: List['Task']) -> List['Task']:
        """排序任务"""
        if self.current_sort == "name":
            return sorted(tasks, key=lambda t: getattr(t, 'name', ''))
        elif self.current_sort == "status":
            return sorted(tasks, key=lambda t: getattr(t, 'status', ''))
        elif self.current_sort == "last_active":
            return sorted(
                tasks,
                key=lambda t: self._get_last_active_sort_value(t),
                reverse=True
            )
        else:
            # 默认按优先级排序
            return sorted(tasks, key=lambda t: getattr(t, 'priority', 0))

    def _get_last_active_sort_value(self, task) -> float:
        """获取距上次处理的排序值（越大越久）"""
        value = getattr(task, 'last_active_seconds', None)
        if value is None:
            return float('inf')
        return value

    def _build_last_active_display(self, task, last_session: Optional[str], time_tracker, now: datetime):
        """构建距上次处理的显示文本与秒数"""
        if time_tracker.current_session and time_tracker.current_session.task_id == task.id:
            return "进行中", 0

        if last_session:
            try:
                last_end = datetime.fromisoformat(last_session)
                elapsed = int((now - last_end).total_seconds())
            except Exception:
                elapsed = 0
            if elapsed < 0:
                elapsed = 0
            return self._format_elapsed(elapsed), elapsed

        access_count = getattr(task, 'access_count', 0)
        last_accessed = getattr(task, 'last_accessed', "")
        if access_count > 0 and last_accessed:
            try:
                last_time = datetime.fromisoformat(last_accessed)
                elapsed = int((now - last_time).total_seconds())
                if elapsed < 0:
                    elapsed = 0
                return self._format_elapsed(elapsed), elapsed
            except Exception:
                pass

        return "未开始", None

    def _format_elapsed(self, seconds: int) -> str:
        """格式化距上次处理时间（紧凑显示）"""
        if seconds < 60:
            return "刚刚"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"

        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"

        days = hours // 24
        if days < 7:
            return f"{days}d"

        weeks = days // 7
        if weeks < 4:
            return f"{weeks}w"

        months = days // 30
        return f"{months}mo"

    def _update_today_time(self):
        """更新今日时间显示"""
        if not self.task_manager:
            return

        time_tracker = get_time_tracker()
        total_seconds = time_tracker.get_today_total()

        # 格式化显示
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            self.today_time_label.setText(f"{hours}h {minutes}m")
        else:
            self.today_time_label.setText(f"{minutes}m")

    # ========== 番茄钟功能 ==========

    def _pomodoro_start(self):
        """启动番茄钟"""
        self.pomodoro_running = True
        self.pomodoro_remaining = 25 * 60  # 25分钟

        # 更新UI
        self.focus_icon_label.setVisible(True)
        self.focus_timer_label.setVisible(True)
        self._update_pomodoro_display()

        # 创建定时器
        if self.pomodoro_timer is None:
            self.pomodoro_timer = QTimer()
            self.pomodoro_timer.timeout.connect(self._pomodoro_tick)

        self.pomodoro_timer.start(1000)  # 每秒更新

        self.set_status("番茄钟已启动 - 专注25分钟")
        self.indicator_label.setStyleSheet("color: #D13438; font-size: 12pt;")

    def _pomodoro_stop(self):
        """停止番茄钟"""
        self.pomodoro_running = False

        if self.pomodoro_timer:
            self.pomodoro_timer.stop()

        # 更新UI
        self.focus_icon_label.setVisible(False)
        self.focus_timer_label.setVisible(False)
        self.focus_timer_label.setText("--:--")

        self.set_status("番茄钟已停止")
        self.indicator_label.setStyleSheet("color: #107C10; font-size: 12pt;")

    def _pomodoro_tick(self):
        """番茄钟计时"""
        if self.pomodoro_remaining > 0:
            self.pomodoro_remaining -= 1
            self._update_pomodoro_display()
        else:
            # 完成
            self._pomodoro_complete()

    def _pomodoro_complete(self):
        """番茄钟完成"""
        self._pomodoro_stop()

        # 显示完成消息
        self.focus_timer_label.setText("完成!")
        self.focus_timer_label.setVisible(True)

        self.set_status("番茄钟完成！休息一下吧~")

        # TODO: 播放提示音或显示通知

    def _update_pomodoro_display(self):
        """更新番茄钟显示"""
        minutes = self.pomodoro_remaining // 60
        seconds = self.pomodoro_remaining % 60
        self.focus_timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    # ========== 公共方法 ==========

    def set_status(self, message: str):
        """设置状态消息"""
        if self.status_label:
            self.status_label.setText(message)

    def get_selected_task(self) -> Optional['Task']:
        """获取选中的任务"""
        row = self.task_table.get_selected_row()
        if 0 <= row < len(self.filtered_tasks):
            return self.filtered_tasks[row]
        return None

    def update_display(self):
        """更新显示（供外部调用）"""
        self._refresh_tasks()
        self._update_today_time()

    def cleanup(self):
        """清理资源"""
        if self.pomodoro_timer:
            self.pomodoro_timer.stop()
        if hasattr(self, "todo_popup"):
            self.todo_popup.hide()
            self.todo_popup.close()

    def eventFilter(self, watched, event):
        """处理 Todo 浮层的悬停状态。"""
        if hasattr(self, "todo_popup") and watched in {
            self.todo_popup,
            self.todo_panel,
            self.todo_list,
            self.todo_input,
            self.todo_add_button,
            self.todo_clear_completed_button,
        }:
            if event.type() == QEvent.Enter:
                self._todo_hover_popup = True
                self._cancel_hide_todo_popup()
                self._show_todo_popup()
                return False
            if event.type() == QEvent.Leave:
                self._todo_hover_popup = False
                self._schedule_hide_todo_popup()
                return False
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        """鼠标进入窗口时显示 Todo 面板。"""
        super().enterEvent(event)
        self._todo_hover_main = True
        self._cancel_hide_todo_popup()
        self._show_todo_popup()

    def leaveEvent(self, event):
        """鼠标离开窗口时隐藏 Todo 面板。"""
        self._todo_hover_main = False
        self._schedule_hide_todo_popup()
        super().leaveEvent(event)

    def moveEvent(self, event):
        """窗口移动时同步浮层位置。"""
        super().moveEvent(event)
        if hasattr(self, "todo_popup") and self.todo_popup.isVisible():
            self._position_todo_popup()

    def resizeEvent(self, event):
        """窗口尺寸变化时同步浮层位置与宽度。"""
        super().resizeEvent(event)
        if hasattr(self, "todo_popup") and self.todo_popup.isVisible():
            self._position_todo_popup()

    def hideEvent(self, event):
        """主窗口隐藏时同步隐藏浮层。"""
        self._hide_todo_popup()
        super().hideEvent(event)
