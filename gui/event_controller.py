"""
事件控制器模块

负责主窗口所有事件处理逻辑的协调和路由
采用模块化设计，将具体处理逻辑委托给专门的处理器
"""

from typing import Dict, Any

from gui.interfaces.event_interfaces import IEventHandler, IWindowActions
from gui.event_handlers.task_event_handler import TaskEventHandler
from gui.event_handlers.focus_event_handler import FocusEventHandler
from gui.event_handlers.stats_event_handler import StatsEventHandler
from gui.event_handlers.help_event_handler import HelpEventHandler
from gui.event_handlers.search_event_handler import SearchEventHandler
from gui.event_handlers.table_event_handler import TableEventHandler


class EventController(IEventHandler):
    """事件控制器实现

    作为事件处理的中央路由器，将事件分发到各个专门的处理器
    """

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

        # 初始化各个子处理器
        self.task_handler = TaskEventHandler(task_manager, window_actions)
        self.focus_handler = FocusEventHandler(task_manager, window_actions)
        self.stats_handler = StatsEventHandler(task_manager, window_actions)
        self.help_handler = HelpEventHandler(task_manager, window_actions)
        self.search_handler = SearchEventHandler(task_manager, window_actions)
        self.table_handler = TableEventHandler(task_manager, window_actions)

        # 所有处理���的列表（用于统一设置数据提供器）
        self._all_handlers = [
            self.task_handler,
            self.focus_handler,
            self.stats_handler,
            self.help_handler,
            self.search_handler,
            self.table_handler,
        ]

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """统一事件处理入口

        Args:
            event: 事件名称
            values: 事件值

        Returns:
            bool: True表示事件已处理，False表示需要进一步处理
        """
        try:
            # 检查是否需要忽略拖拽导致的误触
            if self._should_ignore_due_to_drag(event):
                self.window_was_dragged = False  # 重置拖拽状态
                return True

            # 路由到各个子处理器
            # 按优先级顺序处理：表格 > 任务 > 搜索 > 番茄钟 > 统计 > 帮助
            handlers = [
                self.table_handler,  # 表格事件（包括数字键）
                self.task_handler,   # 任务CRUD
                self.search_handler, # 搜索筛选
                self.focus_handler,  # 番茄钟
                self.stats_handler,  # 统计
                self.help_handler,   # 帮助
            ]

            for handler in handlers:
                if handler.handle_event(event, values):
                    return True

            # 处理其他事件
            if event == "-REFRESH-":
                self._handle_refresh()
                return True
            elif event == "-SETTINGS-":
                self._handle_settings()
                return True
            elif event == "-HOTKEY_TRIGGERED-":
                self._handle_hotkey_switcher_triggered()
                return True
            elif event == "-HOTKEY_ERROR-":
                self._handle_hotkey_error(values)
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

    def set_data_provider(self, data_provider):
        """设置数据提供器引用（分发给所有子处理器）"""
        for handler in self._all_handlers:
            handler.set_data_provider(data_provider)

    def set_preserved_selection(self, selection):
        """设置保存的选中状态"""
        self.table_handler.set_preserved_selection(selection)

    def get_preserved_selection(self):
        """获取保存的选中状态"""
        return self.table_handler.get_preserved_selection()

    def update_focus_timer_display(self):
        """更新番茄钟计时显示（在主循环中调用）"""
        self.focus_handler.update_focus_timer_display()

    def get_search_history(self) -> list:
        """获取搜索历史列表"""
        return self.search_handler.get_search_history()

    def clear_search_history(self):
        """清除搜索历史"""
        self.search_handler.clear_search_history()

    def is_undo_available(self) -> bool:
        """检查撤销是否可用"""
        return self.task_handler.is_undo_available()

    def get_undo_expiry_time(self) -> float:
        """获取撤销过期时间"""
        return self.task_handler.get_undo_expiry_time()

    # 以下是具体的事件处理方法

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
            from utils.popup_helper import PopupManager
            popup = PopupManager(self.window_actions.get_window())
            popup.show_message("设置功能开发中...", "设置")
        except Exception as e:
            print(f"打开设置失败: {e}")
            from utils.popup_helper import PopupManager
            popup = PopupManager(self.window_actions.get_window())
            popup.show_error(f"打开设置失败: {e}", "错误")

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
