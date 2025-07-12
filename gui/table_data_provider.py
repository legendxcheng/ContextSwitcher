"""
表格数据提供器模块

负责主窗口表格的数据转换和颜色渲染逻辑
从MainWindow中提取，遵循单一职责原则
"""

from typing import List, Dict, Any, Optional
from core.task_manager import TaskManager, Task


class IDataProvider:
    """数据提供器接口"""
    
    def get_table_data(self) -> List[List[str]]:
        """获取表格数据"""
        raise NotImplementedError
    
    def get_row_colors(self) -> List[tuple]:
        """获取表格行颜色配置"""
        raise NotImplementedError


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
    
    def get_table_data(self) -> List[List[str]]:
        """获取表格数据"""
        table_data = []
        tasks = self.task_manager.get_all_tasks()
        current_index = self.task_manager.current_task_index
        
        for i, task in enumerate(tasks):
            # 任务编号（带当前任务标记）
            task_num = f"►{i+1}" if i == current_index else str(i+1)
            
            # 任务名称 - 适配调整后的列宽
            task_name = task.name
            if len(task_name) > 15:
                task_name = task_name[:13] + ".."
            
            # 绑定窗口数量 - 紧凑显示
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
                if i == current_index:
                    status = "🟢"  # 活跃 - 绿色圆点
                elif total_windows > 0 and valid_windows == total_windows:
                    status = "🔵"  # 就绪 - 蓝色圆点
                elif valid_windows < total_windows:
                    status = "🟡"  # 部分有效 - 黄色圆点
                else:
                    status = "⚪"  # 空闲 - 白色圆点
            
            # 待机时间计算
            from utils.time_helper import calculate_task_idle_time
            is_current = (i == current_index)
            idle_minutes, idle_display, needs_warning = calculate_task_idle_time(task, is_current)
            
            # 新的5列格式：编号、任务名、窗口数、状态、待机时间
            table_data.append([task_num, task_name, windows_info, status, idle_display])
        
        return table_data
    
    def get_row_colors(self) -> List[tuple]:
        """获取表格行颜色配置 - 使用FreeSimpleGUI正确的row_colors格式"""
        row_colors = []
        tasks = self.task_manager.get_all_tasks()
        current_index = self.task_manager.current_task_index
        
        # FreeSimpleGUI的row_colors格式: (row_number, foreground_color, background_color)
        # 必须为所有行明确设置颜色，否则之前的颜色不会被清除
        for i, task in enumerate(tasks):
            # 计算待机时间以确定是否需要警告
            from utils.time_helper import calculate_task_idle_time
            is_current = (i == current_index)
            idle_minutes, idle_display, needs_warning = calculate_task_idle_time(task, is_current)
            
            if i == current_index:
                # 当前任务：绿色高亮
                row_colors.append((i, '#00DD00', '#2D2D2D'))  # 亮绿色文字, 深灰背景
            elif needs_warning:
                # 超时任务：红色警告（仅针对待机时间列）
                row_colors.append((i, '#FF4444', '#202020'))  # 红色文字, 默认背景
            else:
                # 普通任务：恢复默认白色
                row_colors.append((i, '#FFFFFF', '#202020'))  # 白色文字, 默认背景
        
        return row_colors
    
    def set_task_status_manager(self, task_status_manager):
        """设置任务状态管理器"""
        self.task_status_manager = task_status_manager