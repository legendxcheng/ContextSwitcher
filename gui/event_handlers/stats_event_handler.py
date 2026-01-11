"""
生产力统计事件处理器

处理统计数据获取和显示
"""

from typing import Dict, Any

from gui.event_handlers.base_handler import BaseEventHandler
from gui.interfaces.event_interfaces import IWindowActions
from utils.popup_helper import PopupManager


class StatsEventHandler(BaseEventHandler):
    """生产力统计事件处理器

    处理统计按钮点击，获取并显示生产力统计数据
    """

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化统计事件处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        super().__init__(task_manager, window_actions, data_provider)
        self.popup_manager = PopupManager(window_actions.get_window())

        # 事件路由映射
        self.event_handlers = {
            "-STATS-": self._handle_stats,
        }

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理统计相关事件"""
        handler = self.event_handlers.get(event)
        if handler:
            handler()
            return True
        return False

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
            self.set_status("统计加载失败", 3000)
