"""
任务切换器模块包

提供任务切换对话框的各个子模块：
- SwitcherConfig: 配置管理
- SwitcherLayout: 布局创建
- SwitcherUIUpdater: UI更新
- SwitcherEventHandler: 事件处理
"""

from .switcher_config import SwitcherConfig
from .switcher_layout import SwitcherLayout
from .switcher_ui_updater import SwitcherUIUpdater
from .switcher_event_handler import SwitcherEventHandler

__all__ = [
    'SwitcherConfig',
    'SwitcherLayout',
    'SwitcherUIUpdater',
    'SwitcherEventHandler',
]
