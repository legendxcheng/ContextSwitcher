"""
对话框事件处理器模块

负责对话框事件循环和事件分发处理
"""

from typing import List, Dict, Any, Optional, Callable
import FreeSimpleGUI as sg

from gui.task_dialog.form_handler import TaskFormHandler
from gui.task_dialog.window_selection_manager import WindowSelectionManager
from utils.popup_helper import PopupManager


class DialogEventHandler:
    """对话框事件处理器 - 负责事件循环和分发"""

    def __init__(
        self,
        dialog_window: sg.Window,
        form_handler: TaskFormHandler,
        window_manager: WindowSelectionManager,
        popup_manager: PopupManager
    ):
        """初始化事件处理器

        Args:
            dialog_window: 对话框窗口
            form_handler: 表单处理器
            window_manager: 窗口选择管理器
            popup_manager: 弹窗管理器
        """
        self.dialog_window = dialog_window
        self.form_handler = form_handler
        self.window_manager = window_manager
        self.popup_manager = popup_manager

        # 绑定双击事件
        self._bind_double_click()

    def _bind_double_click(self) -> None:
        """绑定表格双击事件"""
        try:
            self.dialog_window['-WINDOW_TABLE-'].bind('<Double-Button-1>', ' Double')
        except Exception as e:
            print(f"绑定双击事件失败: {e}")

    def run_event_loop(self) -> bool:
        """运行对话框事件循环

        Returns:
            用户是否确认操作
        """
        if not self.dialog_window:
            return False

        try:
            while True:
                event, values = self.dialog_window.read()

                if event in (sg.WIN_CLOSED, "-CANCEL-"):
                    return False

                elif event == "-OK-":
                    return self._handle_ok(values)

                elif event == "-REFRESH_WINDOWS-":
                    self._handle_refresh()

                elif event == "-WINDOW_TABLE-":
                    self._handle_table_click(values)

                elif event == "-WINDOW_TABLE- Double":
                    self._handle_table_double_click(values)

                elif event == "-ADD_WINDOW-":
                    self._handle_add_window(values)

                elif event == "-REMOVE_WINDOW-":
                    self._handle_remove_window(values)

                elif event == "-WINDOW_FILTER-":
                    self._handle_filter_change(values)

                elif event == "-CLEAR_FILTER-":
                    self._handle_clear_filter()

        finally:
            pass  # 窗口关闭由调用者处理

    def _handle_ok(self, values: Dict[str, Any]) -> bool:
        """处理确定按钮

        Args:
            values: 表单值

        Returns:
            是否确认操作
        """
        # 保存表单数据
        self.form_handler.save_from_values(values)

        # 验证表单
        is_valid, error_msg = self.form_handler.validate(
            len(self.window_manager.get_selected_windows()),
            self.popup_manager
        )

        if not is_valid:
            self.popup_manager.show_error(error_msg, "验证错误")
            return False

        # 检查是否选择了窗口
        if not self.window_manager.get_selected_windows():
            result = self.popup_manager.show_question(
                "没有选择任何窗口，确定要创建此任务吗？",
                "确认"
            )
            if not result:
                return False

        return True

    def _handle_refresh(self) -> None:
        """处理刷新窗口列表按钮"""
        self.window_manager.refresh_window_list(self.dialog_window)

    def _handle_table_click(self, values: Dict[str, Any]) -> None:
        """处理表格单击事件

        Args:
            values: 表单值
        """
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                return

            row_index = selected_rows[0]
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values

            if not table_data or row_index >= len(table_data):
                return

            # 可以在这里添加单击后的处理逻辑
            # 目前单击只用于选择行，不需要额外处理

        except Exception as e:
            print(f"处理表格点击失败: {e}")

    def _handle_table_double_click(self, values: Dict[str, Any]) -> None:
        """处理表格双击事件 - 直接添加窗口

        Args:
            values: 表单值
        """
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                return

            row_index = selected_rows[0]

            # 获取表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values

            # 添加窗口
            if self.window_manager.add_window_by_row_index(row_index, table_data):
                self.window_manager.update_selected_display(self.dialog_window)
                self.window_manager.refresh_window_list(self.dialog_window)

        except Exception as e:
            print(f"处理表格双击失败: {e}")

    def _handle_add_window(self, values: Dict[str, Any]) -> None:
        """处理添加窗口按钮

        Args:
            values: 表单值
        """
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                self.popup_manager.show_message("请先选择一个窗口", "提示")
                return

            row_index = selected_rows[0]
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values

            if not table_data or row_index >= len(table_data):
                self.popup_manager.show_error("表格数据异常", "错误")
                return

            # 尝试添加窗口
            if self.window_manager.add_window_by_row_index(row_index, table_data):
                self.window_manager.update_selected_display(self.dialog_window)
                self.window_manager.refresh_window_list(self.dialog_window)
            else:
                self.popup_manager.show_message("此窗口已经选择", "提示")

        except Exception as e:
            print(f"添加窗口失败: {e}")
            self.popup_manager.show_error(f"添加失败: {e}", "错误")

    def _handle_remove_window(self, values: Dict[str, Any]) -> None:
        """处理移除窗口按钮

        Args:
            values: 表单值
        """
        try:
            selected_items = values.get("-SELECTED_WINDOWS-", [])
            if not selected_items:
                self.popup_manager.show_message("请先选择要移除的窗口", "提示")
                return

            selected_text = selected_items[0]

            # 移除窗口
            removed = self.window_manager.remove_window_by_display_text(selected_text)

            if removed:
                self.window_manager.update_selected_display(self.dialog_window)
                self.window_manager.refresh_window_list(self.dialog_window)
                self.popup_manager.show_timed_message(
                    f"已移除窗口: {removed.title}", 2, "成功"
                )
            else:
                self.popup_manager.show_error("未找到要移除的窗口", "错误")

        except Exception as e:
            print(f"移除窗口失败: {e}")

    def _handle_filter_change(self, values: Dict[str, Any]) -> None:
        """处理搜索过滤变化

        Args:
            values: 表单值
        """
        filter_text = values.get("-WINDOW_FILTER-", "").strip()
        self.window_manager.set_filter_text(filter_text, self.dialog_window)

    def _handle_clear_filter(self) -> None:
        """处理清空过滤按钮"""
        self.window_manager.clear_filter(self.dialog_window)
