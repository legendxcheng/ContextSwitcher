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

from utils.popup_helper import PopupManager


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
        
        # 弹窗管理器
        self.popup_manager = PopupManager(window_actions.get_window())
        
        # 拖拽状态跟踪
        self.window_was_dragged = False
        
        # 选中状态保存
        self.preserved_selection = None
        
        # 番茄钟计时器
        self.focus_timer = None

        # 数据提供器引用（用于搜索筛选）
        self.data_provider = None

        # 事件路由映射
        self.event_handlers = {
            "-ADD_TASK-": self._handle_add_task,
            "-EDIT_TASK-": self._handle_edit_task,
            "-DELETE_TASK-": self._handle_delete_task,
            "-REFRESH-": self._handle_refresh,
            "-SETTINGS-": self._handle_settings,
            "-FOCUS-": self._handle_focus_timer,
            "-STATS-": self._handle_stats,
            "-SEARCH-": self._handle_search,
            "-FILTER_STATUS-": self._handle_filter_status,
            "-TASK_TABLE-": self._handle_table_selection,
            "-TASK_TABLE- Double": self._handle_table_double_click,
            "-HOTKEY_TRIGGERED-": self._handle_hotkey_switcher_triggered,
            "-HOTKEY_ERROR-": self._handle_hotkey_error,
            "-HELP-": self._handle_help,
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
                           "-TASK_TABLE- Double", "-HOTKEY_ERROR-",
                           "-SEARCH-", "-FILTER_STATUS-"]:
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

    def set_data_provider(self, data_provider):
        """设置数据提供器引用"""
        self.data_provider = data_provider
    
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
                self.popup_manager.show_message("请先选择要编辑的任务", "提示")
                return

            table_row = selected_rows[0]

            # 转换为原始任务索引
            task_index = table_row
            if self.data_provider:
                orig_idx = self.data_provider.get_original_index(table_row)
                if orig_idx >= 0:
                    task_index = orig_idx

            task = self.task_manager.get_task_by_index(task_index)

            if not task:
                self.popup_manager.show_error("任务不存在", "错误")
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
                self.popup_manager.show_message("请先选择要删除的任务", "提示")
                return

            table_row = selected_rows[0]

            # 转换为原始任务索引
            task_index = table_row
            if self.data_provider:
                orig_idx = self.data_provider.get_original_index(table_row)
                if orig_idx >= 0:
                    task_index = orig_idx

            task = self.task_manager.get_task_by_index(task_index)

            if not task:
                self.popup_manager.show_error("任务不存在", "错误")
                return

            # 确认删除
            result = self.popup_manager.show_question(
                f"确定要删除任务 '{task.name}' 吗？\n\n此操作无法撤销。",
                "确认删除"
            )

            if result:
                if self.task_manager.remove_task(task.id):
                    self.window_actions.update_display()
                    self.window_actions.set_status("任务删除成功", 3000)
                else:
                    self.popup_manager.show_error("删除任务失败", "错误")

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
            self.popup_manager.show_message("设置功能开发中...", "设置")
        except Exception as e:
            print(f"打开设置失败: {e}")
            self.popup_manager.show_error(f"打开设置失败: {e}", "错误")

    def _handle_search(self, values: Dict[str, Any]):
        """处理搜索输入"""
        try:
            search_text = values.get("-SEARCH-", "")
            if self.data_provider:
                self.data_provider.set_search_text(search_text)
                self.window_actions.update_display()
        except Exception as e:
            print(f"搜索处理失败: {e}")

    def _handle_filter_status(self, values: Dict[str, Any]):
        """处理状态筛选"""
        try:
            status_filter = values.get("-FILTER_STATUS-", "全部")
            if self.data_provider:
                self.data_provider.set_status_filter(status_filter)
                self.window_actions.update_display()
                self.window_actions.set_status(f"筛选: {status_filter}", 2000)
        except Exception as e:
            print(f"筛选处理失败: {e}")

    def _handle_stats(self):
        """处理统计按钮 - 显示生产力统计"""
        try:
            from core.time_tracker import get_time_tracker
            from utils.config import get_config

            time_tracker = get_time_tracker()
            config = get_config()
            productivity_config = config.get_productivity_config()

            # 获取统计数据
            today_seconds = time_tracker.get_today_total()
            today_hours = today_seconds // 3600
            today_mins = (today_seconds % 3600) // 60

            week_seconds = time_tracker.get_week_total()
            week_hours = week_seconds // 3600
            week_mins = (week_seconds % 3600) // 60

            # 获取目标
            daily_goal = productivity_config.get("daily_goal_minutes", 120)
            daily_progress = (today_seconds / 60 / daily_goal * 100) if daily_goal > 0 else 0

            # 获取任务统计
            tasks = self.task_manager.get_all_tasks()
            task_count = len(tasks)
            completed_count = sum(1 for t in tasks if t.status.value == "completed")

            # 找出今日最专注的任务
            top_task = "无"
            top_time = 0
            for task in tasks:
                stats = time_tracker.get_task_stats(task.id)
                if stats.today_seconds > top_time:
                    top_time = stats.today_seconds
                    top_task = task.name[:15] + ".." if len(task.name) > 15 else task.name

            top_time_display = f"{top_time // 60}m" if top_time > 0 else "-"

            # 构建统计消息
            stats_msg = f"""📊 生产力统计

━━━ 今日 ━━━
专注时间: {today_hours}h {today_mins}m
目标进度: {daily_progress:.0f}%
最专注任务: {top_task} ({top_time_display})

━━━ 本周 ━━━
总专注: {week_hours}h {week_mins}m

━━━ 任务 ━━━
总任务数: {task_count}
已完成: {completed_count}"""

            self.popup_manager.show_message(stats_msg, "生产力统计")

        except Exception as e:
            print(f"显示统计失败: {e}")
            import traceback
            traceback.print_exc()
            self.window_actions.set_status("统计加载失败", 3000)

    def _handle_table_selection(self, values: Dict[str, Any]):
        """处理表格选择事件"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if selected_rows:
                table_row = selected_rows[0]
                # 保存选中状态（表格行号）
                self.preserved_selection = table_row

                # 转换为原始任务索引
                task_index = table_row
                if self.data_provider:
                    orig_idx = self.data_provider.get_original_index(table_row)
                    if orig_idx >= 0:
                        task_index = orig_idx

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

            table_row = selected_rows[0]

            # 转换为原始任务索引
            task_index = table_row
            if self.data_provider:
                orig_idx = self.data_provider.get_original_index(table_row)
                if orig_idx >= 0:
                    task_index = orig_idx

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
            # window_actions 就是 MainWindow 实例（实现了 IWindowActions 接口）
            # 回调 on_hotkey_switcher_triggered 是设置在 MainWindow 实例上的
            main_window = self.window_actions
            if hasattr(main_window, 'on_hotkey_switcher_triggered') and main_window.on_hotkey_switcher_triggered:
                main_window.on_hotkey_switcher_triggered()
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

    def _handle_focus_timer(self):
        """处理番茄钟按钮点击"""
        try:
            from core.focus_timer import get_focus_timer, TimerState

            timer = get_focus_timer()
            window = self.window_actions.get_window()

            if timer.state == TimerState.IDLE:
                # 开始新的专注
                # 获取当前选中的任务
                task_name = "专注时间"
                task_id = None

                current_task = self.task_manager.get_current_task()
                if current_task:
                    task_name = current_task.name
                    task_id = current_task.id

                timer.start_focus(task_id, task_name)

                # 更新UI显示
                self._update_focus_display(window, timer)
                self.window_actions.set_status(f"🍅 开始专注: {task_name}", 3000)

            elif timer.state == TimerState.FOCUSING:
                # 停止专注
                session = timer.stop()
                if session:
                    duration_min = session.actual_duration // 60
                    self.window_actions.set_status(f"⏹ 专注停止 ({duration_min}分钟)", 3000)
                else:
                    self.window_actions.set_status("⏹ 专注已停止", 2000)

                # 隐藏计时器显示
                self._hide_focus_display(window)

            elif timer.state == TimerState.PAUSED:
                # 恢复
                timer.resume()
                self._update_focus_display(window, timer)
                self.window_actions.set_status("▶ 专注已恢复", 2000)

        except Exception as e:
            print(f"番茄钟操作失败: {e}")
            import traceback
            traceback.print_exc()
            self.window_actions.set_status("番茄钟操作失败", 3000)

    def _update_focus_display(self, window, timer):
        """更新番茄钟显示"""
        try:
            # 显示计时器
            window["-FOCUS_ICON-"].update(visible=True)
            window["-FOCUS_TIMER-"].update(timer.get_display_time(), visible=True)
        except:
            pass

    def _hide_focus_display(self, window):
        """隐藏番茄钟显示"""
        try:
            window["-FOCUS_ICON-"].update(visible=False)
            window["-FOCUS_TIMER-"].update("--:--", visible=False)
        except:
            pass

    def update_focus_timer_display(self):
        """更新番茄钟计时显示（在主循环中调用）"""
        try:
            from core.focus_timer import get_focus_timer, TimerState

            timer = get_focus_timer()
            window = self.window_actions.get_window()

            if timer.state in (TimerState.FOCUSING, TimerState.BREAK):
                window["-FOCUS_TIMER-"].update(timer.get_display_time())

                # 检查是否完成
                if timer.remaining_seconds <= 0:
                    self._hide_focus_display(window)
                    if timer.state == TimerState.FOCUSING:
                        self.window_actions.set_status("🍅 专注完成!", 5000)
                    else:
                        self.window_actions.set_status("☕ 休息结束!", 3000)
        except:
            pass

    def _handle_help(self):
        """显示帮助信息"""
        try:
            from utils.config import get_config
            config = get_config()

            # 获取当前快捷键配置
            hotkey_config = config.get_hotkeys_config()
            modifiers = hotkey_config.get('switcher_modifiers', ['ctrl', 'alt'])
            key = hotkey_config.get('switcher_key', 'space')

            # 格式化快捷键显示
            mod_display = '+'.join([m.title() for m in modifiers])
            key_display = key.title() if key else "Space"
            hotkey_display = f"{mod_display}+{key_display}"

            help_text = f"""ContextSwitcher 快捷操作指南

━━━ 快捷键 ━━━
{hotkey_display}  快速切换任务

━━━ 鼠标操作 ━━━
双击任务     切换到该任务的窗口
单击任务     选中任务

━━━ 按钮说明 ━━━
＋  添加新任务
✎  编辑选中任务
✕  删除选中任务
🍅  番茄钟专注
📊  查看统计
⚙  打开设置

━━━ 提示 ━━━
• 可在设置中自定义快捷键
• 支持一个任务绑定多个窗口
• Explorer窗口会自动记住路径"""

            self.popup_manager.show_message(help_text, "帮助")

        except Exception as e:
            print(f"显示帮助失败: {e}")
            self.window_actions.set_status("帮助加载失败", 3000)