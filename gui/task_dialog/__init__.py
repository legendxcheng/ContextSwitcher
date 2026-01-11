"""
任务对话框模块 (重构版)

负责任务的添加和编辑界面

重构后采用模块化设计：
- layout_builder: 布局构建
- window_selection_manager: 窗口选择管理
- form_handler: 表单处理
- dialog_event_handler: 事件处理
- status_converter: 状态转换
"""

from typing import Optional
import FreeSimpleGUI as sg

from core.task_manager import TaskManager, Task
from core.window_manager import WindowInfo
from gui.task_dialog.layout_builder import TaskDialogLayoutBuilder
from gui.task_dialog.window_selection_manager import WindowSelectionManager
from gui.task_dialog.form_handler import TaskFormHandler
from gui.task_dialog.dialog_event_handler import DialogEventHandler
from gui.modern_config import ModernUIConfig
from utils.dialog_position_manager import get_dialog_position_manager
from utils.popup_helper import PopupManager


# 导出主类
__all__ = ['TaskDialog']


class TaskDialog:
    """任务对话框类 (重构版)

    重构后的职责：
    - 协调各子模块
    - 提供公共接口
    - 管理对话框生命周期
    """

    def __init__(self, parent_window: sg.Window, task_manager: TaskManager):
        """初始化任务对话框

        Args:
            parent_window: 父窗口
            task_manager: 任务管理器
        """
        self.parent_window = parent_window
        self.task_manager = task_manager

        # 初始化子模块
        self.layout_builder = TaskDialogLayoutBuilder()
        self.window_manager = WindowSelectionManager(task_manager.window_manager)
        self.form_handler = TaskFormHandler(task_manager)
        self.position_manager = get_dialog_position_manager()
        self.popup_manager = PopupManager(parent_window)

        # 对话框窗口
        self.dialog_window: Optional[sg.Window] = None

    def show_add_dialog(self) -> bool:
        """显示添加任务对话框

        Returns:
            是否成功添加任务
        """
        # 重置状态
        self.form_handler.reset_form()
        self.window_manager.clear_selection()

        # 创建对话框
        layout = self._create_layout()
        self.dialog_window = self._create_window("添加任务", layout)

        if not self.dialog_window:
            return False

        # 初始化窗口列表
        self.window_manager.refresh_window_list(self.dialog_window)

        # 运行对话框
        result = self._run_dialog()

        if result:
            window_hwnds = [w.hwnd for w in self.window_manager.get_selected_windows()]
            task = self.form_handler.create_task(window_hwnds)
            return task is not None

        return False

    def show_edit_dialog(self, task: Task) -> bool:
        """显示编辑任务对话框

        Args:
            task: 要编辑的任务

        Returns:
            是否成功编辑任务
        """
        # 加载任务数据
        self.form_handler.load_task(task)

        # 加载绑定的窗口
        selected_windows = []
        for bound_window in task.bound_windows:
            if bound_window.is_valid:
                window_info = self.task_manager.window_manager.get_window_info(bound_window.hwnd)
                if window_info:
                    selected_windows.append(window_info)

        self.window_manager.set_selected_windows(selected_windows)

        # 创建对话框
        layout = self._create_layout()
        self.dialog_window = self._create_window(f"编辑任务 - {task.name}", layout)

        if not self.dialog_window:
            return False

        # 初始化窗口列表
        self.window_manager.refresh_window_list(self.dialog_window)

        # 运行对话框
        result = self._run_dialog()

        if result:
            window_hwnds = [w.hwnd for w in self.window_manager.get_selected_windows()]
            return self.form_handler.update_task(task.id, window_hwnds)

        return False

    def _create_layout(self):
        """创建对话框布局"""
        form_values = self.form_handler.get_layout_values()

        selected_display = [
            f"{w.title} ({w.process_name})"
            for w in self.window_manager.get_selected_windows()
        ]

        return self.layout_builder.build_full_layout(
            task_name=form_values["task_name"],
            task_description=form_values["task_description"],
            task_status=self.form_handler.get_form_data().status,
            task_priority=self.form_handler.get_form_data().priority,
            task_notes=form_values["task_notes"],
            task_tags=self.form_handler.get_form_data().tags,
            selected_windows_display=selected_display
        )

    def _create_window(self, title: str, layout):
        """创建对话框窗口

        Args:
            title: 窗口标题
            layout: 布局

        Returns:
            窗口对象
        """
        dialog_size = (620, 650)
        icon_path = ModernUIConfig._get_icon_path()
        main_window_position = self._get_main_window_position()
        dialog_position = self.position_manager.get_task_dialog_position(
            dialog_size, main_window_position
        )

        config = TaskDialogLayoutBuilder.get_dialog_config(
            title, dialog_size, dialog_position, icon_path
        )
        config["layout"] = layout

        return sg.Window(**config)

    def _run_dialog(self) -> bool:
        """运行对话框

        Returns:
            用户是否确认操作
        """
        if not self.dialog_window:
            return False

        try:
            # 创建事件处理器
            event_handler = DialogEventHandler(
                self.dialog_window,
                self.form_handler,
                self.window_manager,
                self.popup_manager
            )

            # 运行事件循环
            return event_handler.run_event_loop()

        finally:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None

    def _get_main_window_position(self) -> Optional[tuple]:
        """获取主窗口位置

        Returns:
            主窗口位置 (x, y) 或 None
        """
        try:
            if self.parent_window and hasattr(self.parent_window, 'current_location'):
                location = self.parent_window.current_location()
                if location and len(location) == 2:
                    return location
        except Exception as e:
            print(f"获取主窗口位置失败: {e}")
        return None
