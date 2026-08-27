"""
PySide6 样式表模块

包含 ContextSwitcher 的所有 UI 样式定义
"""

from pathlib import Path
from functools import lru_cache
import sys

from PySide6.QtGui import QIcon

def _get_styles_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "gui" / "qt" / "styles"
    return Path(__file__).parent


# 获取样式文件目录
styles_dir = _get_styles_dir()
icons_dir = styles_dir / "icons"

REQUIRED_ICON_NAMES = (
    "add",
    "broom",
    "chart",
    "check",
    "chevron-down",
    "chevron-up",
    "close",
    "edit",
    "keyboard",
    "lightning",
    "minimize",
    "priority-high",
    "priority-low",
    "priority-medium",
    "priority-none",
    "radio-dot",
    "refresh",
    "search",
    "settings",
    "tomato",
    "workspace",
)


def load_stylesheet(name: str = "dark") -> str:
    """
    加载样式表

    Args:
        name: 样式名称 ("dark", "light")

    Returns:
        QSS 样式表字符串
    """
    style_file = styles_dir / f"{name}_theme.qss"
    if style_file.exists():
        with open(style_file, 'r', encoding='utf-8') as f:
            stylesheet = f.read()
        return stylesheet.replace("__ICON_DIR__", icons_dir.as_posix())
    return ""


def get_icon_path(name: str) -> Path:
    """返回随应用打包的 SVG 图标路径。"""
    return icons_dir / f"{name}.svg"


@lru_cache(maxsize=None)
def get_icon(name: str) -> QIcon:
    """加载随应用打包的 SVG 图标。"""
    return QIcon(str(get_icon_path(name)))


def get_dark_theme() -> str:
    """获取暗色主题样式表"""
    return load_stylesheet("dark")


def get_light_theme() -> str:
    """获取亮色主题样式表"""
    return load_stylesheet("light")


__all__ = [
    "REQUIRED_ICON_NAMES",
    "get_dark_theme",
    "get_icon",
    "get_icon_path",
    "get_light_theme",
    "load_stylesheet",
]
