"""
任务切换器布局创建模块

负责创建任务切换器的UI布局：
- 主窗口布局
- 任务行布局
- 空任务行布局
"""

from typing import List, Any
from core.task_manager import Task
try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise


class SwitcherLayout:
    """任务切换器布局创建类"""

    def __init__(self, config):
        """初始化布局创建器

        Args:
            config: SwitcherConfig配置实例
        """
        self.config = config

    def create_layout(self, tasks: List[Task], selected_index: int) -> List[List[Any]]:
        """创建窗口布局

        Args:
            tasks: 任务列表
            selected_index: 当前选中的任务索引

        Returns:
            窗口布局列表
        """
        layout = []
        fonts = self.config.fonts
        colors = self.config.colors

        # 标题行
        title_row = [
            sg.Text("任务切换器", font=fonts['task_title'],
                   text_color=colors['text'], pad=(0, 5))
        ]
        layout.append(title_row)

        # 分隔线
        layout.append([sg.HorizontalSeparator()])

        # 任务列表区域
        task_list_column = []

        for i in range(len(tasks)):
            task = tasks[i]
            task_row = self.create_task_row(i, task, selected_index)
            task_list_column.append(task_row)

        # 将任务列表放在列中（无滚动条）
        layout.append([
            sg.Column(
                task_list_column,
                expand_x=True,
                expand_y=False,
                scrollable=False,
                background_color=colors['background'],
                pad=(0, 5)
            )
        ])

        # 分隔线
        layout.append([sg.HorizontalSeparator()])

        # 底部操作说明（带倒计时显示）
        instruction_row = [
            sg.Text("↑↓ 选择 | 回车确认 | ESC取消",
                   font=fonts['instruction'],
                   text_color=colors['text_secondary'],
                   pad=(0, 5)),
            sg.Push(),
            sg.Text("⏱", font=fonts['status'], text_color=colors['warning']),
            sg.Text("2.0", key="-COUNTDOWN-", font=fonts['status'],
                   text_color=colors['warning'], size=(3, 1)),
            sg.Text("秒", font=fonts['instruction'], text_color=colors['text_secondary'])
        ]
        layout.append(instruction_row)

        return layout

    def create_task_row(self, index: int, task: Task, selected_index: int) -> List[Any]:
        """创建任务行（显示编号和任务名）

        Args:
            index: 任务索引
            task: 任务对象
            selected_index: 当前选中的任务索引

        Returns:
            任务行元素列表
        """
        is_selected = (index == selected_index)
        colors = self.config.colors
        fonts = self.config.fonts

        # 选中状态的颜色配置
        if is_selected:
            bg_color = colors['primary']      # 蓝色背景
            text_color = '#FFFFFF'            # 白色文字
            hotkey_color = '#FFFFFF'          # 白色编号
            prefix = "▶ "                     # 播放符号
            border_width = 2
            relief = sg.RELIEF_RAISED
        else:
            bg_color = colors['surface']      # 默认背景
            text_color = colors['text']       # 默认文字
            hotkey_color = colors['primary']  # 蓝色编号
            prefix = "  "                     # 空格
            border_width = 1
            relief = sg.RELIEF_FLAT

        # 任务编号
        hotkey_text = sg.Text(
            f"[{index + 1}]",
            font=fonts['hotkey'],
            text_color=hotkey_color,
            size=(3, 1),
            key=f"-HOTKEY-{index}-",
            background_color=bg_color
        )

        # 任务名称（加上选中指示符）
        display_name = f"{prefix}{task.name}"
        task_name = sg.Text(
            display_name,
            font=fonts['task_title'],
            text_color=text_color,
            size=(25, 1),
            key=f"-TASK_NAME-{index}-",
            background_color=bg_color
        )

        # 创建任务行
        row_elements = [hotkey_text, task_name]

        return [sg.Frame(
            "",
            [row_elements],
            border_width=border_width,
            background_color=bg_color,
            key=f"-TASK_ROW-{index}-",
            expand_x=True,
            element_justification='left',
            pad=(4, 0),
            relief=relief
        )]

    def create_empty_task_row(self, index: int) -> List[Any]:
        """创建空任务行

        Args:
            index: 空槽位索引

        Returns:
            空任务行元素列表
        """
        colors = self.config.colors
        fonts = self.config.fonts

        hotkey_text = sg.Text(
            f"[{index + 1}]",
            font=fonts['hotkey'],
            text_color=colors['text_disabled'],
            size=(4, 1),
            background_color=colors['background']
        )

        empty_text = sg.Text(
            "  （空）",
            font=fonts['task_info'],
            text_color=colors['text_disabled'],
            size=(35, 1),
            background_color=colors['background']
        )

        return [sg.Frame(
            "",
            [[hotkey_text, empty_text]],
            border_width=1,
            background_color=colors['background'],
            key=f"-EMPTY_ROW-{index}-",
            expand_x=True,
            element_justification='left',
            pad=(8, 6),
            relief=sg.RELIEF_FLAT
        )]
