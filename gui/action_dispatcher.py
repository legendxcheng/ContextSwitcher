"""
业务动作调度器模块

负责协调各个组件间的业务逻辑和状态管理
从MainWindow中提取剩余的业务逻辑，完成重构
"""

import time
from typing import Optional
from abc import ABC, abstractmethod

from core.task_manager import Task


class IActionDispatcher(ABC):
    """业务动作调度器接口"""
    
    @abstractmethod
    def update_display(self) -> None:
        """更新显示"""
        pass
    
    @abstractmethod
    def set_status(self, message: str, duration_ms: int = 0) -> None:
        """设置状态消息"""
        pass
    
    @abstractmethod
    def on_task_changed(self, task: Task) -> None:
        """任务变化回调"""
        pass
    
    @abstractmethod
    def on_task_switched(self, task: Task, index: int) -> None:
        """任务切换回调"""
        pass


class IActionProvider(ABC):
    """动作提供器接口 - 定义ActionDispatcher需要的组件访问"""
    
    @abstractmethod
    def get_window(self):
        """获取窗口对象"""
        pass
    
    @abstractmethod
    def get_data_provider(self):
        """获取数据提供器"""
        pass
    
    @abstractmethod
    def get_event_controller(self):
        """获取事件控制器"""
        pass
    
    @abstractmethod
    def get_task_manager(self):
        """获取任务管理器"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """检查是否正在运行"""
        pass


class ActionDispatcher(IActionDispatcher):
    """业务动作调度器实现"""
    
    def __init__(self, action_provider: IActionProvider):
        """初始化业务动作调度器
        
        Args:
            action_provider: 动作提供器接口实现
        """
        self.action_provider = action_provider
        
        # 状态管理
        self.preserved_selection = None
        self.status_clear_time = 0
        
        print("✓ 业务动作调度器初始化完成")
    
    def update_display(self) -> None:
        """更新显示内容"""
        window = self.action_provider.get_window()
        if not window or not self.action_provider.is_running():
            return
        
        try:
            # 确定要使用的选中状态（优先使用事件控制器中保存的状态）
            selection_to_restore = self._get_selection_to_restore()
            
            # 更新任务表格和行颜色
            data_provider = self.action_provider.get_data_provider()
            table_data = data_provider.get_table_data()
            row_colors = data_provider.get_row_colors()
            
            # 更新表格数据和行颜色
            window["-TASK_TABLE-"].update(values=table_data, row_colors=row_colors)
            
            # 恢复选中状态
            self._restore_selection(window, selection_to_restore, len(table_data))
            
            # 更新状态显示
            self._update_status_display(window)
            
        except Exception as e:
            print(f"更新显示失败: {e}")
    
    def _get_selection_to_restore(self) -> Optional[int]:
        """获取要恢复的选中状态"""
        selection_to_restore = None
        
        # 优先使用事件控制器中保存的状态
        event_controller = self.action_provider.get_event_controller()
        if event_controller:
            selection_to_restore = event_controller.get_preserved_selection()
        
        # 备用：使用ActionDispatcher的preserved_selection
        if selection_to_restore is None:
            selection_to_restore = self.preserved_selection
        
        # 如果没有保存的状态，尝试获取当前选中状态
        if selection_to_restore is None:
            try:
                window = self.action_provider.get_window()
                table_widget = window["-TASK_TABLE-"]
                if hasattr(table_widget, 'SelectedRows') and table_widget.SelectedRows:
                    selection_to_restore = table_widget.SelectedRows[0]
            except Exception as e:
                print(f"⚠️ 获取选中状态失败: {e}")
        
        return selection_to_restore
    
    def _restore_selection(self, window, selection_to_restore: Optional[int], table_length: int) -> None:
        """恢复选中状态"""
        if selection_to_restore is not None and selection_to_restore < table_length:
            try:
                window["-TASK_TABLE-"].update(select_rows=[selection_to_restore])
            except Exception as e:
                print(f"⚠️ 恢复选中状态失败: {e}")
    
    def _update_status_display(self, window) -> None:
        """更新状态显示"""
        task_manager = self.action_provider.get_task_manager()
        task_count = len(task_manager.get_all_tasks())
        current_task = task_manager.get_current_task()
        
        if current_task:
            status = f"当前: {current_task.name}"
        else:
            status = f"{task_count} 个任务"
        
        window["-STATUS-"].update(status)
        window["-MAIN_STATUS-"].update("就绪")
    
    def set_status(self, message: str, duration_ms: int = 0) -> None:
        """设置状态消息
        
        Args:
            message: 状态消息
            duration_ms: 显示时长（毫秒），0表示永久显示
        """
        window = self.action_provider.get_window()
        if not window:
            return
        
        try:
            window["-MAIN_STATUS-"].update(message)
            
            if duration_ms > 0:
                # 记录状态清除时间，让主事件循环处理
                self.status_clear_time = time.time() + (duration_ms / 1000.0)
                
        except Exception as e:
            print(f"设置状态失败: {e}")
    
    def on_task_changed(self, task: Task) -> None:
        """任务变化回调"""
        if self.action_provider.is_running():
            # 任务发生变化时，清除保存的选中状态以避免索引错位
            self.preserved_selection = None
            event_controller = self.action_provider.get_event_controller()
            if event_controller:
                event_controller.set_preserved_selection(None)
            self.update_display()
    
    def on_task_switched(self, task: Task, index: int) -> None:
        """任务切换回调"""
        if self.action_provider.is_running():
            self.update_display()
            self.set_status(f"已切换到: {task.name}", 3000)
    
    def check_status_clear(self, current_time: float) -> None:
        """检查状态消息是否需要清除"""
        if self.status_clear_time > 0 and current_time >= self.status_clear_time:
            try:
                window = self.action_provider.get_window()
                if window:
                    window["-MAIN_STATUS-"].update("就绪")
                    self.status_clear_time = 0  # 重置清除时间
            except Exception as e:
                print(f"清除状态失败: {e}")
                self.status_clear_time = 0
    
    def get_preserved_selection(self) -> Optional[int]:
        """获取保存的选中状态"""
        return self.preserved_selection
    
    def set_preserved_selection(self, selection: Optional[int]) -> None:
        """设置保存的选中状态"""
        self.preserved_selection = selection
    
    def setup_task_manager_callbacks(self) -> None:
        """设置任务管理器回调"""
        task_manager = self.action_provider.get_task_manager()
        task_manager.on_task_added = self.on_task_changed
        task_manager.on_task_removed = self.on_task_changed
        task_manager.on_task_updated = self.on_task_changed
        task_manager.on_task_switched = self.on_task_switched
        print("✓ 任务管理器回调已设置")
    
    def get_status_info(self) -> dict:
        """获取状态信息（用于调试）"""
        return {
            "preserved_selection": self.preserved_selection,
            "status_clear_time": self.status_clear_time,
            "next_clear_in": max(0, self.status_clear_time - time.time()) if self.status_clear_time > 0 else 0,
            "is_running": self.action_provider.is_running()
        }
    
    def force_update_display(self) -> None:
        """强制更新显示（忽略运行状态检查）"""
        print("🔄 强制更新显示...")
        window = self.action_provider.get_window()
        if window:
            try:
                data_provider = self.action_provider.get_data_provider()
                table_data = data_provider.get_table_data()
                row_colors = data_provider.get_row_colors()
                window["-TASK_TABLE-"].update(values=table_data, row_colors=row_colors)
                self._update_status_display(window)
                print("✓ 强制更新显示完成")
            except Exception as e:
                print(f"强制更新显示失败: {e}")
    
    def clear_all_status(self) -> None:
        """清除所有状态"""
        self.preserved_selection = None
        self.status_clear_time = 0
        print("✓ 所有状态已清除")