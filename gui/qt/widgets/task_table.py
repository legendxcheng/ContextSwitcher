"""
任务表格组件

提供任务列表的显示和交互功能
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QWidget, QLabel, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

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

    # 列定义
    COLUMNS = ["P", "任务", "窗口", "状态", "距上次"]
    COLUMN_WIDTHS = [20, 140, 24, 48, 48]

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
    # 优先级图标
    PRIORITY_ICONS = {
        1: "🔴",  # 高
        2: "🟡",  # 中
        3: "🟢",  # 低
        0: "⚪",  # 无
    }
    WAVE_WORKSPACE_ICON = "🌊"
    SELECTED_PRIORITY_ICON = "🟢"

    def __init__(self, parent=None):
        super().__init__(parent)

        self._tasks: List = []
        self._selected_row = -1
        self._loading = False

        self._setup_table()
        self.setItemDelegate(_NoFocusDelegate(self))
        self._setup_style()

    def _setup_table(self):
        """设置表格"""
        # 设置列
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # 设置行数
        self.setRowCount(self.DEFAULT_ROWS)

        # 设置列宽（小浮窗紧凑模式）
        self.setColumnWidth(0, 20)   # 优先级 - 固定
        self.setColumnWidth(1, 140)  # 任务名 - 最小宽度
        self.setColumnWidth(2, 24)   # 窗口数 - 固定
        self.setColumnWidth(3, 48)   # 状态 - 固定
        self.setColumnWidth(4, 48)   # 距上次处理 - 固定

        # 设置表头拉伸模式
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 任务名列自动拉伸

        # 禁用垂直表头
        self.verticalHeader().setVisible(False)

        # 表格属性
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

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
        self.setItem(row, 0, self._create_item(self._get_priority_icon(task), alignment=Qt.AlignCenter))

        # 任务名
        self.setItem(row, 1, self._create_item(getattr(task, 'name', 'Unknown')))

        # 窗口数
        window_count = len(getattr(task, 'bound_windows', []))
        self.setItem(row, 2, self._create_item(str(window_count), alignment=Qt.AlignCenter))

        # 状态
        status = getattr(task, 'status', TaskStatus.TODO)
        # 处理枚举类型
        status_value = status.value if isinstance(status, TaskStatus) else status
        status_text = self._get_status_text(status_value)
        status_color = self.STATUS_COLORS.get(status_value, "#CCCCCC")
        self.setItem(row, 3, self._create_centered_item(status_text, status_color))

        # 距上次处理
        last_active_text = getattr(task, 'last_active_text', None)
        if last_active_text is None:
            last_active_seconds = getattr(task, 'last_active_seconds', None)
            if last_active_seconds is None:
                last_active_text = "未开始"
            else:
                last_active_text = self._format_elapsed(last_active_seconds)
        self.setItem(row, 4, self._create_item(last_active_text, alignment=Qt.AlignCenter))

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

            if col == 0:
                if self._has_wave_workspace(task):
                    item.setText(self.WAVE_WORKSPACE_ICON)
                else:
                    item.setText(self.SELECTED_PRIORITY_ICON if is_selected else self._get_priority_icon(task))
                item.setForeground(QColor(self.SELECTED_TEXT_COLOR if is_selected else self._get_priority_color(task)))
                continue

            if is_selected:
                item.setForeground(QColor(self.SELECTED_TEXT_COLOR))
                continue
            elif col == 3:
                item.setForeground(QColor(self._get_status_color(task)))
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

    def _get_priority_icon(self, task) -> str:
        """获取P列优先级图标"""
        if self._has_wave_workspace(task):
            return self.WAVE_WORKSPACE_ICON
        return self.PRIORITY_ICONS.get(getattr(task, 'priority', 0), "⚪")

    def _has_wave_workspace(self, task) -> bool:
        """判断任务是否绑定了 Wave workspace"""
        workspace = getattr(task, 'wave_workspace', None)
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
        status_map = {
            "todo": "待办",
            "in_progress": "进行中",
            "blocked": "已阻塞",
            "review": "待审查",
            "completed": "已完成",
            "paused": "已暂停",
        }
        return status_map.get(status, status)

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
