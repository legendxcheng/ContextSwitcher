"""
表格数据提供器模块

负责主窗口表格的数据转换和颜色渲染逻辑
从MainWindow中提取，遵循单一职责原则
"""

from typing import List, Dict, Any, Optional, Tuple
from core.task_manager import TaskManager, Task, TaskStatus
from core.time_tracker import get_time_tracker


class IDataProvider:
    """数据提供器接口"""

    def get_table_data(self) -> List[List[str]]:
        """获取表格数据"""
        raise NotImplementedError

    def get_row_colors(self) -> List[tuple]:
        """获取表格行颜色配置"""
        raise NotImplementedError


# 状态筛选映射
STATUS_FILTER_MAP = {
    "全部": None,
    "进行中": TaskStatus.IN_PROGRESS,
    "待办": TaskStatus.TODO,
    "已完成": TaskStatus.COMPLETED,
    "已暂停": TaskStatus.PAUSED,
}


class TableDataProvider(IDataProvider):
    """表格数据提供器实现"""

    def __init__(self, task_manager: TaskManager, task_status_manager=None):
        """初始化表格数据提供器

        Args:
            task_manager: 任务管理器实例
            task_status_manager: 任务状态管理器实例（可选）
        """
        self.task_manager = task_manager
        self.task_status_manager = task_status_manager

        # 搜索和筛选状态
        self.search_text = ""
        self.status_filter = None  # None表示全部

        # 缓存过滤后的任务索引映射 (表格行号 -> 原始任务索引)
        self._filtered_indices: List[int] = []

    def set_search_text(self, text: str) -> None:
        """设置搜索文本"""
        self.search_text = text.strip().lower()

    def set_status_filter(self, status_name: str) -> None:
        """设置状态筛选"""
        self.status_filter = STATUS_FILTER_MAP.get(status_name, None)

    def get_original_index(self, table_row: int) -> int:
        """根据表格行号获取原始任务索引

        Args:
            table_row: 表格中的行号

        Returns:
            原始任务列表中的索引，如果无效返回-1
        """
        if 0 <= table_row < len(self._filtered_indices):
            return self._filtered_indices[table_row]
        return -1

    def _get_filtered_tasks(self) -> List[Tuple[int, Task]]:
        """获取过滤后的任务列表

        Returns:
            (原始索引, 任务) 元组列表
        """
        tasks = self.task_manager.get_all_tasks()
        filtered = []

        for i, task in enumerate(tasks):
            # 状态筛选
            if self.status_filter is not None and task.status != self.status_filter:
                continue

            # 文本搜索（搜索任务名称、描述和标签）
            if self.search_text:
                name_match = self.search_text in task.name.lower()
                desc_match = self.search_text in task.description.lower() if task.description else False
                # 搜索标签
                tags_match = False
                if hasattr(task, 'tags') and task.tags:
                    tags_match = any(self.search_text in tag.lower() for tag in task.tags)
                if not (name_match or desc_match or tags_match):
                    continue

            filtered.append((i, task))

        return filtered
    
    def get_table_data(self) -> List[List[str]]:
        """获取表格数据"""
        table_data = []
        current_index = self.task_manager.current_task_index
        time_tracker = get_time_tracker()

        # 获取过滤后的任务
        filtered_tasks = self._get_filtered_tasks()

        # 更新索引映射
        self._filtered_indices = [orig_idx for orig_idx, _ in filtered_tasks]

        for orig_idx, task in filtered_tasks:
            # 任务编号（带当前任务标记）
            task_num = f"►{orig_idx+1}" if orig_idx == current_index else str(orig_idx+1)

            # 任务名称 - 适配调整后的列宽
            task_name = task.name
            if len(task_name) > 12:
                task_name = task_name[:10] + ".."

            # 绑定窗口数量
            valid_windows = sum(1 for w in task.bound_windows if w.is_valid)
            total_windows = len(task.bound_windows)

            if total_windows == 0:
                windows_info = "-"
            elif valid_windows == total_windows:
                windows_info = str(total_windows) if total_windows < 10 else "9+"
            else:
                windows_info = f"{valid_windows}/{total_windows}"

            # 任务状态 - 使用状态管理器的图标
            if self.task_status_manager:
                status_icon = self.task_status_manager.get_status_icon(task.status)
                status = status_icon
            else:
                # 备用显示方案
                if orig_idx == current_index:
                    status = "🟢"  # 活跃 - 绿色圆点
                elif total_windows > 0 and valid_windows == total_windows:
                    status = "🔵"  # 就绪 - 蓝色圆点
                elif valid_windows < total_windows:
                    status = "🟡"  # 部分有效 - 黄色圆点
                else:
                    status = "⚪"  # 空闲 - 白色圆点

            # 获取今日专注时间
            stats = time_tracker.get_task_stats(task.id)
            time_display = stats.today_display

            # 优先级图标
            priority = getattr(task, 'priority', 0)
            priority_icons = {0: "", 1: "🔽", 2: "➖", 3: "🔺"}  # 普通、低、中、高
            priority_icon = priority_icons.get(priority, "")

            # 新的6列格式：编号、优先级、任务名、窗口数、状态、今日时间
            table_data.append([task_num, priority_icon, task_name, windows_info, status, time_display])

        return table_data
    
    def get_row_colors(self) -> List[tuple]:
        """获取表格行颜色配置 - 使用FreeSimpleGUI正确的row_colors格式"""
        row_colors = []
        current_index = self.task_manager.current_task_index
        time_tracker = get_time_tracker()

        # 使用缓存的过滤索引
        # FreeSimpleGUI的row_colors格式: (row_number, foreground_color, background_color)
        for table_row, orig_idx in enumerate(self._filtered_indices):
            task = self.task_manager.get_task_by_index(orig_idx)
            if not task:
                continue

            # 获取任务的时间统计
            stats = time_tracker.get_task_stats(task.id)

            if orig_idx == current_index:
                # 当前任务：绿色高亮
                row_colors.append((table_row, '#00DD00', '#2D2D2D'))  # 亮绿色文字, 深灰背景
            elif stats.today_seconds > 3600:  # 今日专注超过1小时
                # 高效任务：蓝色
                row_colors.append((table_row, '#4DA6FF', '#202020'))  # 亮蓝色文字
            else:
                # 普通任务：恢复默认白色
                row_colors.append((table_row, '#FFFFFF', '#202020'))  # 白色文字, 默认背景

        return row_colors
    
    def set_task_status_manager(self, task_status_manager):
        """设置任务状态管理器"""
        self.task_status_manager = task_status_manager
    
    def get_windows_tooltip(self, task_index: int) -> str:
        """获取指定任务的窗口信息工具提示
        
        Args:
            task_index: 任务索引
            
        Returns:
            工具提示文本
        """
        if not (0 <= task_index < len(self.task_manager.tasks)):
            return ""
        
        task = self.task_manager.tasks[task_index]
        
        if not task.bound_windows:
            return "无绑定窗口"
        
        tooltip_lines = []
        for i, window in enumerate(task.bound_windows):
            status = "✓" if window.is_valid else "✗"
            
            # 基本窗口信息
            window_info = f"{status} {window.title}"
            
            # 如果是Explorer窗口，添加完整路径信息
            if window.folder_path and window.process_name and window.process_name.lower() == 'explorer.exe':
                window_info += f"\n   📁 {window.folder_path}"
            
            tooltip_lines.append(window_info)
        
        return "\n".join(tooltip_lines)