"""
任务对话框布局构建器模块

负责创建任务对话框的各种布局组件
"""

from typing import List, Dict, Any, Optional
import FreeSimpleGUI as sg

from core.task_manager import TaskStatus
from gui.task_dialog.status_converter import TaskStatusConverter


class TaskDialogLayoutBuilder:
    """任务对话框布局构建器"""

    # 优先级选项
    PRIORITY_OPTIONS = ["普通", "低", "中", "高"]

    # 表格列配置
    TABLE_HEADINGS = ["选择", "优先级", "窗口标题", "进程", "句柄"]
    TABLE_COL_WIDTHS = [6, 8, 25, 12, 10]

    def __init__(self):
        """初始化布局构建器"""
        self.status_converter = TaskStatusConverter()

    def build_full_layout(
        self,
        task_name: str = "",
        task_description: str = "",
        task_wave_workspace: str = "",
        task_status: TaskStatus = TaskStatus.TODO,
        task_priority: int = 0,
        task_notes: str = "",
        task_tags: List[str] = None,
        selected_windows_display: List[str] = None
    ) -> List[List[Any]]:
        """构建完整的对话框布局

        Args:
            task_name: 任务名称
            task_description: 任务描述
            task_status: 任务状态
            task_priority: 任务优先级
            task_notes: 快速笔记
            task_tags: 标签列表
            selected_windows_display: 已选窗口显示列表

        Returns:
            完整布局
        """
        if task_tags is None:
            task_tags = []
        if selected_windows_display is None:
            selected_windows_display = []

        # 任务信息区域
        info_frame = self._build_task_info_frame(
            task_name, task_description, task_wave_workspace, task_status,
            task_priority, task_notes, task_tags
        )

        # 窗口选择区域
        window_frame = self._build_window_selection_frame(selected_windows_display)

        # 按钮区域
        button_row = self._build_button_row()

        # 主列
        main_column = [
            [sg.Frame("任务信息", info_frame, expand_x=True,
                     element_justification="left")],
            [sg.Frame("绑定窗口", window_frame, expand_x=True, expand_y=True)],
        ]

        # 完整布局
        layout = [
            [sg.Column(main_column, expand_x=True, expand_y=True,
                      scrollable=False, vertical_scroll_only=False,
                      size=(None, None))],
            [sg.HorizontalSeparator()],
            button_row
        ]

        return layout

    def _build_task_info_frame(
        self,
        task_name: str,
        task_description: str,
        task_wave_workspace: str,
        task_status: TaskStatus,
        task_priority: int,
        task_notes: str,
        task_tags: List[str]
    ) -> List[List[Any]]:
        """构建任务信息输入框区域

        Args:
            task_name: 任务名称
            task_description: 任务描述
            task_status: 任务状态
            task_priority: 任务优先级
            task_notes: 快速笔记
            task_tags: 标签列表

        Returns:
            任务信息框架布局
        """
        # 获取优先级默认值
        priority_default = self.PRIORITY_OPTIONS[task_priority] \
            if 0 <= task_priority < len(self.PRIORITY_OPTIONS) else "普通"

        # 标签显示文本（用逗号分隔）
        tags_display = ", ".join(task_tags) if task_tags else ""

        return [
            [sg.Text("任务名称:", size=(10, 1)),
             sg.Input(task_name, key="-TASK_NAME-", size=(40, 1))],
            [sg.Text("任务描述:", size=(10, 1)),
             sg.Multiline(task_description, key="-TASK_DESC-",
                         size=(40, 2), enable_events=True)],
            [sg.Text("Wave工作区:", size=(10, 1)),
             sg.Input(task_wave_workspace, key="-TASK_WAVE_WORKSPACE-", size=(40, 1),
                     tooltip="可选：填写 Wave workspace 名称，切换任务时自动切换")],
            [sg.Text("任务状态:", size=(10, 1)),
             sg.Combo(self.status_converter.get_all_status_options(),
                     default_value=self.status_converter.status_to_text(task_status),
                     key="-TASK_STATUS-", readonly=True, size=(12, 1)),
             sg.Text("优先级:", size=(6, 1)),
             sg.Combo(self.PRIORITY_OPTIONS,
                     default_value=priority_default,
                     key="-TASK_PRIORITY-", readonly=True, size=(8, 1))],
            [sg.Text("标签:", size=(10, 1)),
             sg.Input(tags_display, key="-TASK_TAGS-", size=(40, 1),
                     tooltip="用逗号分隔多个标签，例如: 前端, bug修复, 紧急")],
            [sg.Text("快速笔记:", size=(10, 1)),
             sg.Multiline(task_notes, key="-TASK_NOTES-",
                         size=(40, 2), enable_events=True,
                         tooltip="记录任务相关的快速笔记、链接或要点")]
        ]

    def _build_window_selection_frame(
        self,
        selected_windows_display: List[str]
    ) -> List[List[Any]]:
        """构建窗口选择区域

        Args:
            selected_windows_display: 已选窗口显示列表

        Returns:
            窗口选择框架布局
        """
        return [
            [sg.Text("选择要绑定到此任务的窗口:")],
            [sg.Text("操作: 1.双击窗口行直接添加  2.或点击选中后点击'添加选择'按钮",
                    font=("Arial", 9), text_color="#666666")],
            # 搜索行
            [sg.Text("🔍 搜索:", font=("Arial", 10), text_color="#0078D4"),
             sg.Input("", key="-WINDOW_FILTER-", size=(20, 1),
                     enable_events=True,
                     tooltip="输入关键词搜索窗口标题或进程名"),
             sg.Button("×", key="-CLEAR_FILTER-", size=(2, 1),
                      button_color=("#666666", "#F0F0F0"),
                      tooltip="清空搜索"),
             sg.Text("输入关键词过滤窗口", font=("Arial", 8), text_color="#888888")],
            [sg.Button("刷新窗口列表", key="-REFRESH_WINDOWS-", size=(12, 1),
                      button_color=("#FFFFFF", "#0078D4"),
                      font=("Segoe UI", 9), border_width=0),
             sg.Button("添加选择", key="-ADD_WINDOW-", size=(10, 1),
                      button_color=("#FFFFFF", "#107C10"),
                      font=("Segoe UI", 9), border_width=0),
             sg.Text("", key="-FILTER_COUNT-", size=(15, 1),
                    text_color="#666666", font=("Arial", 9))],
            [sg.Table(
                values=[],
                headings=self.TABLE_HEADINGS,
                key="-WINDOW_TABLE-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=self.TABLE_COL_WIDTHS,
                justification="left",
                alternating_row_color="#404040",
                selected_row_colors="#CCCCCC on #0078D4",
                header_background_color="#2D2D2D",
                header_text_color="#FFFFFF",
                font=("Arial", 9),
                num_rows=8,
                expand_x=True,
                expand_y=True
            )],
            [sg.Text("已选择窗口:", font=("Arial", 10, "bold"))],
            [sg.Listbox(
                values=selected_windows_display,
                key="-SELECTED_WINDOWS-",
                size=(50, 6),
                enable_events=True,
                expand_x=True,
                expand_y=True
            )],
            [sg.Button("移除选择", key="-REMOVE_WINDOW-", size=(10, 1),
                      button_color=("#FFFFFF", "#D13438"),
                      font=("Segoe UI", 9), border_width=0)]
        ]

    def _build_button_row(self) -> List[Any]:
        """构建按钮行

        Returns:
            按钮行布局
        """
        return [
            sg.Push(),
            sg.Button("确定", key="-OK-", size=(10, 1),
                     button_color=("#FFFFFF", "#107C10"),
                     font=("Segoe UI", 10), border_width=0),
            sg.Button("取消", key="-CANCEL-", size=(10, 1),
                     button_color=("#FFFFFF", "#404040"),
                     font=("Segoe UI", 10), border_width=0),
            sg.Push()
        ]

    @staticmethod
    def get_dialog_config(title: str, size: tuple, location: tuple = None,
                         icon_path: str = None) -> Dict[str, Any]:
        """获取对话框窗口配置

        Args:
            title: 对话框标题
            size: 对话框尺寸 (width, height)
            location: 对话框位置 (x, y)
            icon_path: 图标路径

        Returns:
            窗口配置字典
        """
        config = {
            "title": title,
            "modal": True,
            "keep_on_top": True,
            "finalize": True,
            "resizable": True,
            "size": size,
            "no_titlebar": False,
            "alpha_channel": 0.98,
            "background_color": "#202020",
            "margins": (10, 8),
            "element_padding": (3, 2)
        }

        if location:
            config["location"] = location
        if icon_path:
            config["icon"] = icon_path

        return config
