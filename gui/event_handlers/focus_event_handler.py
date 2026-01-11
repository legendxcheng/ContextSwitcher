"""
番茄钟专注计时器事件处理器

处理专注计时器的启动、暂停、恢复和显示更新
"""

from typing import Dict, Any

from gui.event_handlers.base_handler import BaseEventHandler
from gui.interfaces.event_interfaces import IWindowActions


class FocusEventHandler(BaseEventHandler):
    """番茄钟专注计时器事件处理器

    处理番茄钟按钮点击和计时器显示更新
    """

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化番茄钟事件处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        super().__init__(task_manager, window_actions, data_provider)

        # 事件路由映射
        self.event_handlers = {
            "-FOCUS-": self._handle_focus_timer,
        }

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理番茄钟相关事件"""
        handler = self.event_handlers.get(event)
        if handler:
            handler()
            return True
        return False

    def _handle_focus_timer(self):
        """处理番茄钟按钮点击"""
        try:
            from core.focus_timer import get_focus_timer, TimerState

            timer = get_focus_timer()
            window = self.get_window()

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
                self.set_status(f"🍅 开始专注: {task_name}", 3000)

            elif timer.state == TimerState.FOCUSING:
                # 停止专注
                session = timer.stop()
                if session:
                    duration_min = session.actual_duration // 60
                    self.set_status(f"⏹ 专注停止 ({duration_min}分钟)", 3000)
                else:
                    self.set_status("⏹ 专注已停止", 2000)

                # 隐藏计时器显示
                self._hide_focus_display(window)

            elif timer.state == TimerState.PAUSED:
                # 恢复
                timer.resume()
                self._update_focus_display(window, timer)
                self.set_status("▶ 专注已恢复", 2000)

        except Exception as e:
            print(f"番茄钟操作失败: {e}")
            import traceback
            traceback.print_exc()
            self.set_status("番茄钟操作失败", 3000)

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
            window = self.get_window()

            if timer.state in (TimerState.FOCUSING, TimerState.BREAK):
                window["-FOCUS_TIMER-"].update(timer.get_display_time())

                # 检查是否完成
                if timer.remaining_seconds <= 0:
                    self._hide_focus_display(window)
                    if timer.state == TimerState.FOCUSING:
                        self.set_status("🍅 专注完成!", 5000)
                    else:
                        self.set_status("☕ 休息结束!", 3000)
        except:
            pass
