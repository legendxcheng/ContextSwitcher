"""
窗口状态分析模块

分析窗口状态和活跃程度，提供智能窗口检测功能。
"""

from typing import Dict, Any, Optional, List
try:
    import win32gui
except ImportError:
    print("错误: 请先安装pywin32库")
    raise

from .window_info import WindowInfo, COMMON_APPS
from .window_enumerator import WindowEnumerator


class WindowAnalyzer:
    """窗口分析器

    负责分析窗口状态，识别活跃窗口和最近使用的窗口。
    """

    # 排除的窗口类名（用于活跃窗口检测）
    EXCLUDED_CLASSES = {
        'Shell_TrayWnd', 'DV2ControlHost', 'Windows.UI.Core.CoreWindow',
        'WorkerW', 'Progman', 'Button', 'Edit'
    }

    # 常见文件扩展名（用于识别最近使用的窗口）
    COMMON_FILE_EXTENSIONS = [
        '.txt', '.doc', '.docx', '.pdf', '.py', '.js', '.html', '.css',
        '.java', '.cpp', '.c', '.h', '.xlsx', '.pptx', '.json', '.xml'
    ]

    def __init__(self, enumerator: WindowEnumerator):
        """初始化窗口分析器

        Args:
            enumerator: 窗口枚举器实例
        """
        self.enumerator = enumerator

    def get_foreground_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口信息

        Returns:
            前台窗口信息，如果获取失败则返回None
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return self.enumerator.get_window_info(hwnd)
        except Exception as e:
            print(f"获取前台窗口失败: {e}")
        return None

    def get_active_windows_info(self) -> Dict[str, Any]:
        """获取活跃窗口信息（包括多屏幕环境）

        Returns:
            包含前台窗口和活跃窗口列表的信息字典
        """
        try:
            result = {
                'foreground_window': None,
                'active_windows': [],
                'recent_windows': [],
                'total_windows': 0
            }

            # 获取系统前台窗口
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd:
                foreground_info = self.enumerator.get_window_info(foreground_hwnd)
                if foreground_info:
                    result['foreground_window'] = foreground_info

            # 获取所有窗口
            all_windows = self.enumerator.enumerate_windows()
            result['total_windows'] = len(all_windows)

            # 识别活跃窗口（基于窗口属性和状态）
            active_windows = []
            recent_windows = []

            for window in all_windows:
                try:
                    # 检查窗口是否可能是活跃的
                    if self._is_likely_active_window(window):
                        if window.hwnd == foreground_hwnd:
                            # 前台窗口有最高优先级
                            active_windows.insert(0, window)
                        else:
                            active_windows.append(window)

                    # 收集最近可能使用的窗口
                    if self._is_recently_used_window(window):
                        recent_windows.append(window)

                except Exception as e:
                    print(f"分析窗口活跃状态失败 {window.hwnd}: {e}")
                    continue

            result['active_windows'] = active_windows[:10]  # 限制数量
            result['recent_windows'] = recent_windows[:20]  # 限制数量

            return result

        except Exception as e:
            print(f"获取活跃窗口信息失败: {e}")
            return {
                'foreground_window': None,
                'active_windows': [],
                'recent_windows': [],
                'total_windows': 0
            }

    def _is_likely_active_window(self, window: WindowInfo) -> bool:
        """判断窗口是否可能是活跃窗口

        Args:
            window: 窗口信息

        Returns:
            是否可能是活跃窗口
        """
        try:
            # 基本条件：窗口可见且启用
            if not window.is_visible or not window.is_enabled:
                return False

            # 检查窗口是否最小化
            if win32gui.IsIconic(window.hwnd):
                return False

            # 检查窗口大小（过小的窗口通常不是主要工作窗口）
            left, top, right, bottom = window.rect
            width = right - left
            height = bottom - top

            if width < 200 or height < 100:
                return False

            # 检查窗口是否在屏幕可见区域内
            if left > 3000 or top > 3000 or right < 0 or bottom < 0:
                return False

            # 排除一些系统窗口类型
            if window.class_name in self.EXCLUDED_CLASSES:
                return False

            return True

        except Exception as e:
            print(f"检查窗口活跃状态失败: {e}")
            return False

    def _is_recently_used_window(self, window: WindowInfo) -> bool:
        """判断窗口是否可能是最近使用的窗口

        Args:
            window: 窗口信息

        Returns:
            是否可能是最近使用的窗口
        """
        try:
            # 基本的可见性检查
            if not window.is_visible:
                return False

            # 如果是常见应用，认为是最近可能使用的
            process_name = window.process_name.lower()
            if process_name in COMMON_APPS:
                return True

            # 检查窗口标题是否包含文件名或项目名
            title_lower = window.title.lower()
            if any(ext in title_lower for ext in self.COMMON_FILE_EXTENSIONS):
                return True

            return False

        except Exception as e:
            print(f"检查窗口最近使用状态失败: {e}")
            return False