"""
应用窗口辅助模块

提供各类应用的窗口上下文提取和恢复功能:
- BaseAppHelper: 抽象基类
- TerminalHelper: Windows Terminal/PowerShell/CMD
- VSCodeHelper: Visual Studio Code
- AppHelperRegistry: 辅助类注册表
- get_app_helper_registry: 获取全局注册表单例
"""

from .base_app_helper import BaseAppHelper
from .terminal_helper import TerminalHelper
from .vscode_helper import VSCodeHelper
from .app_helper_registry import AppHelperRegistry, get_app_helper_registry

__all__ = [
    'BaseAppHelper',
    'TerminalHelper',
    'VSCodeHelper',
    'AppHelperRegistry',
    'get_app_helper_registry',
]
