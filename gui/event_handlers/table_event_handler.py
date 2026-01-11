"""
表格交互事件处理器

处理表格选择、双击切换和数字键快捷键
"""

from typing import Dict, Any

from gui.event_handlers.base_handler import BaseEventHandler
from gui.interfaces.event_interfaces import IWindowActions


class TableEventHandler(BaseEventHandler):
    """表格交互事件处理器

    处理表格选择事件、双击切换任务和数字键快捷键
    """

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化表格事件处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        super().__init__(task_manager, window_actions, data_provider)

        # 选中状态保存
        self.preserved_selection = None

        # 事件路由映射
        self.event_handlers = {
            "-TASK_TABLE-": self._handle_table_selection,
            "-TASK_TABLE- Double": self._handle_table_double_click,
        }

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理表格相关事件"""
        # 先检查数字键快捷键
        if self._handle_number_shortcut(event):
            return True

        # 路由到具体的事件处理器
        handler = self.event_handlers.get(event)
        if handler:
            handler(values)
            return True

        return False

    def set_preserved_selection(self, selection):
        """设置保存的选中状态"""
        self.preserved_selection = selection

    def get_preserved_selection(self):
        """获取保存的选中���态"""
        return self.preserved_selection

    def _handle_number_shortcut(self, event: str) -> bool:
        """处理数字键快捷键 (1-9) 快速切换任务

        Args:
            event: 事件字符串

        Returns:
            是否成功处理了数字键事件
        """
        try:
            # 检查是否是数字键事件 (格式: "1", "2", ..., "9" 或 "1:49", "2:50", ...)
            number_key = None

            # 直接数字键
            if event in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                number_key = int(event)
            # 带键码的数字键
            elif event and event[0] in "123456789" and ":" in event:
                number_key = int(event[0])

            if number_key is None:
                return False

            # 获取任务列表
            tasks = self.task_manager.get_all_tasks()
            task_index = number_key - 1  # 转换为0-based索引

            if 0 <= task_index < len(tasks):
                task = tasks[task_index]
                print(f"⌨ 数字键 {number_key} 触发，切换到任务: {task.name}")
                self.set_status(f"正在切换到: {task.name}", 1000)

                success = self.task_manager.switch_to_task(task_index)
                if success:
                    self.set_status(f"已切换到: {task.name}", 3000)
                else:
                    self.set_status(f"切换失败: {task.name}", 3000)
                return True
            else:
                # 超出范围的数字键，播放提示音或显示提示
                self.set_status(f"没有第 {number_key} 个任务", 2000)
                return True

        except Exception as e:
            print(f"处理数字键快捷键失败: {e}")
            return False

    def _handle_table_selection(self, values: Dict[str, Any]):
        """处理表格选择事件"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if selected_rows:
                table_row = selected_rows[0]
                # 保存选中状态（表格行号）
                self.preserved_selection = table_row

                # 转换为原始任务索引
                task_index = self.get_original_task_index(table_row)
                task = self.task_manager.get_task_by_index(task_index)
                if task:
                    self.set_status(f"已选择: {task.name}", 2000)
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
            task_index = self.get_original_task_index(table_row)
            task = self.task_manager.get_task_by_index(task_index)

            if not task:
                print(f"⚠️ 找不到索引为 {task_index} 的任务")
                return

            print(f"🖱️ 双击任务: {task.name}")
            self.set_status(f"正在切换到: {task.name}", 1000)

            # 使用任务管理器切换到该任务
            success = self.task_manager.switch_to_task(task_index)

            if success:
                print(f"✅ 成功切换到任务: {task.name}")
                self.set_status(f"已切换到: {task.name}", 3000)
            else:
                print(f"❌ 切换任务失败: {task.name}")
                self.set_status(f"切换失败: {task.name}", 3000)

        except Exception as e:
            print(f"处理表格双击失败: {e}")
            self.set_status("切换任务失败", 2000)
