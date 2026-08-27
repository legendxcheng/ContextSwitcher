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
    QListWidget, QListWidgetItem, QApplication
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QEvent, QPoint
from PySide6.QtGui import QColor, QCursor, QGuiApplication

if TYPE_CHECKING:
    from core.task_manager import TaskManager, Task
    from utils.data_storage import DataStorage
from core.time_tracker import get_time_tracker
from core.herdr_integration import HerdrTaskBinding
from utils.config import get_config
from utils.localization import get_localizer, tr

from gui.qt.widgets import FramelessWindow, TaskTableWidget
from gui.qt.styles import get_dark_theme, get_icon


class QtScreenContextProvider:
    """Read cursor and work-area geometry from Qt's DPI-aware screen model."""

    def current(self):
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        return cursor, screen.availableGeometry()


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
    herdr_transition = Signal(object)  # 需要通知用户的后台 Agent 状态转换

    # 状态筛选映射
    STATUS_FILTERS = (
        ("all", None),
        ("in_progress", "in_progress"),
        ("todo", "todo"),
        ("completed", "completed"),
        ("paused", "paused"),
        ("blocked", "blocked"),
        ("review", "review"),
    )
    SORT_OPTIONS = (
        ("default", "default"),
        ("name", "name"),
        ("status", "status"),
        ("last_active", "last_active"),
    )

    def __init__(
        self,
        task_manager: 'TaskManager',
        data_storage: Optional['DataStorage'] = None,
        screen_context_provider=None,
    ):
        super().__init__(
            title="ContextSwitcher",
            icon=get_icon("lightning"),
            alpha=0.98,
            idle_alpha=0.6,
            keep_on_top=True
        )

        self.task_manager = task_manager
        self.data_storage = data_storage
        self._screen_context_provider = screen_context_provider or QtScreenContextProvider()

        # 状态
        self.running = True
        self.refresh_interval = max(
            1.0,
            float(
                (get_config().get("integrations.herdr", {}) or {}).get(
                    "refresh_interval_seconds", 2
                )
            ),
        )
        self.last_refresh = 0

        # 筛选状态
        self.current_search = ""
        self.current_status_filter = None
        self.current_sort = "default"
        self.filtered_tasks: List['Task'] = []
        self._herdr_monitor = None
        self._last_herdr_metadata_signature = None
        self._herdr_activation_retries: set[str] = set()

        # 番茄钟状态
        self.pomodoro_running = False
        self.pomodoro_seconds = 25 * 60  # 25分钟
        self.pomodoro_remaining = 25 * 60
        self.pomodoro_timer: Optional[QTimer] = None
        self._todo_syncing = False
        self._todo_hover_main = False
        self._todo_hover_popup = False
        self._todo_popup_expanded = False
        self._todo_hide_timer = QTimer(self)
        self._todo_hide_timer.setSingleShot(True)
        self._todo_hide_timer.timeout.connect(self._maybe_hide_todo_popup)
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._maybe_hide_main_window)

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

        self.title_bar.installEventFilter(self)
        self.title_bar.title_label.installEventFilter(self)
        if self.title_bar.icon_label is not None:
            self.title_bar.icon_label.installEventFilter(self)
        self.title_bar.min_btn.installEventFilter(self)
        self.title_bar.close_btn.installEventFilter(self)

        get_localizer().subscribe(self._on_language_changed)

        print("✓ PySide6 主窗口初始化完成")

    def summon_at_cursor(self):
        """Show this window near the cursor and make it ready for interaction."""
        cursor, work_area = self._screen_context_provider.current()
        self._expand_main_window()
        self.setWindowOpacity(self._hover_alpha)

        anchor_x = 24
        anchor_y = max(1, self.title_bar.height() // 2)
        target_x = cursor.x() - anchor_x
        target_y = cursor.y() - anchor_y
        max_x = work_area.right() - self.width() + 1
        max_y = work_area.bottom() - self.height() + 1
        target_x = (
            work_area.left()
            if max_x < work_area.left()
            else min(max(target_x, work_area.left()), max_x)
        )
        target_y = (
            work_area.top()
            if max_y < work_area.top()
            else min(max(target_y, work_area.top()), max_y)
        )

        # Exact screen edges can otherwise put the pointer on a translucent
        # rounded corner. Make those edge pixels solid while keeping both the
        # pointer and the full window inside the monitor work area.
        safe_margin = 8
        local_x = cursor.x() - target_x
        local_y = cursor.y() - target_y
        pointer_near_rounded_edge = (
            local_x < safe_margin
            or local_x >= self.width() - safe_margin
            or local_y < safe_margin
            or local_y >= self.height() - safe_margin
        )
        self.set_square_corners(pointer_near_rounded_edge)

        self.move(target_x, target_y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _setup_ui(self):
        """设置 UI"""
        layout = self.get_content_layout()
        layout.setSpacing(2)   # 更紧凑的间距
        layout.setContentsMargins(4, 3, 4, 3)  # 更紧凑的边距

        self.status_row_widget = None
        self._attach_status_indicator_to_title_bar()

        # 搜索行（已移除以节省空间）

        # 任务表格
        self.task_table = self._create_task_table()
        layout.addWidget(self.task_table)

        # 按钮行
        self.button_row_widget = self._create_button_row()
        layout.addWidget(self.button_row_widget)

        # 底部状态行
        self.bottom_row_widget = self._create_bottom_row()
        layout.addWidget(self.bottom_row_widget)

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

    def _attach_status_indicator_to_title_bar(self):
        """将运行状态指示器放到标题栏内，避免额外占用一整行。"""
        self.status_label = None
        self.indicator_label = QLabel()
        self.indicator_label.setFixedSize(8, 8)
        self._set_status_indicator_color("#107C10")
        self.indicator_label.setToolTip(tr("main.ready"))
        title_layout = self.title_bar.layout()
        title_layout.insertWidget(title_layout.indexOf(self.title_bar.min_btn), self.indicator_label)

    def _set_status_indicator_color(self, color: str):
        """用自绘圆点显示运行状态，避免依赖系统符号字体。"""
        self.indicator_label.setStyleSheet(
            f"background-color: {color}; border: none; border-radius: 4px;"
        )

    def _create_search_row(self) -> QHBoxLayout:
        """创建搜索行"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 搜索图标
        search_icon = QLabel()
        search_icon.setPixmap(get_icon("search").pixmap(QSize(14, 14)))
        layout.addWidget(search_icon)

        # 搜索框
        self.search_combo = QComboBox()
        self.search_combo.setEditable(True)
        self.search_combo.setPlaceholderText(tr("main.search_placeholder"))
        self.search_combo.setMinimumWidth(90)
        self.search_combo.lineEdit().textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_combo)

        # 状态筛选
        self.status_filter = QComboBox()
        for key, value in self.STATUS_FILTERS:
            label_key = "main.filter.all" if key == "all" else f"status.{key}"
            self.status_filter.addItem(tr(label_key), value)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.status_filter.setMinimumWidth(60)
        layout.addWidget(self.status_filter)

        # 排序
        self.sort_label = QLabel(tr("main.sort_label"))
        self.sort_label.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(self.sort_label)

        self.sort_combo = QComboBox()
        for key, value in self.SORT_OPTIONS:
            self.sort_combo.addItem(tr(f"main.sort.{key}"), value)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        self.sort_combo.setMinimumWidth(55)
        layout.addWidget(self.sort_combo)

        # 刷新按钮
        refresh_btn = QPushButton()
        refresh_btn.setFixedSize(24, 22)
        refresh_btn.setProperty("data-size", "small")
        refresh_btn.setIcon(get_icon("refresh"))
        refresh_btn.setIconSize(QSize(13, 13))
        refresh_btn.setToolTip(tr("main.tooltips.refresh"))
        self.refresh_button = refresh_btn
        refresh_btn.clicked.connect(self._refresh_tasks)
        layout.addWidget(refresh_btn)

        return layout

    def _create_task_table(self) -> TaskTableWidget:
        """创建任务表格"""
        table = TaskTableWidget()
        # 连接选择事件
        table.task_selected.connect(self._on_task_selected)
        table.task_activated.connect(self._on_task_activated)
        table.task_reordered.connect(self._on_task_reordered)
        table.agent_focus_requested.connect(self._on_herdr_focus_requested)
        return table

    def set_herdr_monitor(self, monitor) -> None:
        """注入 Herdr 后台适配层，主窗口只消费任务级结果。"""
        if self._herdr_monitor is monitor:
            return
        if self._herdr_monitor is not None:
            try:
                self._herdr_monitor.refreshed.disconnect(self._on_herdr_refresh)
                self._herdr_monitor.focus_finished.disconnect(self._on_herdr_focus_finished)
                self._herdr_monitor.metadata_finished.disconnect(self._on_herdr_metadata_finished)
                self._herdr_monitor.reveal_finished.disconnect(self._on_herdr_reveal_finished)
            except (RuntimeError, TypeError):
                pass

        self._herdr_monitor = monitor
        self._last_herdr_metadata_signature = None
        if monitor is None:
            return
        monitor.refreshed.connect(self._on_herdr_refresh)
        monitor.focus_finished.connect(self._on_herdr_focus_finished)
        monitor.metadata_finished.connect(self._on_herdr_metadata_finished)
        monitor.reveal_finished.connect(self._on_herdr_reveal_finished)
        self._request_herdr_refresh()

    def _herdr_config(self):
        return get_config().get("integrations.herdr", {}) or {}

    def _build_herdr_bindings(self):
        return tuple(
            self._herdr_binding_for_task(task)
            for task in (self.task_manager.tasks if self.task_manager else ())
        )

    @staticmethod
    def _herdr_binding_for_task(task) -> HerdrTaskBinding:
        return HerdrTaskBinding(
            task_id=str(getattr(task, "id", "")),
            workspace_label=str(getattr(task, "herdr_workspace", "") or ""),
            workspace_id=getattr(task, "herdr_workspace_id", None),
        )

    def _request_herdr_refresh(self) -> None:
        if self._herdr_monitor is None or not callable(
            getattr(self._herdr_monitor, "request_refresh", None)
        ):
            return
        if not self._herdr_config().get("monitoring_enabled", True):
            return
        self._herdr_monitor.request_refresh(self._build_herdr_bindings())

    def _on_herdr_refresh(self, result) -> None:
        """原子应用一次 Herdr 快照的全部任务结果。"""
        if not self.task_manager:
            return
        tasks_by_id = {
            str(getattr(task, "id", "")): task
            for task in self.task_manager.tasks
        }
        requested_by_id = {
            binding.task_id: binding
            for binding in getattr(result, "requested_bindings", ())
        }
        eligible_task_ids = {
            task_id
            for task_id, task in tasks_by_id.items()
            if task_id not in requested_by_id
            or self._herdr_binding_for_task(task) == requested_by_id[task_id]
        }
        for summary in result.summaries:
            task = tasks_by_id.get(summary.task_id)
            if task is not None and summary.task_id in eligible_task_ids:
                task.herdr_summary = summary

        for update in result.binding_updates:
            task = tasks_by_id.get(update.task_id)
            if task is None or update.task_id not in eligible_task_ids:
                continue
            self.task_manager.update_herdr_binding(
                update.task_id,
                update.workspace_id,
                update.workspace_label,
            )

        self._refresh_tasks()
        for transition in result.transitions:
            if transition.task_id in eligible_task_ids:
                self.herdr_transition.emit(transition)
        self.sync_active_task_metadata(force=bool(result.reconnected))

    def _on_herdr_focus_requested(self, row: int) -> None:
        if self._herdr_monitor is None or not (0 <= row < len(self.filtered_tasks)):
            return
        task = self.filtered_tasks[row]
        binding = self._herdr_binding_for_task(task)
        self.set_status(
            tr("main.messages.focusing_herdr", task=getattr(task, "name", ""))
        )
        self._herdr_monitor.request_focus(binding)

    def _on_herdr_focus_finished(self, result) -> None:
        self.set_status(
            result.message
            or tr(
                "main.messages.herdr_focus_succeeded"
                if result.success
                else "main.messages.herdr_focus_failed"
            )
        )

    def _on_herdr_metadata_finished(self, result) -> None:
        if not result.success:
            self.set_status(
                result.message or tr("main.messages.herdr_metadata_failed")
            )

    def _on_herdr_reveal_finished(self, result) -> None:
        """Apply a terminal result only while its task is still active."""
        if not self.task_manager:
            return
        task = self.task_manager.get_current_task()
        if task is None or str(getattr(task, "id", "")) != result.task_id:
            return

        if not result.success:
            self._herdr_activation_retries.discard(result.task_id)
            self.set_status(
                result.message or tr("main.messages.herdr_terminal_failed")
            )
            return

        if result.success and result.workspace_id:
            workspace_label = (
                result.workspace_label
                or str(getattr(task, "herdr_workspace", "") or "")
            )
            self.task_manager.update_herdr_binding(
                result.task_id,
                result.workspace_id,
                workspace_label,
            )

        activated = result.hwnd is None
        if result.hwnd is not None:
            activated = self.task_manager.window_manager.activate_window(result.hwnd)

        if not activated:
            if (
                result.task_id not in self._herdr_activation_retries
                and self._herdr_monitor is not None
            ):
                self._herdr_activation_retries.add(result.task_id)
                if self._herdr_monitor.request_reveal(
                    self._herdr_binding_for_task(task)
                ):
                    self.set_status(tr("main.messages.herdr_terminal_retry"))
                    return
                self._herdr_activation_retries.discard(result.task_id)
            self.set_status(tr("main.messages.herdr_terminal_focus_failed"))
            return
        self._herdr_activation_retries.discard(result.task_id)
        self.set_status(
            result.message
            or tr("main.messages.herdr_terminal_ready")
        )

    def sync_active_task_metadata(self, force: bool = False) -> None:
        """将当前任务作为展示型 token 同步到 Herdr workspace。"""
        if self._herdr_monitor is None:
            return
        if not self._herdr_config().get("metadata_sync_enabled", True):
            signature = ("disabled",)
            if force or signature != self._last_herdr_metadata_signature:
                self._last_herdr_metadata_signature = signature
                self._herdr_monitor.request_metadata_clear()
            return

        index = getattr(self.task_manager, "current_task_index", -1)
        tasks = self.task_manager.tasks if self.task_manager else ()
        if not (0 <= index < len(tasks)):
            signature = ("clear",)
            if force or signature != self._last_herdr_metadata_signature:
                self._last_herdr_metadata_signature = signature
                self._herdr_monitor.request_metadata_clear()
            return

        task = tasks[index]
        workspace_id = getattr(task, "herdr_workspace_id", None)
        if not workspace_id:
            signature = ("unbound", str(getattr(task, "id", "")))
            if force or signature != self._last_herdr_metadata_signature:
                self._last_herdr_metadata_signature = signature
                self._herdr_monitor.request_metadata_clear()
            return
        status = getattr(task, "status", "")
        status_value = getattr(status, "value", status)
        signature = (
            str(getattr(task, "id", "")),
            workspace_id,
            str(getattr(task, "name", "")),
            str(status_value or ""),
            str(getattr(task, "description", "") or ""),
        )
        if not force and signature == self._last_herdr_metadata_signature:
            return

        self._last_herdr_metadata_signature = signature
        self._herdr_monitor.request_metadata_sync(
            self._herdr_binding_for_task(task),
            task_name=signature[2],
            task_status=signature[3],
            summary=signature[4],
        )

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
            self.set_status(tr("main.messages.switch_index_missing"))
            return

        binding = self._herdr_binding_for_task(task)
        herdr_monitor = self._herdr_monitor
        defer_herdr = herdr_monitor is not None and binding.is_bound
        self.set_status(tr("main.messages.switching", task=task.name))
        success = self.task_manager.switch_to_task(
            task_index,
            defer_herdr=defer_herdr,
        )
        if defer_herdr:
            if herdr_monitor is not None and herdr_monitor.request_reveal(binding):
                self.set_status(tr("main.messages.opening_herdr", task=task.name))
            else:
                self.set_status(
                    tr("main.messages.herdr_open_failed", task=task.name)
                )
            return
        if success:
            self.set_status(tr("main.messages.switched", task=task.name))
        else:
            self.set_status(tr("main.messages.switch_failed", task=task.name))

    def _on_task_reordered(self, from_row: int, to_row: int):
        """处理任务拖拽排序。"""
        if not self.task_manager:
            return

        # 仅在默认视图（无筛选/搜索）下允许调整顺序，避免映射歧义
        if self.current_search or self.current_status_filter or self.current_sort != "default":
            self.set_status(tr("main.messages.reorder_default_only"))
            self._refresh_tasks()
            return

        if not (0 <= from_row < len(self.filtered_tasks) and 0 <= to_row < len(self.filtered_tasks)):
            self._refresh_tasks()
            return

        moved_task = self.filtered_tasks[from_row]

        if self.task_manager.move_task(from_row, to_row):
            self._apply_filters_internal(self.task_manager.tasks)
            self.task_table.load_tasks(self.filtered_tasks)

            for row, task in enumerate(self.filtered_tasks):
                if getattr(task, "id", None) == getattr(moved_task, "id", None):
                    self.task_table.select_row(row)
                    break

            self.set_status(tr("main.messages.reordered"))
        else:
            self._refresh_tasks()
            self.set_status(tr("main.messages.reorder_failed"))

    def _create_button_row(self) -> QWidget:
        """创建按钮行"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        buttons = [
            ("add", "success", "add", self._on_add_task),
            ("edit", "primary", "edit", self._on_edit_task),
            ("close", "error", "delete", self._on_delete_task),
            ("tomato", "error", "pomodoro", self._on_pomodoro_toggle),
            ("chart", "primary", "stats", self._on_stats),
            ("settings", "warning", "settings", self._on_settings),
        ]

        self.action_buttons = []
        for icon_name, style, tooltip_key, callback in buttons:
            btn = QPushButton()
            btn.setProperty("data-style", style)
            btn.setProperty("data-size", "square")
            btn.setIcon(get_icon(icon_name))
            btn.setIconSize(QSize(14, 14))
            btn.setProperty("i18nTooltip", tooltip_key)
            btn.setToolTip(tr(f"main.tooltips.{tooltip_key}"))
            btn.setFixedSize(24, 24)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            self.action_buttons.append(btn)

        return widget

    def _create_bottom_row(self) -> QWidget:
        """创建底部状态行"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # 今日时间
        self.today_label = QLabel(tr("main.today"))
        layout.addWidget(self.today_label)
        self.today_time_label = QLabel("0m")
        self.today_time_label.setStyleSheet("color: #0078D4;")
        layout.addWidget(self.today_time_label)

        layout.addWidget(QLabel("/"))

        goal_label = QLabel("2h")
        goal_label.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(goal_label)

        # 番茄钟
        self.focus_icon_label = QLabel()
        self.focus_icon_label.setPixmap(get_icon("tomato").pixmap(QSize(14, 14)))
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
        self.shortcut_label = QLabel()
        self.shortcut_label.setPixmap(get_icon("keyboard").pixmap(QSize(15, 15)))
        self.shortcut_label.setToolTip(tr("main.tooltips.shortcut"))
        layout.addWidget(self.shortcut_label)

        # 帮助按钮
        self.help_btn = QPushButton("?")
        self.help_btn.setProperty("data-size", "square")
        self.help_btn.setFixedSize(24, 24)
        self.help_btn.setToolTip(tr("main.tooltips.help"))
        self.help_btn.clicked.connect(self._on_help)
        layout.addWidget(self.help_btn)

        return widget

    def _create_todo_panel(self) -> QWidget:
        """创建当前激活任务的 Todo 面板。"""
        panel = QFrame()
        panel.setObjectName("todoPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, 6, 6, 6)
        panel_layout.setSpacing(4)

        self.todo_summary_row = QFrame()
        self.todo_summary_row.setObjectName("todoSummaryRow")
        summary_layout = QHBoxLayout(self.todo_summary_row)
        summary_layout.setContentsMargins(4, 2, 4, 2)
        summary_layout.setSpacing(4)

        self.todo_summary_label = QLabel(tr("main.todo.inactive"))
        self.todo_summary_label.setObjectName("todoSummaryLabel")
        self.todo_summary_label.setStyleSheet("color: #F2F2F2; font-weight: 600;")
        summary_layout.addWidget(self.todo_summary_label)
        panel_layout.addWidget(self.todo_summary_row)

        self.todo_details_container = QWidget()
        details_layout = QVBoxLayout(self.todo_details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)

        self.todo_title_label = QLabel("Todo")
        self.todo_title_label.setStyleSheet("color: #CCCCCC; font-weight: 600;")
        details_layout.addWidget(self.todo_title_label)

        self.todo_hint_label = QLabel(tr("main.todo.switch_first"))
        self.todo_hint_label.setStyleSheet("color: #8A8A8A;")
        details_layout.addWidget(self.todo_hint_label)

        self.todo_list = QListWidget()
        self.todo_list.setObjectName("todoList")
        self.todo_list.setMaximumHeight(120)
        self.todo_list.itemChanged.connect(self._on_todo_item_changed)
        details_layout.addWidget(self.todo_list)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)

        self.todo_clear_completed_button = QPushButton()
        self.todo_clear_completed_button.setProperty("data-style", "warning")
        self.todo_clear_completed_button.setProperty("data-size", "square")
        self.todo_clear_completed_button.setFixedSize(24, 24)
        self.todo_clear_completed_button.setIcon(get_icon("broom"))
        self.todo_clear_completed_button.setIconSize(QSize(14, 14))
        self.todo_clear_completed_button.setToolTip(
            tr("main.tooltips.clear_completed")
        )
        self.todo_clear_completed_button.clicked.connect(self._on_clear_completed_todo_clicked)
        input_row.addWidget(self.todo_clear_completed_button)

        self.todo_input = QLineEdit()
        self.todo_input.setPlaceholderText(tr("main.todo.input_placeholder"))
        self.todo_input.returnPressed.connect(self._on_add_todo_clicked)
        input_row.addWidget(self.todo_input)

        self.todo_add_button = QPushButton("+")
        self.todo_add_button.setProperty("data-style", "success")
        self.todo_add_button.setProperty("data-size", "square")
        self.todo_add_button.setFixedSize(24, 24)
        self.todo_add_button.clicked.connect(self._on_add_todo_clicked)
        input_row.addWidget(self.todo_add_button)

        details_layout.addLayout(input_row)
        panel_layout.addWidget(self.todo_details_container)

        panel.setStyleSheet("""
            QFrame#todoPanel {
                background-color: #1E1E1E;
                border: 1px solid #404040;
                border-radius: 6px;
            }
            QFrame#todoSummaryRow {
                background-color: #252525;
                border: 1px solid #333333;
                border-radius: 4px;
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
        self.todo_summary_row.installEventFilter(self)
        self.todo_summary_label.installEventFilter(self)
        self.todo_details_container.installEventFilter(self)
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
            self._request_herdr_refresh()
            self._refresh_tasks()
            self._update_today_time()
            self.last_refresh = current_time

    def _on_search_changed(self, text: str):
        """搜索框文本变化"""
        self.current_search = text.lower() if text else ""
        self._apply_filters()

    def _on_filter_changed(self, _index: int):
        """筛选变化"""
        self.current_status_filter = self.status_filter.currentData()
        self._apply_filters()

    def _on_sort_changed(self, _index: int):
        """排序变化"""
        self.current_sort = self.sort_combo.currentData() or "default"
        self._apply_filters()

    def _on_add_task(self):
        """添加任务"""
        self.add_task_requested.emit()
        self.set_status(tr("main.messages.adding_task"))

    def _on_edit_task(self):
        """编辑任务"""
        row = self.task_table.get_selected_row()
        if 0 <= row < len(self.filtered_tasks):
            task = self.filtered_tasks[row]
            self.edit_task_requested.emit(task)
            self.set_status(tr("main.messages.editing_task", task=task.name))

    def _on_delete_task(self):
        """删除任务"""
        row = self.task_table.get_selected_row()
        if 0 <= row < len(self.filtered_tasks):
            task = self.filtered_tasks[row]
            self.delete_task_requested.emit(task)
            self.set_status(tr("main.messages.deleting_task", task=task.name))

    def _on_pomodoro_toggle(self):
        """番茄钟切换"""
        if self.pomodoro_running:
            self._pomodoro_stop()
        else:
            self._pomodoro_start()

    def _on_stats(self):
        """统计"""
        # TODO: 实现统计功能
        self.set_status(tr("main.messages.stats_coming"))

    def _on_settings(self):
        """设置"""
        self.settings_requested.emit()
        self.set_status(tr("main.messages.opening_settings"))

    def _on_help(self):
        """帮助"""
        self.set_status(tr("main.messages.help_coming"))

    def _on_add_todo_clicked(self):
        """新增当前激活任务的 Todo 项。"""
        if not self.task_manager:
            return

        current_task = self.task_manager.get_current_task()
        if not current_task:
            self.set_status(tr("main.messages.activate_task_first"))
            return

        text = self.todo_input.text().strip()
        if not text:
            return

        if self.task_manager.add_todo_item(current_task.id, text):
            self.todo_input.clear()
            self._refresh_todo_panel()
            self.set_status(tr("main.messages.todo_added"))

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
            self.set_status(tr("main.messages.activate_task_first"))
            return

        removed_count = self.task_manager.remove_completed_todo_items(current_task.id)
        if removed_count <= 0:
            self.set_status(tr("main.messages.no_completed_todo"))
            return

        self._refresh_todo_panel()
        self.set_status(tr("main.messages.todo_deleted", count=removed_count))

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
            self.todo_summary_label.setText(tr("main.todo.inactive"))
            self.todo_title_label.setText(tr("main.todo.inactive_title"))
            self.todo_hint_label.setText(tr("main.todo.switch_first"))
            self.todo_hint_label.setVisible(True)
            self.todo_list.setEnabled(False)
            self.todo_input.setEnabled(False)
            self.todo_add_button.setEnabled(False)
            self.todo_clear_completed_button.setEnabled(False)
            self.todo_list.blockSignals(False)
            self._todo_syncing = False
            return

        self.todo_summary_label.setText(current_task.name)
        self.todo_title_label.setText(
            tr("main.todo.title", task=current_task.name)
        )
        todo_items = getattr(current_task, "todo_items", []) or []

        if todo_items:
            self.todo_hint_label.setVisible(False)
        else:
            self.todo_hint_label.setText(tr("main.todo.empty_hint"))
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

    def _expand_main_window(self):
        """Keep the fully expanded window visible while it is being used."""
        self._cancel_auto_hide()

    def _schedule_auto_hide(self):
        """Hide shortly after the pointer leaves the app interaction region."""
        self._cancel_auto_hide()
        self._auto_hide_timer.start(200)

    def _cancel_auto_hide(self):
        if self._auto_hide_timer.isActive():
            self._auto_hide_timer.stop()

    def _maybe_hide_main_window(self):
        """Hide only when the pointer is outside every owned interaction surface."""
        cursor = QCursor.pos()
        if self.frameGeometry().contains(cursor):
            return
        if hasattr(self, "todo_popup") and self.todo_popup.isVisible():
            if self.todo_popup.frameGeometry().contains(cursor):
                return
        if self._is_dragging or self.title_bar.is_dragging:
            self._schedule_auto_hide()
            return

        active_modal = QApplication.activeModalWidget()
        if active_modal is not None and self._owns_widget(active_modal):
            self._schedule_auto_hide()
            return

        self.hide_to_tray()

    def _owns_widget(self, widget) -> bool:
        """Return whether a top-level or child widget belongs to this window."""
        current = widget
        while current is not None:
            if current is self:
                return True
            current = current.parentWidget()
        return False

    def _set_todo_popup_expanded(self, expanded: bool):
        """切换 Todo 浮层的收起/展开状态。"""
        self._todo_popup_expanded = bool(expanded)
        if hasattr(self, "todo_details_container"):
            self.todo_details_container.setVisible(self._todo_popup_expanded)

    def _expand_todo_popup(self):
        """展开 Todo 浮层。"""
        self._set_todo_popup_expanded(True)
        if hasattr(self, "todo_popup"):
            self._position_todo_popup()

    def _collapse_todo_popup(self):
        """收起 Todo 浮层，仅保留当前任务摘要。"""
        self._set_todo_popup_expanded(False)
        if hasattr(self, "todo_popup") and self.isVisible():
            self.todo_popup.show()
            self._position_todo_popup()

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

    def _show_todo_popup(self, expanded: Optional[bool] = None):
        """显示 Todo 浮层。"""
        if not hasattr(self, "todo_popup"):
            return
        if expanded is not None:
            self._set_todo_popup_expanded(expanded)
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
        """仅当鼠标不在 Todo 浮层上时收起。"""
        if self._todo_hover_popup:
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
                task.last_active_text = getattr(
                    task, "last_active_text", tr("time.not_started")
                )
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
            # 默认保持任务管理器中的手动顺序
            return list(tasks)

    def _get_last_active_sort_value(self, task) -> float:
        """获取距上次处理的排序值（越大越久）"""
        value = getattr(task, 'last_active_seconds', None)
        if value is None:
            return float('inf')
        return value

    def _build_last_active_display(self, task, last_session: Optional[str], time_tracker, now: datetime):
        """构建距上次处理的显示文本与秒数"""
        if time_tracker.current_session and time_tracker.current_session.task_id == task.id:
            return tr("status.in_progress"), 0

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

        return tr("time.not_started"), None

    def _format_elapsed(self, seconds: int) -> str:
        """格式化距上次处理时间（紧凑显示）"""
        if seconds < 60:
            return tr("time.just_now")

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

        self.set_status(tr("main.messages.pomodoro_started"))
        self._set_status_indicator_color("#D13438")

    def _pomodoro_stop(self):
        """停止番茄钟"""
        self.pomodoro_running = False

        if self.pomodoro_timer:
            self.pomodoro_timer.stop()

        # 更新UI
        self.focus_icon_label.setVisible(False)
        self.focus_timer_label.setVisible(False)
        self.focus_timer_label.setText("--:--")

        self.set_status(tr("main.messages.pomodoro_stopped"))
        self._set_status_indicator_color("#107C10")

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
        self.focus_timer_label.setText(tr("main.messages.pomodoro_done"))
        self.focus_timer_label.setVisible(True)

        self.set_status(tr("main.messages.pomodoro_complete"))

        # TODO: 播放提示音或显示通知

    def _update_pomodoro_display(self):
        """更新番茄钟显示"""
        minutes = self.pomodoro_remaining // 60
        seconds = self.pomodoro_remaining % 60
        self.focus_timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_language_changed(self, _language: str) -> None:
        self._retranslate_ui()
        self._refresh_tasks()
        self._request_herdr_refresh()
        self._ensure_window_size()

    def _retranslate_ui(self) -> None:
        self.indicator_label.setToolTip(tr("main.ready"))
        if hasattr(self, "search_combo"):
            self.search_combo.setPlaceholderText(tr("main.search_placeholder"))

            selected_filter = self.status_filter.currentData()
            self.status_filter.blockSignals(True)
            self.status_filter.clear()
            for key, value in self.STATUS_FILTERS:
                label_key = "main.filter.all" if key == "all" else f"status.{key}"
                self.status_filter.addItem(tr(label_key), value)
            filter_index = self.status_filter.findData(selected_filter)
            self.status_filter.setCurrentIndex(max(0, filter_index))
            self.status_filter.blockSignals(False)

            selected_sort = self.sort_combo.currentData()
            self.sort_combo.blockSignals(True)
            self.sort_combo.clear()
            for key, value in self.SORT_OPTIONS:
                self.sort_combo.addItem(tr(f"main.sort.{key}"), value)
            sort_index = self.sort_combo.findData(selected_sort)
            self.sort_combo.setCurrentIndex(max(0, sort_index))
            self.sort_combo.blockSignals(False)
            self.sort_label.setText(tr("main.sort_label"))
            self.refresh_button.setToolTip(tr("main.tooltips.refresh"))

        for button in getattr(self, "action_buttons", ()):
            tooltip_key = button.property("i18nTooltip")
            button.setToolTip(tr(f"main.tooltips.{tooltip_key}"))

        self.today_label.setText(tr("main.today"))
        self.shortcut_label.setToolTip(tr("main.tooltips.shortcut"))
        self.help_btn.setToolTip(tr("main.tooltips.help"))
        self.todo_clear_completed_button.setToolTip(
            tr("main.tooltips.clear_completed")
        )
        self.todo_input.setPlaceholderText(tr("main.todo.input_placeholder"))

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
        self._request_herdr_refresh()
        self._refresh_tasks()
        self._update_today_time()

    def cleanup(self):
        """清理资源"""
        if self.pomodoro_timer:
            self.pomodoro_timer.stop()
        self._cancel_auto_hide()
        if hasattr(self, "todo_popup"):
            self.todo_popup.hide()
            self.todo_popup.close()

    def eventFilter(self, watched, event):
        """处理 Todo 浮层的悬停状态。"""
        if watched in {
            getattr(self, "title_bar", None),
            getattr(getattr(self, "title_bar", None), "title_label", None),
            getattr(getattr(self, "title_bar", None), "icon_label", None),
            getattr(getattr(self, "title_bar", None), "min_btn", None),
            getattr(getattr(self, "title_bar", None), "close_btn", None),
        }:
            if event.type() == QEvent.Enter:
                print(f"[HOVER] enter on {type(watched).__name__}")
                self._expand_main_window()
                return False

        if hasattr(self, "todo_popup") and watched in {
            self.todo_popup,
            self.todo_panel,
            self.todo_summary_row,
            self.todo_summary_label,
            self.todo_details_container,
            self.todo_list,
            self.todo_input,
            self.todo_add_button,
            self.todo_clear_completed_button,
        }:
            if event.type() == QEvent.Enter:
                self._todo_hover_popup = True
                self._cancel_auto_hide()
                self._cancel_hide_todo_popup()
                self._show_todo_popup(expanded=True)
                return False
            if event.type() == QEvent.Leave:
                self._todo_hover_popup = False
                self._schedule_hide_todo_popup()
                self._schedule_auto_hide()
                return False
        return super().eventFilter(watched, event)

    def enterEvent(self, event):
        """鼠标进入窗口时展开主界面。"""
        super().enterEvent(event)
        self._cancel_auto_hide()
        self._todo_hover_main = True
        self._cancel_hide_todo_popup()
        print("[HOVER] main enterEvent")
        self._expand_main_window()

    def leaveEvent(self, event):
        """鼠标离开窗口时延迟隐藏主界面。"""
        self._todo_hover_main = False
        print("[HOVER] main leaveEvent")
        self._schedule_auto_hide()
        super().leaveEvent(event)
        self.setWindowOpacity(self._hover_alpha)

    def showEvent(self, event):
        """主窗口显示时进入完整、清晰的活动态。"""
        super().showEvent(event)
        self.setWindowOpacity(self._hover_alpha)
        self._expand_main_window()

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
        self._cancel_auto_hide()
        self._cancel_hide_todo_popup()
        self._hide_todo_popup()
        super().hideEvent(event)
