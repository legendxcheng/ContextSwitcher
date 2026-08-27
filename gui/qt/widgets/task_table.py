"""
任务表格组件

提供任务列表的显示和交互功能
"""

from datetime import datetime
from typing import List, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QWidget, QLabel, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QDropEvent, QIcon

from gui.qt.styles import get_icon
from core.herdr_integration import HerdrTaskState
from utils.localization import get_localizer, tr

# 导入 TaskStatus 用于类型检查
try:
    from core.task_manager import TaskStatus
except ImportError:
    # 如果导入失败，创建一个简单的枚举
    from enum import Enum
    class TaskStatus(Enum):
        TODO = "todo"
        IN_PROGRESS = "in_progress"
        BLOCKED = "blocked"
        REVIEW = "review"
        COMPLETED = "completed"
        PAUSED = "paused"


class _NoFocusDelegate(QStyledItemDelegate):
    """移除单元格焦点绘制，避免出现竖线焦点框"""

    def paint(self, painter, option, index):
        if option.state & QStyle.State_HasFocus:
            option.state &= ~QStyle.State_HasFocus
        super().paint(painter, option, index)


class TaskTableWidget(QTableWidget):
    """任务表格组件

    功能：
    - 任务列表显示
    - 状态图标
    - 行选择
    - 双击切换
    """

    # 信号
    task_selected = Signal(int)  # 任务索引
    task_activated = Signal(int)  # 任务被激活（双击切换或回车）
    task_reordered = Signal(int, int)  # from_row, to_row
    agent_focus_requested = Signal(int)  # 聚焦该任务最需要关注的 Agent

    # 列定义
    PRIORITY_COLUMN = 0
    AGENT_COLUMN = 1
    TASK_COLUMN = 2
    WINDOW_COLUMN = 3
    STATUS_COLUMN = 4
    LAST_ACTIVE_COLUMN = 5
    COLUMNS = ["P", "A", "task", "windows", "status", "last_active"]
    COLUMN_WIDTHS = [20, 20, 120, 24, 48, 48]

    # 默认显示行数（小浮窗）
    DEFAULT_ROWS = 4

    # 状态颜色映射
    STATUS_COLORS = {
        "todo": "#808080",
        "in_progress": "#0078D4",
        "blocked": "#FF8C00",
        "review": "#9B59B6",
        "completed": "#107C10",
        "paused": "#607D8B",
    }

    # 选中/告警颜色
    SELECTED_TEXT_COLOR = "#00FF66"
    PRIORITY_DEFAULT_COLOR = "#808080"
    PRIORITY_STALE_COLOR = "#D13438"
    DEFAULT_TEXT_COLOR = "#FFFFFF"
    RECENT_LAST_ACTIVE_COLOR = "#00FF66"
    STALE_LAST_ACTIVE_COLOR = "#FFFFFF"
    LAST_ACTIVE_COLOR_RANGE_SECONDS = 2 * 60 * 60
    # 优先级图标
    PRIORITY_ICON_NAMES = {
        1: "priority-high",
        2: "priority-medium",
        3: "priority-low",
        0: "priority-none",
    }
    AGENT_STATE_PRESENTATION = {
        HerdrTaskState.NOT_STARTED: ("○", "#808080", "not_started"),
        HerdrTaskState.BLOCKED: ("●", "#D13438", "blocked"),
        HerdrTaskState.WORKING: ("▶", "#FFBA08", "working"),
        HerdrTaskState.DONE: ("✓", "#4AA3FF", "done"),
        HerdrTaskState.IDLE: ("◆", "#6CCB6C", "idle"),
        HerdrTaskState.UNKNOWN: ("?", "#FF8C00", "unknown"),
        HerdrTaskState.UNAVAILABLE: ("×", "#808080", "unavailable"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._tasks: List = []
        self._selected_row = -1
        self._loading = False

        self._setup_table()
        self.setItemDelegate(_NoFocusDelegate(self))
        self._setup_style()
        get_localizer().subscribe(self._on_language_changed)

    def _setup_table(self):
        """设置表格"""
        # 设置列
        self.setColumnCount(6)
        self._retranslate_headers()

        # 设置行数
        self.setRowCount(self.DEFAULT_ROWS)

        # 设置列宽（小浮窗紧凑模式）
        for column, width in enumerate(self.COLUMN_WIDTHS):
            self.setColumnWidth(column, width)

        # 设置表头拉伸模式
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.TASK_COLUMN, QHeaderView.Stretch)  # 任务名列自动拉伸

        # 禁用垂直表头
        self.verticalHeader().setVisible(False)

        # 表格属性
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.setIconSize(QSize(12, 12))
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)

        # 设置固定行高（紧凑）
        self.verticalHeader().setDefaultSectionSize(20)  # 20像素行高
        self.verticalHeader().setMinimumSectionSize(20)

        # 表头设置
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)

        # 设置表头高度
        header.setFixedHeight(22)

        # 连接事件
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.cellClicked.connect(self._on_cell_clicked)

    def _setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QTableWidget {
                background-color: #1A1A1A;
                alternate-background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #404040;
                gridline-color: #404040;
                selection-background-color: transparent;
                selection-color: #00FF66;
            }
            QTableWidget::item {
                padding: 2px;
                border-bottom: 1px solid #404040;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: #00FF66;
                border: none;
                border-bottom: 1px solid #404040;
            }
            QTableWidget::item:selected:active,
            QTableWidget::item:selected:!active {
                background-color: transparent;
                color: #00FF66;
                border: none;
                border-bottom: 1px solid #404040;
            }
            QTableWidget::item:focus {
                outline: none;
            }
            QTableWidget::item:hover {
                background-color: #3A3A3A;
            }
            QHeaderView::section {
                background-color: #404040;
                color: #FFFFFF;
                padding: 4px;
                border: none;
                border-right: 1px solid #505050;
                border-bottom: 1px solid #505050;
                font-weight: bold;
            }
            QHeaderView::section:hover {
                background-color: #505050;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #404040;
                border: none;
            }
        """)

    def _on_selection_changed(self):
        """选择变化"""
        if self._loading:
            return
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            self._selected_row = row
            self._apply_row_styles()
            self.task_selected.emit(row)
        else:
            self._selected_row = -1
            self._apply_row_styles()

    def _on_item_double_clicked(self, item):
        """双击项目"""
        self.task_activated.emit(item.row())

    def _on_cell_clicked(self, row: int, column: int):
        """Agent 列是独立的一键聚焦入口。"""
        if column == self.AGENT_COLUMN:
            self.agent_focus_requested.emit(row)

    def dropEvent(self, event: QDropEvent):
        """拖拽重排任务行，交由外层更新真实任务顺序。"""
        if (
            self._loading
            or event.source() is not self
            or self.rowCount() <= 1
        ):
            super().dropEvent(event)
            return

        from_row = self.currentRow()
        if not (0 <= from_row < self.rowCount()):
            super().dropEvent(event)
            return

        drop_position = event.position().toPoint()
        drop_row = self.rowAt(drop_position.y())
        if drop_row < 0:
            insertion_index = self.rowCount()
        else:
            insertion_index = drop_row
            if self.dropIndicatorPosition() == QAbstractItemView.BelowItem:
                insertion_index += 1

        # 将插入位置转换为“移除后”的最终索引
        to_row = insertion_index
        if insertion_index > from_row:
            to_row -= 1

        to_row = max(0, min(to_row, self.rowCount() - 1))
        if to_row != from_row:
            event.acceptProposedAction()
            self.task_reordered.emit(from_row, to_row)
            return

        event.ignore()

    def load_tasks(self, tasks: List):
        """加载任务列表

        Args:
            tasks: 任务对象列表
        """
        self._loading = True
        self._tasks = tasks or []
        self.setRowCount(len(self._tasks))

        for row, task in enumerate(self._tasks):
            self._set_row_data(row, task)

        # 尝试保留选择行
        if 0 <= self._selected_row < self.rowCount():
            self.selectRow(self._selected_row)
        else:
            self.clearSelection()
            self._selected_row = -1

        self._loading = False
        self._apply_row_styles()

    def _set_row_data(self, row: int, task):
        """设置行数据

        Args:
            row: 行索引
            task: 任务对象
        """
        # 优先级
        priority_item = self._create_item("", alignment=Qt.AlignCenter)
        priority_item.setIcon(self._get_priority_icon(task))
        self.setItem(row, self.PRIORITY_COLUMN, priority_item)

        # Herdr Agent 运行态（与任务优先级分列展示）
        self.setItem(row, self.AGENT_COLUMN, self._create_agent_item(task))

        # 任务名
        self.setItem(
            row,
            self.TASK_COLUMN,
            self._create_item(getattr(task, 'name', tr("status.unknown"))),
        )

        # 窗口数
        window_count = len(getattr(task, 'bound_windows', []))
        self.setItem(row, self.WINDOW_COLUMN, self._create_item(str(window_count), alignment=Qt.AlignCenter))

        # 状态
        status = getattr(task, 'status', TaskStatus.TODO)
        # 处理枚举类型
        status_value = status.value if isinstance(status, TaskStatus) else status
        status_text = self._get_status_text(status_value)
        status_color = self.STATUS_COLORS.get(status_value, "#CCCCCC")
        self.setItem(row, self.STATUS_COLUMN, self._create_centered_item(status_text, status_color))

        # 距上次处理
        last_active_text = getattr(task, 'last_active_text', None)
        if last_active_text is None:
            last_active_seconds = getattr(task, 'last_active_seconds', None)
            if last_active_seconds is None:
                last_active_text = tr("time.not_started")
            else:
                last_active_text = self._format_elapsed(last_active_seconds)
        self.setItem(row, self.LAST_ACTIVE_COLUMN, self._create_item(last_active_text, alignment=Qt.AlignCenter))

    def _create_agent_item(self, task) -> QTableWidgetItem:
        """创建 Herdr Agent 运行态图标和详情提示。"""
        summary = getattr(task, "herdr_summary", None)
        if summary is None:
            if self._has_herdr_workspace(task):
                item = self._create_centered_item("…", "#808080")
                item.setToolTip(tr("table.agent.loading"))
                return item
            item = self._create_centered_item("", "#808080")
            item.setToolTip(tr("table.agent.not_bound"))
            return item

        if summary.state is HerdrTaskState.NOT_BOUND:
            item = self._create_centered_item("", "#808080")
            item.setToolTip(tr("table.agent.not_bound"))
            return item

        glyph, color, state_key = self.AGENT_STATE_PRESENTATION.get(
            summary.state,
            ("?", "#FF8C00", "unknown"),
        )
        state_text = tr(f"table.agent.{state_key}")
        item = self._create_centered_item(glyph, color)
        tooltip_lines = [
            tr(
                "table.agent.workspace",
                workspace=summary.workspace_label or summary.workspace_id or "-",
            ),
            tr("table.agent.state", state=state_text),
        ]
        if summary.agent_counts:
            counts = ", ".join(
                f"{status}: {count}"
                for status, count in sorted(summary.agent_counts.items())
            )
            tooltip_lines.append(tr("table.agent.counts", counts=counts))
        if summary.urgent_agent or summary.urgent_pane_id:
            target = summary.urgent_agent or "Agent"
            if summary.urgent_pane_id:
                target = f"{target} ({summary.urgent_pane_id})"
            tooltip_lines.append(tr("table.agent.focus", target=target))
        if summary.last_updated:
            updated_at = datetime.fromtimestamp(summary.last_updated).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            tooltip_lines.append(tr("table.agent.updated", time=updated_at))
        if summary.stale:
            tooltip_lines.append(tr("table.agent.stale"))
        if summary.error:
            tooltip_lines.append(tr("table.agent.details", details=summary.error))
        item.setToolTip("\n".join(tooltip_lines))
        return item

    def _create_item(self, text: str, alignment: Optional[Qt.AlignmentFlag] = None) -> QTableWidgetItem:
        """创建表格项"""
        item = QTableWidgetItem(text)
        if alignment is not None:
            item.setTextAlignment(alignment)
        return item

    def _create_centered_item(self, text: str, color: str) -> QTableWidgetItem:
        """创建居中带颜色的项"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        # 设置前景色
        item.setForeground(QColor(color))
        return item

    def _apply_row_styles(self) -> None:
        """应用行样式（选中高亮与P列颜色）"""
        if not self._tasks:
            return

        for row, task in enumerate(self._tasks):
            is_selected = row == self._selected_row
            self._apply_row_text_colors(row, task, is_selected)

    def _apply_row_text_colors(self, row: int, task, is_selected: bool) -> None:
        """根据选中状态与任务信息更新文字颜色"""
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if not item:
                continue

            if col == self.PRIORITY_COLUMN:
                item.setText("")
                item.setIcon(self._get_priority_icon(task, selected=is_selected))
                item.setForeground(QColor(self.SELECTED_TEXT_COLOR if is_selected else self._get_priority_color(task)))
                continue

            if col == self.AGENT_COLUMN:
                summary = getattr(task, "herdr_summary", None)
                if summary is not None and summary.state in self.AGENT_STATE_PRESENTATION:
                    item.setForeground(QColor(self.AGENT_STATE_PRESENTATION[summary.state][1]))
                continue

            if is_selected:
                item.setForeground(QColor(self.SELECTED_TEXT_COLOR))
                continue
            elif col == self.STATUS_COLUMN:
                item.setForeground(QColor(self._get_status_color(task)))
            elif col == self.LAST_ACTIVE_COLUMN:
                item.setForeground(QColor(self._get_last_active_color(task)))
            else:
                item.setForeground(QColor(self.DEFAULT_TEXT_COLOR))

    def _get_status_color(self, task) -> str:
        """获取状态列颜色"""
        status = getattr(task, 'status', TaskStatus.TODO)
        status_value = status.value if isinstance(status, TaskStatus) else status
        return self.STATUS_COLORS.get(status_value, "#CCCCCC")

    def _get_priority_color(self, task) -> str:
        """获取P列颜色（选中/超时/默认）"""
        if self._is_task_overdue(task):
            return self.PRIORITY_STALE_COLOR
        return self.PRIORITY_DEFAULT_COLOR

    def _get_priority_icon(self, task, selected: bool = False) -> QIcon:
        """获取 P 列的内置 SVG 图标。"""
        if self._is_task_overdue(task):
            icon_name = "priority-high"
        else:
            icon_name = self.PRIORITY_ICON_NAMES.get(
                getattr(task, 'priority', 0),
                "priority-none",
            )
        return get_icon(icon_name)

    def _has_herdr_workspace(self, task) -> bool:
        """判断任务是否绑定了 Herdr workspace"""
        workspace = getattr(task, 'herdr_workspace', None)
        if workspace is None:
            return False
        if isinstance(workspace, str):
            return workspace.strip() != ""
        return bool(workspace)

    def _is_task_overdue(self, task) -> bool:
        """判断任务是否超时未点击"""
        last_active_seconds = getattr(task, 'last_active_seconds', None)
        if last_active_seconds is None:
            return False

        try:
            last_active_seconds = int(last_active_seconds)
        except (TypeError, ValueError):
            return False

        if last_active_seconds <= 0:
            return False

        threshold_seconds = self._get_idle_warning_seconds()
        return last_active_seconds >= threshold_seconds

    def _get_last_active_color(self, task) -> str:
        """获取距上次列颜色：刚看过为绿，2小时及以上为白。"""
        last_active_seconds = getattr(task, 'last_active_seconds', None)
        if last_active_seconds is None:
            return self.DEFAULT_TEXT_COLOR

        try:
            last_active_seconds = int(last_active_seconds)
        except (TypeError, ValueError):
            return self.DEFAULT_TEXT_COLOR

        if last_active_seconds <= 0:
            return self.RECENT_LAST_ACTIVE_COLOR

        ratio = min(
            last_active_seconds / self.LAST_ACTIVE_COLOR_RANGE_SECONDS,
            1.0,
        )
        return self._interpolate_color(
            self.RECENT_LAST_ACTIVE_COLOR,
            self.STALE_LAST_ACTIVE_COLOR,
            ratio,
        )

    def _interpolate_color(self, start_color: str, end_color: str, ratio: float) -> str:
        """按 RGB 通道线性插值两个 #RRGGBB 颜色。"""
        ratio = max(0.0, min(float(ratio), 1.0))
        start = QColor(start_color)
        end = QColor(end_color)
        red = round(start.red() + (end.red() - start.red()) * ratio)
        green = round(start.green() + (end.green() - start.green()) * ratio)
        blue = round(start.blue() + (end.blue() - start.blue()) * ratio)
        return QColor(red, green, blue).name().upper()

    def _get_idle_warning_seconds(self) -> int:
        """获取待机警告阈值（秒）"""
        try:
            from utils.config import get_config

            config = get_config()
            minutes = config.get('monitoring.idle_time_warning_minutes', 10)
            return max(0, int(minutes)) * 60
        except Exception:
            return 10 * 60

    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        translated = tr(f"status.{status}")
        return status if translated == f"status.{status}" else translated

    def _format_time(self, seconds: int) -> str:
        """格式化时间

        Args:
            seconds: 秒数

        Returns:
            格式化后的时间字符串 (如 "1h 30m" 或 "45m")
        """
        if seconds < 60:
            return "0m"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

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

    def _on_language_changed(self, _language: str) -> None:
        self._retranslate_headers()
        self.load_tasks(self._tasks)

    def _retranslate_headers(self) -> None:
        self.setHorizontalHeaderLabels([
            tr("table.columns.priority"),
            tr("table.columns.agent"),
            tr("table.columns.task"),
            tr("table.columns.windows"),
            tr("table.columns.status"),
            tr("table.columns.last_active"),
        ])

    def clear_tasks(self):
        """清空任务列表"""
        self._tasks = []
        self._selected_row = -1
        self.clearSelection()
        self.setRowCount(0)

    def get_selected_row(self) -> int:
        """获取选中的行索引"""
        selected = self.selectedItems()
        if selected:
            return selected[0].row()
        return -1

    def select_row(self, row: int):
        """选中指定行"""
        if 0 <= row < self.rowCount():
            self.selectRow(row)
