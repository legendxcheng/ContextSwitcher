"""
PySide6 样式表模块

包含 ContextSwitcher 的所有 UI 样式定义
"""

from pathlib import Path
import sys

def _get_styles_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "gui" / "qt" / "styles"
    return Path(__file__).parent


# 获取样式文件目录
styles_dir = _get_styles_dir()


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
            return f.read()
    return ""


def get_dark_theme() -> str:
    """获取暗色主题样式表"""
    return load_stylesheet("dark")


def get_light_theme() -> str:
    """获取亮色主题样式表"""
    return load_stylesheet("light")
