"""
事件处理相关接口

定义事件控制器和处理器使用的抽象接口
"""

from typing import Dict, Any
from abc import ABC, abstractmethod


class IEventHandler(ABC):
    """事件处理器接口"""

    @abstractmethod
    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理事件

        Args:
            event: 事件名称
            values: 事件值

        Returns:
            bool: True表示事件已处理，False表示需要进一步处理
        """
        pass


class IWindowActions(ABC):
    """窗口动作接口 - 定义EventHandler需要的回调方法"""

    @abstractmethod
    def update_display(self):
        """更新显示"""
        pass

    @abstractmethod
    def set_status(self, message: str, duration_ms: int = 0):
        """设置状态消息"""
        pass

    @abstractmethod
    def get_window(self):
        """获取窗口对象"""
        pass
