"""
待机时间计算工具模块

负责处理任务的时间相关操作：
- ISO时间字符串解析
- 待机时间计算
- 友好的时间格式化显示
- 时间比较和验证
"""

import time
from datetime import datetime, timezone
from typing import Optional, Tuple


class TimeHelper:
    """时间工具类"""
    
    @staticmethod
    def parse_iso_time(iso_string: str) -> Optional[datetime]:
        """解析ISO格式时间字符串
        
        Args:
            iso_string: ISO格式时间字符串 (如 "2024-01-01T12:00:00.123456")
            
        Returns:
            datetime对象，解析失败返回None
        """
        if not iso_string:
            return None
            
        try:
            # 处理带微秒的ISO格式
            if '.' in iso_string:
                return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            else:
                # 处理不带微秒的格式
                return datetime.fromisoformat(iso_string + '.000000')
                
        except (ValueError, TypeError) as e:
            print(f"解析时间字符串失败: {iso_string}, 错误: {e}")
            return None
    
    @staticmethod
    def calculate_idle_minutes(last_accessed: str) -> Optional[int]:
        """计算待机时间（分钟）
        
        Args:
            last_accessed: 最后访问时间的ISO字符串
            
        Returns:
            待机分钟数，计算失败返回None
        """
        last_time = TimeHelper.parse_iso_time(last_accessed)
        if not last_time:
            return None
            
        current_time = datetime.now()
        
        # 确保时间对象都有时区信息或都没有
        if last_time.tzinfo is None:
            time_diff = current_time - last_time
        else:
            current_time = current_time.replace(tzinfo=timezone.utc)
            time_diff = current_time - last_time
        
        # 转换为分钟数
        total_minutes = int(time_diff.total_seconds() // 60)
        return max(0, total_minutes)  # 确保不返回负数
    
    @staticmethod
    def format_idle_time(minutes: Optional[int]) -> str:
        """格式化显示待机时间
        
        Args:
            minutes: 待机分钟数
            
        Returns:
            友好的时间显示字符串
        """
        if minutes is None:
            return "?"
        
        if minutes == 0:
            return "刚刚"
        elif minutes < 60:
            return f"{minutes}分钟"
        elif minutes < 1440:  # 小于24小时
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours}小时"
            else:
                return f"{hours}小时{remaining_minutes}分钟"
        else:  # 大于等于24小时
            days = minutes // 1440
            remaining_hours = (minutes % 1440) // 60
            if remaining_hours == 0:
                return f"{days}天"
            else:
                return f"{days}天{remaining_hours}小时"
    
    @staticmethod
    def format_idle_time_compact(minutes: Optional[int]) -> str:
        """紧凑格式显示待机时间（适合表格显示）
        
        Args:
            minutes: 待机分钟数
            
        Returns:
            紧凑的时间显示字符串
        """
        if minutes is None:
            return "?"
        
        if minutes == 0:
            return "<1分"
        elif minutes < 60:
            return f"{minutes}分"
        elif minutes < 1440:  # 小于24小时
            hours = minutes // 60
            return f"{hours}时"
        else:  # 大于等于24小时
            days = minutes // 1440
            return f"{days}天"
    
    @staticmethod
    def is_idle_time_warning(minutes: Optional[int], warning_threshold: int) -> bool:
        """判断是否需要待机时间警告
        
        Args:
            minutes: 待机分钟数
            warning_threshold: 警告阈值（分钟）
            
        Returns:
            是否需要警告
        """
        if minutes is None:
            return False
        
        return minutes >= warning_threshold
    
    @staticmethod
    def get_current_iso_time() -> str:
        """获取当前时间的ISO格式字符串
        
        Returns:
            当前时间的ISO格式字符串
        """
        return datetime.now().isoformat()
    
    @staticmethod
    def validate_and_fix_time(iso_string: str) -> str:
        """验证并修复时间字符串
        
        Args:
            iso_string: 原始时间字符串
            
        Returns:
            修复后的有效时间字符串
        """
        parsed_time = TimeHelper.parse_iso_time(iso_string)
        if parsed_time:
            return iso_string
        else:
            # 如果解析失败，返回当前时间
            return TimeHelper.get_current_iso_time()


def calculate_task_idle_time(task, is_current_task: bool = False) -> Tuple[Optional[int], str, bool]:
    """计算任务的待机时间信息（便捷函数）
    
    Args:
        task: 任务对象（需要有last_accessed属性）
        is_current_task: 是否为当前活跃任务
        
    Returns:
        元组 (待机分钟数, 显示字符串, 是否需要警告)
    """
    from utils.config import get_config
    
    config = get_config()
    warning_threshold = config.get('monitoring.idle_time_warning_minutes', 10)
    
    minutes = TimeHelper.calculate_idle_minutes(task.last_accessed)
    display_text = TimeHelper.format_idle_time_compact(minutes)
    
    # 当前活跃任务不需要警告
    needs_warning = False if is_current_task else TimeHelper.is_idle_time_warning(minutes, warning_threshold)
    
    return minutes, display_text, needs_warning


def get_overdue_tasks(tasks, current_task_index: int = -1) -> list:
    """获取超时的任务列表（便捷函数）
    
    Args:
        tasks: 任务列表
        current_task_index: 当前活跃任务的索引，-1表示无当前任务
        
    Returns:
        超时任务列表
    """
    from utils.config import get_config
    
    config = get_config()
    warning_threshold = config.get('monitoring.idle_time_warning_minutes', 10)
    
    overdue_tasks = []
    
    for i, task in enumerate(tasks):
        # 跳过当前活跃任务
        if i == current_task_index:
            continue
            
        minutes = TimeHelper.calculate_idle_minutes(task.last_accessed)
        if TimeHelper.is_idle_time_warning(minutes, warning_threshold):
            overdue_tasks.append({
                'task': task,
                'idle_minutes': minutes,
                'display_time': TimeHelper.format_idle_time(minutes)
            })
    
    return overdue_tasks