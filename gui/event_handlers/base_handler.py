"""
基础事件处理器

提供所有子处理器的通用功能
"""

from typing import Dict, Any, Optional
from abc import abstractmethod

from gui.interfaces.event_interfaces import IEventHandler, IWindowActions


class BaseEventHandler(IEventHandler):
    """基础事件处理器抽象类

    提供子处理器通用的状态管理、弹窗管理等基础方法
    """

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化基础处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        self.task_manager = task_manager
        self.window_actions = window_actions
        self.data_provider = data_provider

    @abstractmethod
    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理事件（子类必须实现）"""
        pass

    def set_data_provider(self, data_provider):
        """设置数据提供器引用"""
        self.data_provider = data_provider

    def get_window(self):
        """获取窗口对象"""
        return self.window_actions.get_window()

    def update_display(self):
        """更新显示"""
        self.window_actions.update_display()

    def set_status(self, message: str, duration_ms: int = 0):
        """设置状态消息"""
        self.window_actions.set_status(message, duration_ms)

    def get_original_task_index(self, table_row: int) -> int:
        """转换表格行为原始任务索引

        Args:
            table_row: 表格行号

        Returns:
            原始任务索引
        """
        if self.data_provider:
            orig_idx = self.data_provider.get_original_index(table_row)
            if orig_idx >= 0:
                return orig_idx
        return table_row

    def get_task_from_table_row(self, table_row: int):
        """从表格行获取任务对象

        Args:
            table_row: 表格行号

        Returns:
            Task对象或None
        """
        task_index = self.get_original_task_index(table_row)
        return self.task_manager.get_task_by_index(task_index)
