"""
无边框窗口基类模块

提供无边框窗口的基础功能：
- FramelessWindow: 无边框窗口基类
- CustomTitleBar: 自定义标题栏
"""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QIcon, QAction


class CustomTitleBar(QWidget):
    """自定义标题栏组件"""

    # 信号
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, title: str = "", icon: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # 保存拖拽状态
        self._old_pos: Optional[QPoint] = None
        self._drag_start_pos: Optional[QPoint] = None

        self.setup_ui(title, icon)

    def setup_ui(self, title: str, icon: str):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        # 应用图标
        if icon:
            icon_label = QLabel(icon)
            icon_label.setObjectName("titleIcon")
            icon_label.setStyleSheet("font-size: 14pt;")
            layout.addWidget(icon_label)

        # 应用标题
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # 最小化按钮
        self.min_btn = QPushButton("─")
        self.min_btn.setObjectName("titleButton")
        self.min_btn.setFixedSize(26, 20)
        self.min_btn.setToolTip("最小化")
        self.min_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.min_btn)

        # 关闭按钮
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("titleButton")
        self.close_btn.setProperty("closeButton", True)
        self.close_btn.setFixedSize(26, 20)
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

    def set_title(self, title: str):
        """设置标题"""
        self.title_label.setText(title)

    def mousePressEvent(self, event):
        """鼠标按下 - 记录位置用于拖拽"""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()

    def mouseMoveEvent(self, event):
        """鼠标移动 - 触发窗口拖拽"""
        if self._drag_start_pos and event.buttons() == Qt.LeftButton:
            # 通知父窗口移动
            if self.parent():
                parent = self.parent()
                while parent and not isinstance(parent, (FramelessWindow, QMainWindow)):
                    parent = parent.parent()
                if parent and hasattr(parent, 'move_by_drag'):
                    delta = event.pos() - self._drag_start_pos
                    parent.move_by_drag(delta)

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        self._drag_start_pos = None

    def mouseDoubleClickEvent(self, event):
        """双击 - 最大化/还原"""
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()


class FramelessWindow(QMainWindow):
    """无边框窗口基类

    特性：
    - 无边框显示
    - 可拖拽移动
    - 自定义标题栏
    - 可选透明度
    - Windows 11 圆角效果
    """

    # 信号
    window_shown = Signal()
    window_hidden = Signal()

    def __init__(
        self,
        title: str = "",
        icon: str = "⚡",
        alpha: float = 0.98,
        idle_alpha: Optional[float] = None,
        keep_on_top: bool = True,
        resizable: bool = False,
        size: tuple = (420, 420)  # 小浮窗尺寸 - 进一步增加高度
    ):
        super().__init__()

        # 配置
        self._hover_alpha = alpha
        if idle_alpha is None:
            self._idle_alpha = max(0.7, alpha - 0.18)
        else:
            self._idle_alpha = min(max(idle_alpha, 0.35), 1.0)
        self._keep_on_top = keep_on_top
        self._resizable = resizable
        self._window_size = size

        # 拖拽相关
        self._drag_position: Optional[QPoint] = None
        self._is_dragging = False

        # 窗口标志
        self._setup_window_flags()

        # 窗口属性
        self.setWindowOpacity(self._idle_alpha)

        # 半透明背景（用于圆角效果）
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 设置窗口尺寸
        self.resize(*self._window_size)

        # 标题和图标
        if title:
            self.setWindowTitle(title)

        # 创建中心部件
        self._setup_central_widget()

        # 创建标题栏
        self.title_bar = CustomTitleBar(title, icon, self)
        self.title_bar.minimize_clicked.connect(self.hide_to_tray)
        self.title_bar.close_clicked.connect(self.close)
        self.layout().addWidget(self.title_bar)

        # 内容容器
        self.content_widget = QWidget()
        self.content_widget.setObjectName("mainContainer")
        self.layout().addWidget(self.content_widget)

        # 设置样式
        self.setStyleSheet("""
            FramelessWindow {
                background-color: transparent;
            }
            QWidget#mainContainer {
                background-color: #2D2D2D;
                border: 1px solid #404040;
                border-radius: 8px;
            }
        """)

    def _setup_window_flags(self):
        """设置窗口标志"""
        flags = Qt.FramelessWindowHint

        if self._keep_on_top:
            flags |= Qt.WindowStaysOnTopHint
        # 仅托盘显示：隐藏任务栏图标
        flags |= Qt.Tool

        # 如果可调整大小
        if self._resizable:
            # 暂时不启用，需要额外实现调整大小逻辑
            pass

        self.setWindowFlags(flags)

    def _setup_central_widget(self):
        """设置中心部件"""
        central_widget = QWidget()
        central_widget.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setCentralWidget(central_widget)

    def get_content_layout(self) -> QVBoxLayout:
        """获取内容区域的布局"""
        # 如果 content_widget 还没有布局，创建一个
        if not self.content_widget.layout():
            layout = QVBoxLayout(self.content_widget)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
        return self.content_widget.layout()

    def move_by_drag(self, delta: QPoint):
        """通过拖拽移动窗口"""
        self.move(self.pos() + delta)

    def enterEvent(self, event):
        """鼠标进入窗口 - 提高不透明度"""
        self.setWindowOpacity(self._hover_alpha)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口 - 降低不透明度"""
        self.setWindowOpacity(self._idle_alpha)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """鼠标按下 - 记录位置用于拖拽"""
        if event.button() == Qt.LeftButton:
            # 检查是否在标题栏区域
            if event.position().y() <= self.title_bar.height():
                self._drag_position = event.globalPosition().toPoint()
                self._is_dragging = True

    def mouseMoveEvent(self, event):
        """鼠标移动 - 拖拽窗口"""
        if self._is_dragging and self._drag_position:
            delta = event.globalPosition().toPoint() - self._drag_position
            self.move(self.pos() + delta)
            self._drag_position = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """鼠标释放 - 停止拖拽"""
        self._is_dragging = False
        self._drag_position = None

    def show_from_tray(self):
        """从托盘恢复显示"""
        # 强制恢复到正常状态并置顶激活，避免托盘双击后不弹出
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        self.window_shown.emit()

    def hide_to_tray(self):
        """隐藏到托盘"""
        self.hide()
        self.window_hidden.emit()

    def set_title(self, title: str):
        """设置窗口标题"""
        self.title_bar.set_title(title)
        self.setWindowTitle(title)

    def add_widget_to_content(self, widget):
        """添加组件到内容区域"""
        self.get_content_layout().addWidget(widget)

    def add_layout_to_content(self, layout):
        """添加布局到内容区域"""
        self.get_content_layout().addLayout(layout)
