"""
业务动作调度器模块

负责协调各个组件间的业务逻辑和状态管理
从MainWindow中提取剩余的业务逻辑，完成重构
"""

import time
from typing import Optional
from abc import ABC, abstractmethod

from core.task_manager import Task
from core.time_tracker import get_time_tracker


class IActionDispatcher(ABC):
    """业务动作调度器接口"""

    @abstractmethod
    def update_display(self) -> None:
        """更新显示"""
        pass

    @abstractmethod
    def set_status(self, message: str, duration_ms: int = 0, status_type: str = "info") -> None:
        """设置状态消息"""
        pass

    @abstractmethod
    def set_status_success(self, message: str, duration_ms: int = 3000) -> None:
        """设置成功状态消息"""
        pass

    @abstractmethod
    def set_status_warning(self, message: str, duration_ms: int = 3000) -> None:
        """设置警告状态消息"""
        pass

    @abstractmethod
    def set_status_error(self, message: str, duration_ms: int = 5000) -> None:
        """设置错误状态消息"""
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
    
    @abstractmethod
    def get_data_storage(self):
        """获取数据存储管理器"""
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
        
        # 自动保存统计
        self.auto_save_count = 0  # 自动保存次数
        self.auto_save_fail_count = 0  # 失败次数
        self.last_auto_save_time = 0  # 上次保存时间戳
        
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
        time_tracker = get_time_tracker()

        if current_task:
            status = f"当前: {current_task.name}"
        else:
            status = f"{task_count} 个任务"

        if self._has_status_element(window):
            window["-STATUS-"].update(status)

        # 更新今日总专注时间和目标进度
        today_total = time_tracker.get_today_display()
        today_seconds = time_tracker.get_today_total()
        try:
            window["-TODAY_TOTAL-"].update(today_total)

            # 获取每日目标配置
            from utils.config import get_config
            config = get_config()
            productivity_config = config.get_productivity_config()
            daily_goal_minutes = productivity_config.get("daily_goal_minutes", 120)
            daily_goal_seconds = daily_goal_minutes * 60

            # 更新目标显示
            goal_hours = daily_goal_minutes // 60
            goal_mins = daily_goal_minutes % 60
            goal_display = f"{goal_hours}h" if goal_mins == 0 else f"{goal_hours}h{goal_mins}m"
            window["-DAILY_GOAL-"].update(goal_display)

            # 根据完成比例更新颜色
            progress = today_seconds / daily_goal_seconds if daily_goal_seconds > 0 else 0
            if progress >= 1.0:
                # 目标达成 - 绿色
                window["-TODAY_TOTAL-"].update(text_color="#00DD00")
            elif progress >= 0.5:
                # 过半 - 蓝色
                window["-TODAY_TOTAL-"].update(text_color="#0078D4")
            else:
                # 未过半 - 保持默认
                window["-TODAY_TOTAL-"].update(text_color="#0078D4")

            # 更新快捷键提示
            self._update_hotkey_hint(window, config)
        except:
            pass  # 忽略键不存在的错误（向后兼容）

    def _update_hotkey_hint(self, window, config) -> None:
        """更新快捷键提示显示"""
        try:
            hotkey_config = config.get_hotkeys_config()
            modifiers = hotkey_config.get('switcher_modifiers', ['ctrl', 'alt'])
            key = hotkey_config.get('switcher_key', 'space')

            # 格式化快捷键显示（简短形式）
            mod_abbrev = {
                'ctrl': 'C',
                'alt': 'A',
                'shift': 'S',
                'win': 'W'
            }
            key_abbrev = {
                'space': '空格',
                'tab': 'Tab',
                'enter': '回车'
            }

            mod_display = '+'.join([mod_abbrev.get(m, m[0].upper()) for m in modifiers])
            key_display = key_abbrev.get(key, key.title())
            hotkey_display = f"{mod_display}+{key_display}"

            window["-HOTKEY_HINT-"].update(hotkey_display)
        except:
            pass
    
    def set_status(self, message: str, duration_ms: int = 0, status_type: str = "info") -> None:
        """设置状态消息（支持不同类型和颜色）

        Args:
            message: 状态消息
            duration_ms: 显示时长（毫秒），0表示永久显示
            status_type: 消息类型 (info/success/warning/error)
        """
        window = self.action_provider.get_window()
        if not window:
            return
        if not self._has_status_element(window):
            return

        try:
            # 根据消息类型设置颜色
            status_colors = {
                "info": "#FFFFFF",      # 白色 - 普通信息
                "success": "#00FF00",   # 绿色 - 成功
                "warning": "#FFD700",   # 金色 - 警告
                "error": "#FF6B6B",     # 红色 - 错误
            }

            text_color = status_colors.get(status_type, "#FFFFFF")

            # 添加类型前缀
            prefix_map = {
                "success": "✅ ",
                "warning": "⚠️ ",
                "error": "❌ ",
                "info": ""
            }
            prefix = prefix_map.get(status_type, "")

            # 更新状态消息（不重复添加前缀）
            display_message = message
            if status_type != "info" and not any(message.startswith(p) for p in prefix_map.values()):
                display_message = prefix + message

            window["-STATUS-"].update(display_message, text_color=text_color)

            if duration_ms > 0:
                # 记录状态清除时间，让主事件循环处理
                self.status_clear_time = time.time() + (duration_ms / 1000.0)

        except Exception as e:
            print(f"设置状态失败: {e}")

    def set_status_success(self, message: str, duration_ms: int = 3000) -> None:
        """设置成功状态消息"""
        self.set_status(message, duration_ms, "success")

    def set_status_warning(self, message: str, duration_ms: int = 3000) -> None:
        """设置警告状态消息"""
        self.set_status(message, duration_ms, "warning")

    def set_status_error(self, message: str, duration_ms: int = 5000) -> None:
        """设置错误状态消息"""
        self.set_status(message, duration_ms, "error")
    
    def on_task_changed(self, task: Task) -> None:
        """任务变化回调"""
        if self.action_provider.is_running():
            # 任务发生变化时，清除保存的选中状态以避免索引错位
            self.preserved_selection = None
            event_controller = self.action_provider.get_event_controller()
            if event_controller:
                event_controller.set_preserved_selection(None)
            self.update_display()
            
            # 立即自动保存任务数据
            self._auto_save_tasks()
    
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
                if window and self._has_status_element(window):
                    window["-STATUS-"].update("就绪")
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
        from datetime import datetime
        
        return {
            "preserved_selection": self.preserved_selection,
            "status_clear_time": self.status_clear_time,
            "next_clear_in": max(0, self.status_clear_time - time.time()) if self.status_clear_time > 0 else 0,
            "is_running": self.action_provider.is_running(),
            # 自动保存统计
            "auto_save_count": self.auto_save_count,
            "auto_save_fail_count": self.auto_save_fail_count,
            "last_auto_save_time": datetime.fromtimestamp(self.last_auto_save_time).isoformat() if self.last_auto_save_time > 0 else "从未保存",
            "auto_save_success_rate": f"{(self.auto_save_count / (self.auto_save_count + self.auto_save_fail_count) * 100):.1f}%" if (self.auto_save_count + self.auto_save_fail_count) > 0 else "N/A"
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

    def _has_status_element(self, window) -> bool:
        """检查状态显示组件是否存在"""
        try:
            return window is not None and "-STATUS-" in window.AllKeysDict
        except Exception:
            return False
    
    def _auto_save_tasks(self) -> bool:
        """自动保存任务数据（线程安全）
        
        Returns:
            是否成功保存
        """
        try:
            # 获取数据存储管理器
            data_storage = self.action_provider.get_data_storage()
            
            # 检查数据存储是否存在
            if data_storage is None:
                print("⚠️ [AutoSave] 数据存储管理器未初始化，跳过自动保存")
                return False
            
            # 获取任务管理器
            task_manager = self.action_provider.get_task_manager()
            if task_manager is None:
                print("⚠️ [AutoSave] 任务管理器未初始化，跳过自动保存")
                return False
            
            # 获取所有任务
            tasks = task_manager.get_all_tasks()
            
            # 记录开始时间（用于性能监控）
            start_time = time.time()
            
            # 执行保存
            print(f"[AutoSave] 检测到任务变更，准备自动保存 {len(tasks)} 个任务...")
            success = data_storage.save_tasks(tasks)
            
            # 计算耗时
            elapsed_ms = (time.time() - start_time) * 1000
            
            if success:
                # 更新统计信息
                self.auto_save_count += 1
                self.last_auto_save_time = time.time()
                
                print(f"[AutoSave] ✓ 成功保存 {len(tasks)} 个任务（耗时 {elapsed_ms:.1f} ms）[总计: {self.auto_save_count} 次]")
                return True
            else:
                # 更新失败统计
                self.auto_save_fail_count += 1
                
                print(f"[AutoSave] ✗ 保存失败（耗时 {elapsed_ms:.1f} ms）[失败: {self.auto_save_fail_count} 次]")
                # 通过状态栏提示用户
                self.set_status("⚠️ 自动保存失败，请检查磁盘空间和权限", 5000)
                return False
                
        except Exception as e:
            print(f"[AutoSave] ✗ 自动保存异常: {e}")
            import traceback
            traceback.print_exc()
            # 通过状态栏提示用户
            self.set_status(f"⚠️ 自动保存异常: {str(e)}", 5000)
            return False
