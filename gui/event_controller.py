"""
事件控制器模块

负责主窗口所有事件处理逻辑
从MainWindow中提取，遵循单一职责原则
"""

from typing import Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    print("运行: pip install FreeSimpleGUI")
    raise


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
    """窗口动作接口 - 定义EventController需要的回调方法"""
    
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


class EventController(IEventHandler):
    """事件控制器实现"""
    
    def __init__(self, task_manager, window_actions: IWindowActions):
        """初始化事件控制器
        
        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
        """
        self.task_manager = task_manager
        self.window_actions = window_actions
        
        # 拖拽状态跟踪
        self.window_was_dragged = False
        
        # 选中状态保存
        self.preserved_selection = None
        
        # 事件路由映射
        self.event_handlers = {
            "-ADD_TASK-": self._handle_add_task,
            "-EDIT_TASK-": self._handle_edit_task,
            "-DELETE_TASK-": self._handle_delete_task,
            "-REFRESH-": self._handle_refresh,
            "-SETTINGS-": self._handle_settings,
            "-TASK_TABLE-": self._handle_table_selection,
            "-TASK_TABLE- Double": self._handle_table_double_click,
            "-HOTKEY_TRIGGERED-": self._handle_hotkey_switcher_triggered,
            "-HOTKEY_ERROR-": self._handle_hotkey_error,
        }
    
    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """统一事件处理入口"""
        try:
            # 检查是否需要忽略拖拽导致的误触
            if self._should_ignore_due_to_drag(event):
                self.window_was_dragged = False  # 重置拖拽状态
                return True
            
            # 路由到具体的事件处理器
            handler = self.event_handlers.get(event)
            if handler:
                if event in ["-EDIT_TASK-", "-DELETE_TASK-", "-TASK_TABLE-", 
                           "-TASK_TABLE- Double", "-HOTKEY_ERROR-"]:
                    # 需要values参数的处理器
                    handler(values)
                else:
                    # 不需要values参数的处理器
                    handler()
                return True
            
            return False  # 事件未处理
            
        except Exception as e:
            print(f"事件处理失败 [{event}]: {e}")
            return False
    
    def _should_ignore_due_to_drag(self, event: str) -> bool:
        """检查是否应该因拖拽而忽略事件"""
        drag_sensitive_events = ["-CLOSE-", "-ADD_TASK-", "-EDIT_TASK-", 
                               "-DELETE_TASK-", "-SETTINGS-"]
        return self.window_was_dragged and event in drag_sensitive_events
    
    def set_drag_state(self, dragged: bool):
        """设置拖拽状态"""
        self.window_was_dragged = dragged
    
    def set_preserved_selection(self, selection):
        """设置保存的选中状态"""
        self.preserved_selection = selection
    
    def get_preserved_selection(self):
        """获取保存的选中状态"""
        return self.preserved_selection
    
    def _handle_add_task(self):
        """处理添加任务"""
        try:
            print("点击了添加任务按钮")  # 调试信息
            from gui.task_dialog import TaskDialog
            
            window = self.window_actions.get_window()
            dialog = TaskDialog(window, self.task_manager)
            result = dialog.show_add_dialog()
            
            if result:
                self.window_actions.update_display()
                self.window_actions.set_status("任务添加成功", 3000)
                print("任务添加成功")
            else:
                print("任务添加取消")
            
        except Exception as e:
            print(f"添加任务失败: {e}")
            import traceback
            traceback.print_exc()
            self.window_actions.set_status("添加任务失败", 3000)
    
    def _handle_edit_task(self, values: Dict[str, Any]):
        """处理编辑任务"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                sg.popup("请先选择要编辑的任务", title="提示")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                sg.popup("任务不存在", title="错误")
                return
            
            from gui.task_dialog import TaskDialog
            
            window = self.window_actions.get_window()
            dialog = TaskDialog(window, self.task_manager)
            result = dialog.show_edit_dialog(task)
            
            if result:
                self.window_actions.update_display()
                self.window_actions.set_status("任务编辑成功", 3000)
            
        except Exception as e:
            print(f"编辑任务失败: {e}")
            self.window_actions.set_status("编辑任务失败", 3000)
    
    def _handle_delete_task(self, values: Dict[str, Any]):
        """处理删除任务"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                sg.popup("请先选择要删除的任务", title="提示")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                sg.popup("任务不存在", title="错误")
                return
            
            # 确认删除
            result = sg.popup_yes_no(
                f"确定要删除任务 '{task.name}' 吗？\\n\\n此操作无法撤销。",
                title="确认删除"
            )
            
            if result == "Yes":
                if self.task_manager.remove_task(task.id):
                    self.window_actions.update_display()
                    self.window_actions.set_status("任务删除成功", 3000)
                else:
                    sg.popup("删除任务失败", title="错误")
            
        except Exception as e:
            print(f"删除任务失败: {e}")
            self.window_actions.set_status("删除任务失败", 3000)
    
    def _handle_refresh(self):
        """处理刷新"""
        try:
            # 验证所有任务的窗口绑定
            invalid_windows = self.task_manager.validate_all_tasks()
            
            if invalid_windows:
                total_invalid = sum(len(windows) for windows in invalid_windows.values())
                self.window_actions.set_status(f"发现 {total_invalid} 个失效窗口", 3000)
            
            self.window_actions.update_display()
            self.window_actions.set_status("刷新完成", 2000)
            
        except Exception as e:
            print(f"刷新失败: {e}")
            self.window_actions.set_status("刷新失败", 3000)
    
    def _handle_settings(self):
        """处理设置"""
        try:
            from gui.settings_dialog import SettingsDialog
            
            window = self.window_actions.get_window()
            dialog = SettingsDialog(window, self.task_manager)
            result = dialog.show_settings_dialog()
            
            if result:
                self.window_actions.update_display()
                self.window_actions.set_status("设置已保存", 3000)
                print("✓ 设置已保存并应用")
            
        except ImportError:
            sg.popup("设置功能开发中...", title="设置")
        except Exception as e:
            print(f"打开设置失败: {e}")
            sg.popup(f"打开设置失败: {e}", title="错误")
    
    def _handle_table_selection(self, values: Dict[str, Any]):
        """处理表格选择事件"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if selected_rows:
                task_index = selected_rows[0]
                # 保存选中状态
                self.preserved_selection = task_index
                
                task = self.task_manager.get_task_by_index(task_index)
                if task:
                    self.window_actions.set_status(f"已选择: {task.name}", 2000)
            else:
                # 清除选中状态
                self.preserved_selection = None
            
        except Exception as e:
            print(f"处理表格选择失败: {e}")
    
    def _handle_table_double_click(self, values: Dict[str, Any]):
        """处理表格双击事件 - 切换到任务窗口"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                print("⚠️ 双击事件：没有选中的任务")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                print(f"⚠️ 找不到索引为 {task_index} 的任务")
                return
            
            print(f"🖱️ 双击任务: {task.name}")
            self.window_actions.set_status(f"正在切换到: {task.name}", 1000)
            
            # 使用任务管理器切换到该任务
            success = self.task_manager.switch_to_task(task_index)
            
            if success:
                print(f"✅ 成功切换到任务: {task.name}")
                self.window_actions.set_status(f"已切换到: {task.name}", 3000)
            else:
                print(f"❌ 切换任务失败: {task.name}")
                self.window_actions.set_status(f"切换失败: {task.name}", 3000)
            
        except Exception as e:
            print(f"处理表格双击失败: {e}")
            self.window_actions.set_status("切换任务失败", 2000)
    
    def _handle_hotkey_switcher_triggered(self):
        """处理热键线程发送的切换器触发事件（线程安全）"""
        try:
            # 获取主程序实例，通过回调来显示任务切换器
            # 这样避免直接在主窗口中操作任务切换器
            window = self.window_actions.get_window()
            if hasattr(window, '_app_instance') and window._app_instance:
                # 如果有应用实例的引用，调用其方法
                window._app_instance.show_task_switcher()
            else:
                # 备用方案：直接调用全局回调（如果设置了）
                if hasattr(window, 'on_hotkey_switcher_triggered') and window.on_hotkey_switcher_triggered:
                    window.on_hotkey_switcher_triggered()
                else:
                    print("⚠️ 未找到任务切换器回调方法")
            
        except Exception as e:
            print(f"处理热键切换器触发失败: {e}")
    
    def _handle_hotkey_error(self, values: Dict[str, Any]):
        """处理热键线程发送的错误事件（线程安全）"""
        try:
            error_msg = values.get("-HOTKEY_ERROR-", "未知热键错误")
            print(f"⚠️ 热键错误: {error_msg}")
            # 在主线程中安全地显示错误状态
            self.window_actions.set_status(f"热键错误: {error_msg}", 5000)
            
        except Exception as e:
            print(f"处理热键错误失败: {e}")