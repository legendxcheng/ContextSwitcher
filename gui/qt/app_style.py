"""Qt 应用级样式配置。"""

from PySide6.QtWidgets import QApplication

from gui.qt.styles import get_dark_theme


APPLICATION_STYLE = "Fusion"


def configure_application_style(app: QApplication) -> None:
    """固定平台无关的基础样式，并在应用级加载主题。"""
    app.setStyle(APPLICATION_STYLE)
    app.setStyleSheet(get_dark_theme())


__all__ = ["APPLICATION_STYLE", "configure_application_style"]
