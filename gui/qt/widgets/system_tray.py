"""
系统托盘模块

提供 PySide6 的系统托盘功能
"""

from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QBrush, QColor
from PySide6.QtCore import Qt, Signal


class SystemTrayIcon(QSystemTrayIcon):
    """系统托盘图标

    功能：
    - 托盘图标显示
    - 右键菜单
    - 双击显示窗口
    - 通知消息
    """

    # 信号
    show_requested = Signal()
    hide_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        icon_path: Optional[Path] = None,
        parent=None
    ):
        super().__init__(parent)
        self._menu: Optional[QMenu] = None

        # 设置图标
        self._setup_icon(icon_path)

        # 设置提示文本
        self.setToolTip("ContextSwitcher")

        # 创建菜单
        self._create_menu()

    def _setup_icon(self, icon_path: Optional[Path]):
        """设置托盘图标"""
        if icon_path and icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            # 创建默认图标
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # 绘制圆形图标
            painter.setBrush(QBrush(QColor("#107C10")))  # 绿色
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(4, 4, 56, 56)

            # 绘制闪电符号（简单白色圆形）
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.drawEllipse(24, 20, 16, 24)

            painter.end()

            icon = QIcon(pixmap)

        self.setIcon(icon)

    def _create_menu(self):
        """创建右键菜单"""
        menu = QMenu()

        # 显示窗口
        show_action = QAction("显示窗口", menu)
        show_action.triggered.connect(self.show_requested.emit)
        menu.addAction(show_action)

        # 隐藏窗口
        hide_action = QAction("隐藏窗口", menu)
        hide_action.triggered.connect(self.hide_requested.emit)
        menu.addAction(hide_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self._menu = menu
        self.setContextMenu(menu)

        # 双击事件
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        """托盘图标被激活"""
        activation = QSystemTrayIcon.ActivationReason
        if reason in (activation.DoubleClick, activation.Trigger, activation.MiddleClick):
            self.show_requested.emit()

    def show_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information
    ):
        """显示通知消息

        Args:
            title: 通知标题
            message: 通知内容
            icon: 图标类型
        """
        self.showMessage(title, message, icon, 3000)

    def set_tooltip(self, text: str):
        """设置提示文本"""
        self.setToolTip(text)
