"""
搜索和筛选事件处理器

处理搜索输入、状态筛选和排序功能
"""

from typing import Dict, Any

from gui.event_handlers.base_handler import BaseEventHandler
from gui.interfaces.event_interfaces import IWindowActions


class SearchEventHandler(BaseEventHandler):
    """搜索和筛选事件处理器

    处理搜索输入、状态筛选、排序方式和搜索历史管理
    """

    MAX_HISTORY = 10  # 最大历史记录数

    def __init__(self, task_manager, window_actions: IWindowActions, data_provider=None):
        """初始化搜索事件处理器

        Args:
            task_manager: 任务管理器实例
            window_actions: 窗口动作接口实现
            data_provider: 数据提供器（可选）
        """
        super().__init__(task_manager, window_actions, data_provider)

        # 搜索历史
        self._search_history = []

        # 事件路由映射
        self.event_handlers = {
            "-SEARCH-": self._handle_search,
            "-FILTER_STATUS-": self._handle_filter_status,
            "-SORT_BY-": self._handle_sort_by,
        }

    def handle_event(self, event: str, values: Dict[str, Any]) -> bool:
        """处理搜索和筛选相关事件"""
        handler = self.event_handlers.get(event)
        if handler:
            handler(values)
            return True
        return False

    def _handle_search(self, values: Dict[str, Any]):
        """处理搜索输入（支持历史记录）"""
        try:
            search_text = values.get("-SEARCH-", "")
            if self.data_provider:
                self.data_provider.set_search_text(search_text)

                # 更新搜索历史
                if search_text and search_text not in self._search_history:
                    self._search_history.insert(0, search_text)
                    # 限制历史记录数量
                    if len(self._search_history) > self.MAX_HISTORY:
                        self._search_history = self._search_history[:self.MAX_HISTORY]

                    # 更新搜索下拉框的选项
                    try:
                        window = self.get_window()
                        if window and "-SEARCH-" in window.AllKeysDict:
                            window["-SEARCH-"].update(values=self._search_history + [search_text])
                            window["-SEARCH-"].update(value=search_text)
                    except:
                        pass

                self.update_display()
        except Exception as e:
            print(f"搜索处理失败: {e}")

    def _handle_filter_status(self, values: Dict[str, Any]):
        """处理状态筛选"""
        try:
            status_filter = values.get("-FILTER_STATUS-", "全部")
            if self.data_provider:
                self.data_provider.set_status_filter(status_filter)
                self.update_display()
                self.set_status(f"筛选: {status_filter}", 2000)
        except Exception as e:
            print(f"筛选处理失败: {e}")

    def _handle_sort_by(self, values: Dict[str, Any]):
        """处理排序方式变更"""
        try:
            sort_by = values.get("-SORT_BY-", "默认")
            if self.data_provider:
                self.data_provider.set_sort_by(sort_by)
                self.update_display()
                self.set_status(f"排序: {sort_by}", 2000)
        except Exception as e:
            print(f"排序处理失败: {e}")

    def get_search_history(self) -> list:
        """获取搜索历史列表

        Returns:
            搜索历史列表的副本
        """
        return self._search_history.copy()

    def clear_search_history(self):
        """清除搜索历史"""
        self._search_history = []
