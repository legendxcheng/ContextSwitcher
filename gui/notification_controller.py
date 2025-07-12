"""
通知控制器模块

负责Toast通知管理和空闲任务检测逻辑
从MainWindow中提取，遵循单一职责原则
"""

import time
from typing import Optional, Callable
from abc import ABC, abstractmethod


class INotificationHandler(ABC):
    """通知处理器接口"""
    
    @abstractmethod
    def handle_toast_click(self, task_id: str) -> None:
        """处理Toast点击"""
        pass
    
    @abstractmethod
    def check_idle_tasks(self) -> None:
        """检查空闲任务"""
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化通知系统"""
        pass


class INotificationProvider(ABC):
    """通知提供器接口 - 定义NotificationController需要的回调方法"""
    
    @abstractmethod
    def get_task_manager(self):
        """获取任务管理器"""
        pass
    
    @abstractmethod
    def get_config(self):
        """获取配置对象"""
        pass
    
    @abstractmethod
    def set_status(self, message: str, duration_ms: int = 0):
        """设置状态消息"""
        pass


class NotificationController(INotificationHandler):
    """通知控制器实现"""
    
    def __init__(self, notification_provider: INotificationProvider):
        """初始化通知控制器
        
        Args:
            notification_provider: 通知提供器接口实现
        """
        self.notification_provider = notification_provider
        
        # Toast管理器
        self.toast_manager = None
        
        # 监控状态
        self.last_monitoring = 0
        self.monitoring_interval = 60.0  # 监控间隔：60秒
        
        print("✓ 通知控制器初始化完成")
    
    def initialize(self) -> None:
        """初始化Toast管理器"""
        try:
            from utils.toast_manager import get_toast_manager
            
            self.toast_manager = get_toast_manager()
            
            # 从配置读取设置
            config = self.notification_provider.get_config()
            monitoring_config = config.get_monitoring_config()
            cooldown_minutes = monitoring_config.get('toast_cooldown_minutes', 30)
            self.toast_manager.set_cooldown_minutes(cooldown_minutes)
            
            # 设置点击回调
            self.toast_manager.on_toast_clicked = self.handle_toast_click
            
            print("✓ Toast管理器初始化完成")
            
        except Exception as e:
            print(f"初始化Toast管理器失败: {e}")
            self.toast_manager = None
    
    def check_idle_tasks(self) -> None:
        """检查并处理待机时间超时的任务"""
        try:
            config = self.notification_provider.get_config()
            monitoring_config = config.get_monitoring_config()
            
            # 检查是否启用通知
            if not monitoring_config.get('toast_notifications_enabled', True):
                return
            
            if not self.toast_manager:
                return
            
            # 获取超时任务
            from utils.time_helper import get_overdue_tasks
            task_manager = self.notification_provider.get_task_manager()
            current_task_index = task_manager.current_task_index
            overdue_tasks = get_overdue_tasks(task_manager.get_all_tasks(), current_task_index)
            
            if not overdue_tasks:
                return
            
            # 发送通知
            if len(overdue_tasks) == 1:
                # 单个任务通知
                task_info = overdue_tasks[0]
                self.toast_manager.send_idle_task_notification(
                    task_info['task'].name,
                    task_info['task'].id,
                    task_info['display_time']
                )
            else:
                # 多个任务汇总通知
                self.toast_manager.send_multiple_tasks_notification(overdue_tasks)
            
        except Exception as e:
            print(f"检查待机任务失败: {e}")
    
    def handle_toast_click(self, task_id: str) -> None:
        """Toast通知点击回调"""
        try:
            task_manager = self.notification_provider.get_task_manager()
            
            # 查找对应的任务
            task = task_manager.get_task_by_id(task_id)
            if not task:
                print(f"找不到任务: {task_id}")
                return
            
            # 获取任务索引
            all_tasks = task_manager.get_all_tasks()
            for i, t in enumerate(all_tasks):
                if t.id == task_id:
                    # 切换到该任务
                    success = task_manager.switch_to_task(i)
                    if success:
                        self.notification_provider.set_status(f"通过通知切换到: {task.name}", 3000)
                        print(f"✓ 通过Toast通知切换到任务: {task.name}")
                    else:
                        print(f"✗ 切换到任务失败: {task.name}")
                    break
            
        except Exception as e:
            print(f"处理Toast点击失败: {e}")
    
    def should_check_idle_tasks(self, current_time: float) -> bool:
        """检查是否应该进行空闲任务检测
        
        Args:
            current_time: 当前时间戳
            
        Returns:
            bool: 是否应该检测空闲任务
        """
        if current_time - self.last_monitoring > self.monitoring_interval:
            self.last_monitoring = current_time
            return True
        return False
    
    def get_toast_manager(self):
        """获取Toast管理器实例"""
        return self.toast_manager
    
    def set_monitoring_interval(self, interval: float) -> None:
        """设置监控间隔
        
        Args:
            interval: 监控间隔（秒）
        """
        if interval > 0:
            self.monitoring_interval = interval
            print(f"✓ 监控间隔设置为: {interval}秒")
    
    def get_monitoring_status(self) -> dict:
        """获取监控状态信息（用于调试）"""
        return {
            "toast_manager_initialized": self.toast_manager is not None,
            "last_monitoring": self.last_monitoring,
            "monitoring_interval": self.monitoring_interval,
            "next_check_in": max(0, self.monitoring_interval - (time.time() - self.last_monitoring))
        }
    
    def force_check_idle_tasks(self) -> None:
        """强制执行空闲任务检测（忽略时间间隔）"""
        print("🔔 强制执行空闲任务检测...")
        self.check_idle_tasks()
    
    def is_notifications_enabled(self) -> bool:
        """检查通知是否启用"""
        try:
            config = self.notification_provider.get_config()
            monitoring_config = config.get_monitoring_config()
            return monitoring_config.get('toast_notifications_enabled', True)
        except Exception as e:
            print(f"检查通知设置失败: {e}")
            return False