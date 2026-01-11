"""
窗口选择管理器模块

负责窗口选择相关的所有功能：
- 窗口列表刷新、过滤、排序
- 窗口添加、移除
- 窗口显示格式化
"""

from typing import List, Dict, Any, Optional
import FreeSimpleGUI as sg

from core.window_manager import WindowInfo, WindowManager
from utils.search_helper import SearchHelper
from utils.window_priority import WindowPriorityManager


class WindowSelectionManager:
    """窗口选择管理器 - 负责窗口列表、过滤、排序、选择"""

    # 优先级图标映射
    PRIORITY_ICONS = {
        "foreground": "🔥",  # 前台窗口
        "active": "⭐",      # 活跃窗口
        "recent": "📌",      # 最近使用
        "search": "🔍",      # 搜索匹配
        "high_score": "💻"   # 高优先级应用
    }

    def __init__(self, window_manager: WindowManager):
        """初始化窗口选择管理器

        Args:
            window_manager: 窗口管理器
        """
        self.window_manager = window_manager
        self.search_helper = SearchHelper()
        self.priority_manager = WindowPriorityManager()

        # 状态数据
        self.selected_windows: List[WindowInfo] = []
        self.window_filter_text = ""
        self._filtered_windows: List[WindowInfo] = []
        self._current_priorities: Dict[int, Any] = {}

    def refresh_window_list(self, dialog_window: sg.Window) -> None:
        """刷新窗口列表（支持搜索和优先级）

        Args:
            dialog_window: 对话框窗口对象
        """
        if not dialog_window:
            return

        try:
            # 强制刷新窗口缓存
            self.window_manager.invalidate_cache()

            # 获取最新窗口列表
            all_windows = self.window_manager.enumerate_windows()

            # 应用搜索过滤和智能排序
            filtered_windows = self._filter_and_sort_windows(all_windows)
            self._filtered_windows = filtered_windows

            # 更新表格数据
            window_data = self._build_table_data(filtered_windows)

            # 更新表格
            dialog_window["-WINDOW_TABLE-"].update(values=window_data)

            # 更新搜索统计信息
            self._update_filter_count(dialog_window, len(all_windows), len(filtered_windows))

        except Exception as e:
            print(f"刷新窗口列表失败: {e}")

    def add_window_by_row_index(self, row_index: int, table_data: List) -> bool:
        """通过行索引添加窗口

        Args:
            row_index: 行索引
            table_data: 表格数据

        Returns:
            是否成功添加
        """
        try:
            if not table_data or row_index >= len(table_data):
                print(f"表格数据异常: row_index={row_index}")
                return False

            row_data = table_data[row_index]
            if not isinstance(row_data, list) or len(row_data) < 5:
                print(f"表格行数据格式异常: {row_data}")
                return False

            # 获取窗口句柄（第4列）
            hwnd_str = row_data[4]
            hwnd = int(hwnd_str)

            # 检查是否已经选择
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            if hwnd in selected_hwnds:
                print(f"窗口已经选择: {hwnd}")
                return False

            # 获取窗口信息并添加
            window_info = self.window_manager.get_window_info(hwnd)
            if window_info:
                self.selected_windows.append(window_info)
                print(f"添加窗口成功: {window_info.title}")
                return True
            else:
                print("窗口信息获取失败")
                return False

        except Exception as e:
            print(f"添加窗口失败: {e}")
            return False

    def remove_window_by_display_text(self, display_text: str) -> Optional[WindowInfo]:
        """根据显示文本移除窗口

        Args:
            display_text: 窗口显示文本

        Returns:
            被移除的窗口，如果没找到则返回None
        """
        for i, window in enumerate(self.selected_windows):
            text = f"{window.title} ({window.process_name})"
            if text == display_text:
                removed = self.selected_windows.pop(i)
                print(f"移除窗口: {removed.title}")
                return removed
        return None

    def update_selected_display(self, dialog_window: sg.Window) -> None:
        """更新已选择窗口的显示

        Args:
            dialog_window: 对话框窗口对象
        """
        if not dialog_window:
            return

        try:
            display_list = [
                f"{w.title} ({w.process_name})"
                for w in self.selected_windows
            ]
            dialog_window["-SELECTED_WINDOWS-"].update(values=display_list)
        except Exception as e:
            print(f"更新选择窗口显示失败: {e}")

    def clear_filter(self, dialog_window: sg.Window) -> None:
        """清空搜索过滤

        Args:
            dialog_window: 对话框窗口对象
        """
        self.window_filter_text = ""
        dialog_window["-WINDOW_FILTER-"].update("")
        self.refresh_window_list(dialog_window)

    def set_filter_text(self, filter_text: str, dialog_window: sg.Window) -> None:
        """设置搜索过滤文本

        Args:
            filter_text: 过滤文本
            dialog_window: 对话框窗口对象
        """
        self.window_filter_text = filter_text.strip()
        self.refresh_window_list(dialog_window)

    def get_selected_windows(self) -> List[WindowInfo]:
        """获取已选择的窗口列表

        Returns:
            已选择的窗口列表
        """
        return self.selected_windows.copy()

    def set_selected_windows(self, windows: List[WindowInfo]) -> None:
        """设置已选择的窗口列表

        Args:
            windows: 窗口列表
        """
        self.selected_windows = windows.copy()

    def clear_selection(self) -> None:
        """清空窗口选择"""
        self.selected_windows.clear()
        self.window_filter_text = ""
        self._filtered_windows.clear()
        self._current_priorities.clear()

    def _filter_and_sort_windows(self, windows: List[WindowInfo]) -> List[WindowInfo]:
        """使用智能排序和搜索过滤窗口列表

        Args:
            windows: 原始窗口列表

        Returns:
            过滤和排序后的窗口列表
        """
        try:
            # 获取活跃窗口信息
            active_windows_info = self.window_manager.get_active_windows_info()

            # 搜索过滤
            search_results_dict = {}
            filtered_windows = windows

            if self.window_filter_text:
                search_results = self.search_helper.search_windows(
                    windows, self.window_filter_text
                )
                search_results_dict = {
                    result.item.hwnd: result for result in search_results
                }
                filtered_windows = [result.item for result in search_results]

            # 使用优先级管理器进行智能排序
            priorities = self.priority_manager.calculate_window_priorities(
                filtered_windows, active_windows_info, search_results_dict
            )

            # 存储优先级信息用于显示
            self._current_priorities = {
                priority.window.hwnd: priority for priority in priorities
            }

            return [priority.window for priority in priorities]

        except Exception as e:
            print(f"过滤和排序窗口失败: {e}")
            return windows

    def _build_table_data(self, windows: List[WindowInfo]) -> List[List[str]]:
        """构建表格数据

        Args:
            windows: 窗口列表

        Returns:
            表格数据列表
        """
        window_data = []
        selected_hwnds = [w.hwnd for w in self.selected_windows]

        for window in windows:
            is_selected = window.hwnd in selected_hwnds

            # 获取优先级图标
            priority_indicator = self._get_priority_icon(window.hwnd)

            window_data.append([
                "✓" if is_selected else "",
                priority_indicator,
                window.title,
                window.process_name,
                str(window.hwnd)
            ])

        return window_data

    def _get_priority_icon(self, hwnd: int) -> str:
        """获取窗口优先级图标

        Args:
            hwnd: 窗口句柄

        Returns:
            优先级图标字符串
        """
        priority_info = self._current_priorities.get(hwnd)
        if not priority_info:
            return ""

        if priority_info.is_foreground:
            return self.PRIORITY_ICONS["foreground"]
        elif priority_info.is_active:
            return self.PRIORITY_ICONS["active"]
        elif priority_info.is_recent:
            return self.PRIORITY_ICONS["recent"]
        elif priority_info.search_score > 0:
            return self.PRIORITY_ICONS["search"]
        elif priority_info.total_score > 50:
            return self.PRIORITY_ICONS["high_score"]

        return ""

    def _update_filter_count(self, dialog_window: sg.Window,
                            total_count: int, filtered_count: int) -> None:
        """更新过滤统计信息

        Args:
            dialog_window: 对话框窗口对象
            total_count: 总窗口数
            filtered_count: 过滤后窗口数
        """
        try:
            if self.window_filter_text:
                filter_info = f"显示 {filtered_count}/{total_count}"
            else:
                filter_info = f"共 {total_count} 个窗口"

            if "-FILTER_COUNT-" in dialog_window.AllKeysDict:
                dialog_window["-FILTER_COUNT-"].update(filter_info)
        except Exception as e:
            print(f"更新过滤统计失败: {e}")
