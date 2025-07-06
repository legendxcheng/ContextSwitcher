"""
Toast通知管理器

负责管理系统级Toast通知：
- Windows 10/11 Toast通知
- 通知去重和冷却时间管理
- 通知历史记录
- 通知点击响应
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta

try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    print("警告: win10toast库未安装，Toast通知功能不可用")
    TOAST_AVAILABLE = False


class ToastManager:
    """Toast通知管理器"""
    
    def __init__(self):
        """初始化Toast管理器"""
        self.enabled = TOAST_AVAILABLE
        self.toaster = ToastNotifier() if TOAST_AVAILABLE else None
        
        # 通知历史和冷却管理
        self.notification_history: Dict[str, datetime] = {}  # 任务ID -> 最后通知时间
        self.cooldown_minutes = 30  # 默认冷却时间
        
        # 事件回调
        self.on_toast_clicked: Optional[Callable[[str], None]] = None
        self.on_toast_error: Optional[Callable[[str], None]] = None
        
        # 线程锁
        self._lock = threading.Lock()
        
        print(f"✓ Toast通知管理器初始化 (可用: {self.enabled})")
    
    def set_cooldown_minutes(self, minutes: int):
        """设置冷却时间
        
        Args:
            minutes: 冷却时间（分钟）
        """
        self.cooldown_minutes = max(1, minutes)
    
    def is_notification_allowed(self, task_id: str) -> bool:
        """检查是否允许发送通知（冷却时间检查）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否允许发送通知
        """
        if not self.enabled:
            return False
        
        with self._lock:
            last_notification = self.notification_history.get(task_id)
            if not last_notification:
                return True
            
            # 检查冷却时间
            cooldown_threshold = datetime.now() - timedelta(minutes=self.cooldown_minutes)
            return last_notification < cooldown_threshold
    
    def send_idle_task_notification(self, task_name: str, task_id: str, idle_time: str) -> bool:
        """发送任务待机提醒通知
        
        Args:
            task_name: 任务名称
            task_id: 任务ID
            idle_time: 待机时间描述
            
        Returns:
            是否成功发送通知
        """
        if not self.enabled:
            print("Toast通知功能不可用")
            return False
        
        if not self.is_notification_allowed(task_id):
            print(f"任务 {task_name} 在冷却期内，跳过通知")
            return False
        
        try:
            title = "ContextSwitcher - 任务提醒"
            message = f"任务 '{task_name}' 已待机 {idle_time}\n点击切换到该任务"
            
            # 创建点击回调
            def on_click():
                print(f"用户点击了任务通知: {task_name}")
                if self.on_toast_clicked:
                    self.on_toast_clicked(task_id)
            
            # 发送通知
            self.toaster.show_toast(
                title=title,
                msg=message,
                icon_path=None,  # 使用默认图标
                duration=10,     # 显示10秒
                threaded=True,   # 使用线程避免阻塞
                callback_on_click=on_click
            )
            
            # 记录通知历史
            with self._lock:
                self.notification_history[task_id] = datetime.now()
            
            print(f"✓ 已发送Toast通知: {task_name} (待机 {idle_time})")
            return True
            
        except Exception as e:
            error_msg = f"发送Toast通知失败: {e}"
            print(error_msg)
            if self.on_toast_error:
                self.on_toast_error(error_msg)
            return False
    
    def send_multiple_tasks_notification(self, overdue_tasks: List[Dict[str, Any]]) -> bool:
        """发送多个超时任务的汇总通知
        
        Args:
            overdue_tasks: 超时任务列表，每个元素包含 task, idle_minutes, display_time
            
        Returns:
            是否成功发送通知
        """
        if not self.enabled or not overdue_tasks:
            return False
        
        try:
            count = len(overdue_tasks)
            title = f"ContextSwitcher - {count}个任务需要处理"
            
            # 构建消息内容
            if count == 1:
                task_info = overdue_tasks[0]
                message = f"任务 '{task_info['task'].name}' 已待机 {task_info['display_time']}"
            else:
                # 多个任务的汇总
                task_names = [task_info['task'].name for task_info in overdue_tasks[:3]]  # 最多显示3个
                if count > 3:
                    message = f"{', '.join(task_names)} 等{count}个任务长时间未处理"
                else:
                    message = f"{', '.join(task_names)} 等任务长时间未处理"
            
            # 发送通知
            self.toaster.show_toast(
                title=title,
                msg=message,
                icon_path=None,
                duration=10,
                threaded=True
            )
            
            # 更新所有任务的通知历史
            current_time = datetime.now()
            with self._lock:
                for task_info in overdue_tasks:
                    self.notification_history[task_info['task'].id] = current_time
            
            print(f"✓ 已发送汇总Toast通知: {count}个超时任务")
            return True
            
        except Exception as e:
            error_msg = f"发送汇总Toast通知失败: {e}"
            print(error_msg)
            if self.on_toast_error:
                self.on_toast_error(error_msg)
            return False
    
    def send_custom_notification(self, title: str, message: str, duration: int = 5) -> bool:
        """发送自定义通知
        
        Args:
            title: 通知标题
            message: 通知内容
            duration: 显示时长（秒）
            
        Returns:
            是否成功发送通知
        """
        if not self.enabled:
            return False
        
        try:
            self.toaster.show_toast(
                title=title,
                msg=message,
                icon_path=None,
                duration=duration,
                threaded=True
            )
            
            print(f"✓ 已发送自定义Toast通知: {title}")
            return True
            
        except Exception as e:
            error_msg = f"发送自定义Toast通知失败: {e}"
            print(error_msg)
            if self.on_toast_error:
                self.on_toast_error(error_msg)
            return False
    
    def clear_notification_history(self, task_id: str = None):
        """清除通知历史
        
        Args:
            task_id: 任务ID，为None时清除所有历史
        """
        with self._lock:
            if task_id:
                self.notification_history.pop(task_id, None)
                print(f"✓ 已清除任务 {task_id} 的通知历史")
            else:
                self.notification_history.clear()
                print("✓ 已清除所有通知历史")
    
    def cleanup_old_history(self, days: int = 7):
        """清理过期的通知历史
        
        Args:
            days: 保留天数
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with self._lock:
            expired_tasks = [
                task_id for task_id, last_time in self.notification_history.items()
                if last_time < cutoff_time
            ]
            
            for task_id in expired_tasks:
                del self.notification_history[task_id]
        
        if expired_tasks:
            print(f"✓ 已清理 {len(expired_tasks)} 个过期通知历史")
    
    def get_notification_status(self) -> Dict[str, Any]:
        """获取通知管理器状态
        
        Returns:
            状态信息字典
        """
        with self._lock:
            history_count = len(self.notification_history)
            recent_notifications = [
                {
                    'task_id': task_id,
                    'last_notification': last_time.isoformat()
                }
                for task_id, last_time in self.notification_history.items()
            ]
        
        return {
            'enabled': self.enabled,
            'available': TOAST_AVAILABLE,
            'cooldown_minutes': self.cooldown_minutes,
            'history_count': history_count,
            'recent_notifications': recent_notifications
        }
    
    def test_notification(self) -> bool:
        """测试通知功能
        
        Returns:
            是否测试成功
        """
        if not self.enabled:
            print("Toast通知功能不可用，无法测试")
            return False
        
        try:
            title = "ContextSwitcher - 测试通知"
            message = "这是一个测试通知，如果您看到这条消息，说明Toast通知工作正常。"
            
            self.toaster.show_toast(
                title=title,
                msg=message,
                icon_path=None,
                duration=5,
                threaded=True
            )
            
            print("✓ Toast通知测试已发送")
            return True
            
        except Exception as e:
            print(f"Toast通知测试失败: {e}")
            return False


# 全局Toast管理器实例
_toast_manager = None


def get_toast_manager() -> ToastManager:
    """获取全局Toast管理器实例"""
    global _toast_manager
    if _toast_manager is None:
        _toast_manager = ToastManager()
    return _toast_manager


def send_task_idle_notification(task_name: str, task_id: str, idle_time: str) -> bool:
    """便捷函数：发送任务待机通知"""
    return get_toast_manager().send_idle_task_notification(task_name, task_id, idle_time)


def test_toast_notification() -> bool:
    """便捷函数：测试Toast通知功能"""
    return get_toast_manager().test_notification()