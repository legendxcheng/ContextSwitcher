"""
任务事件处理器

处理任务的添加、编辑、删除和撤销操作
"""

import copy
import time
from typing import Dict, Any

from gui.event_handlers.base_handler import BaseEventHandler
from gui.interfaces.event_interfaces import IWindowActions
from utils.popup_helper import PopupManager


class TaskEventHandler(BaseEventHandler):
    """任务事件处理器

    处理添加任务、编辑任务、删除任务和撤销删除操作
    """

    UNDO_TIMEOUT_SECONDS = 5  # 撤销操作过期时间（秒）

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化任务事件处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        super().__init__(task_manager, window_actions, data_provider)
        self.popup_manager = PopupManager(window_actions.get_window())

        # 删除撤销功能状态
        self._deleted_task = None
        self._undo_expiry_time = 0
        self._undo_timer_active = False

        # 事件路由映射
        self.event_handlers = {
            "-ADD_TASK-": self._handle_add_task,
            "-EDIT_TASK-": self._handle_edit_task,
            "-DELETE_TASK-": self._handle_delete_task,
            "-UNDO_DELETE-": self._handle_undo_delete,
        }

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理任务相关事件"""
        handler = self.event_handlers.get(event)
        if handler:
            if event in ["-EDIT_TASK-", "-DELETE_TASK-"]:
                handler(values)
            else:
                handler()
            return True
        return False

    def _handle_add_task(self):
        """处理添加任务"""
        try:
            print("点击了添加任务按钮")
            from gui.task_dialog import TaskDialog

            window = self.get_window()
            dialog = TaskDialog(window, self.task_manager)
            result = dialog.show_add_dialog()

            if result:
                self.update_display()
                self.set_status("任务添加成功", 3000)
                print("任务添加成功")
            else:
                print("任务添加取消")

        except Exception as e:
            print(f"添加任务失败: {e}")
            import traceback
            traceback.print_exc()
            self.set_status("添加任务失败", 3000)

    def _handle_edit_task(self, values: Dict[str, Any]):
        """处理编辑任务"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                self.popup_manager.show_message("请先选择要编辑的任务", "提示")
                return

            table_row = selected_rows[0]
            task_index = self.get_original_task_index(table_row)
            task = self.task_manager.get_task_by_index(task_index)

            if not task:
                self.popup_manager.show_error("任务不存在", "错误")
                return

            from gui.task_dialog import TaskDialog

            window = self.get_window()
            dialog = TaskDialog(window, self.task_manager)
            result = dialog.show_edit_dialog(task)

            if result:
                self.update_display()
                self.set_status("任务编辑成功", 3000)

        except Exception as e:
            print(f"编辑任务失败: {e}")
            self.set_status("编辑任务失败", 3000)

    def _handle_delete_task(self, values: Dict[str, Any]):
        """处理删除任务 - 支持撤销"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                self.popup_manager.show_message("请先选择要删除的任务", "提示")
                return

            table_row = selected_rows[0]
            task_index = self.get_original_task_index(table_row)
            task = self.task_manager.get_task_by_index(task_index)

            if not task:
                self.popup_manager.show_error("任务不存在", "错误")
                return

            # 确认删除
            result = self.popup_manager.show_question(
                f"确定要删除任务 '{task.name}' 吗？\n\n删除后可在5秒内点击撤销按钮恢复。",
                "确认删除"
            )

            if result:
                # 保存任务副本用于撤销
                self._deleted_task = copy.deepcopy(task)
                self._undo_expiry_time = time.time() + self.UNDO_TIMEOUT_SECONDS

                if self.task_manager.remove_task(task.id):
                    self.update_display()
                    self.set_status("任务已删除 | 点击撤销按钮恢复", 5000)

                    # 显示撤销按钮
                    try:
                        window = self.get_window()
                        window["-UNDO_DELETE-"].update(visible=True)
                        self._undo_timer_active = True
                    except:
                        self._undo_timer_active = True
                else:
                    self.popup_manager.show_error("删除任务失败", "错误")
                    self._deleted_task = None

        except Exception as e:
            print(f"删除任务失败: {e}")
            self.set_status("删除任务失败", 3000)

    def _handle_undo_delete(self):
        """处理撤销删除"""
        try:
            if self._deleted_task is None:
                self.set_status("没有可撤销的删除操作", 2000)
                return

            if time.time() > self._undo_expiry_time:
                self.set_status("撤销时间已过期", 2000)
                self._deleted_task = None
                self._undo_timer_active = False
                self._hide_undo_button()
                return

            # 恢复任务
            if self.task_manager.add_task(self._deleted_task):
                self.update_display()
                self.set_status(f"已恢复任务: {self._deleted_task.name}", 3000)
                print(f"✓ 撤销删除成功: {self._deleted_task.name}")
            else:
                self.set_status("撤销失败", 2000)

            # 清除撤销状态并隐藏按钮
            self._deleted_task = None
            self._undo_timer_active = False
            self._hide_undo_button()

        except Exception as e:
            print(f"撤销删除失败: {e}")
            self.set_status("撤销失败", 2000)

    def _hide_undo_button(self):
        """隐藏撤销按钮"""
        try:
            window = self.get_window()
            window["-UNDO_DELETE-"].update(visible=False)
        except:
            pass

    def is_undo_available(self) -> bool:
        """检查撤销是否可用

        Returns:
            bool: 撤销是否可用
        """
        return (
            self._deleted_task is not None and
            time.time() <= self._undo_expiry_time
        )

    def get_undo_expiry_time(self) -> float:
        """获取撤销过期时间

        Returns:
            过期时间戳
        """
        return self._undo_expiry_time
