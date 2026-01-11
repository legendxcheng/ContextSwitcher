"""
任务切换器UI更新模块

负责更新任务切换器的UI显示：
- 选中状态更新
- 倒计时显示更新
- 选中位置移动
"""

from typing import List, Optional
from core.task_manager import Task
try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise


class SwitcherUIUpdater:
    """任务切换器UI更新类"""

    def __init__(self, config):
        """初始化UI更新器

        Args:
            config: SwitcherConfig配置实例
        """
        self.config = config
        self.selected_index = 0

    def set_selected_index(self, index: int):
        """设置选中的任务索引

        Args:
            index: 任务索引
        """
        self.selected_index = index

    def update_selection_display(self, window, tasks: List[Task]):
        """更新选中状态的显示

        Args:
            window: FreeSimpleGUI窗口对象
            tasks: 任务列表
        """
        if not window:
            return

        try:
            # 简化版本：只更新文字内容，避免颜色更新导致的API错误
            for i in range(min(9, len(tasks))):
                task = tasks[i]
                is_selected = (i == self.selected_index)

                # 更新任务名称显示
                task_name_key = f"-TASK_NAME-{i}-"

                if task_name_key in window.AllKeysDict:
                    # 更新任务名称显示（只更新文字内容）
                    if is_selected:
                        display_name = f"▶ {task.name}"
                    else:
                        display_name = f"  {task.name}"

                    # 只更新文字内容，避免颜色更新
                    window[task_name_key].update(value=display_name)

        except Exception as e:
            print(f"更新选中状态显示失败: {e}")

    def update_countdown_display(self, window, remaining_time: float):
        """更新倒计时显示

        Args:
            window: FreeSimpleGUI窗口对象
            remaining_time: 剩余时间（秒）
        """
        if not window:
            return

        try:
            countdown_key = "-COUNTDOWN-"
            if countdown_key in window.AllKeysDict:
                # 格式化显示
                display_text = f"{remaining_time:.1f}"

                # 根据剩余时间改变颜色
                colors = self.config.colors
                if remaining_time <= 0.5:
                    color = colors['error']      # 红色 - 即将切换
                elif remaining_time <= 1.0:
                    color = colors['warning']    # 橙色 - 警告
                else:
                    color = colors['primary']    # 蓝色 - 正常

                window[countdown_key].update(display_text, text_color=color)
        except:
            pass  # 忽略更新失败

    def move_selection(self, direction: int, task_count: int) -> int:
        """移动选中位置

        Args:
            direction: 移动方向（-1向上，1向下）
            task_count: 任务总数

        Returns:
            新的选中索引
        """
        if task_count == 0:
            return self.selected_index

        try:
            new_index = self.selected_index + direction

            # 循环选择
            if new_index < 0:
                new_index = task_count - 1
            elif new_index >= task_count:
                new_index = 0

            self.selected_index = new_index
            return self.selected_index

        except Exception as e:
            print(f"移动选择失败: {e}")
            return self.selected_index
