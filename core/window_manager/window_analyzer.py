"""
窗口状态分析模块

分析窗口状态和活跃程度，提供智能窗口检测功能。
"""

from typing import Dict, Any, Optional
try:
    import win32gui
except ImportError:
    print("错误: 请先安装pywin32库")
    raise

from .window_info import WindowInfo, COMMON_APPS
from .window_enumerator import WindowEnumerator


class WindowAnalyzer:
    """窗口分析器"""
    
    def __init__(self, enumerator: WindowEnumerator):
        self.enumerator = enumerator
    
    def get_foreground_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口信息"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return self.enumerator.get_window_info(hwnd)
        except Exception as e:
            print(f"获取前台窗口失败: {e}")
        return None
    
    def get_active_windows_info(self) -> Dict[str, Any]:
        """获取活跃窗口信息（基础实现）"""
        # 临时基础实现
        return {
            'foreground_window': self.get_foreground_window(),
            'active_windows': [],
            'recent_windows': [],
            'total_windows': 0
        }