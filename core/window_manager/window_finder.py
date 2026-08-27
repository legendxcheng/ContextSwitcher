"""
窗口查找服务模块

提供窗口查找和统计功能。
"""

from typing import List, Dict, Any
from .window_info import WindowInfo
from .window_enumerator import WindowEnumerator


class WindowFinder:
    """窗口查找器"""
    
    def __init__(self, enumerator: WindowEnumerator):
        self.enumerator = enumerator
    
    def find_windows_by_title(self, title: str, exact_match: bool = False) -> List[WindowInfo]:
        """根据标题查找窗口"""
        windows = self.enumerator.enumerate_windows()
        
        if exact_match:
            return [w for w in windows if w.title == title]
        else:
            title_lower = title.lower()
            return [w for w in windows if title_lower in w.title.lower()]
    
    def find_windows_by_process(self, process_name: str) -> List[WindowInfo]:
        """根据进程名查找窗口"""
        windows = self.enumerator.enumerate_windows()
        process_name_lower = process_name.lower()
        
        return [w for w in windows if process_name_lower in w.process_name.lower()]
    
    def get_window_summary(self) -> Dict[str, Any]:
        """获取窗口管理器状态摘要"""
        windows = self.enumerator.enumerate_windows()
        
        # 按进程分组统计
        process_count = {}
        for window in windows:
            process_count[window.process_name] = process_count.get(window.process_name, 0) + 1
        
        return {
            "total_windows": len(windows),
            "top_processes": dict(sorted(process_count.items(), 
                                       key=lambda x: x[1], reverse=True)[:5])
        }