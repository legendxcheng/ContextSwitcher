"""
窗口枚举和基础信息模块

负责与Windows API交互，枚举系统中的窗口并获取窗口基础信息。
从原始 window_manager.py 中提取核心枚举逻辑。
"""

from typing import List, Optional

try:
    import win32gui
    import win32con
    import win32process
    import win32api
except ImportError:
    print("错误: 请先安装pywin32库")
    print("运行: pip install pywin32")
    raise

from .window_info import WindowInfo, FILTERED_CLASSES, FILTERED_TITLES
from .cache_manager import CacheManager


class WindowEnumerator:
    """窗口枚举器
    
    负责枚举系统窗口和获取窗口基础信息，支持缓存机制。
    """
    
    def __init__(self, cache_manager: CacheManager):
        """初始化窗口枚举器
        
        Args:
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager
    
    def enumerate_windows(self, use_cache: bool = True) -> List[WindowInfo]:
        """枚举所有可见窗口
        
        Args:
            use_cache: 是否使用缓存（提高性能）
            
        Returns:
            窗口信息列表
        """
        # 检查缓存
        if use_cache:
            cached_windows = self.cache_manager.get_cached_windows()
            if cached_windows is not None:
                return cached_windows
        
        windows = []
        
        def enum_callback(hwnd: int, windows_list: List[WindowInfo]) -> bool:
            """枚举窗口的回调函数"""
            try:
                # 检查窗口是否可见
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                # 获取窗口标题
                title = win32gui.GetWindowText(hwnd)
                if not title or title in FILTERED_TITLES:
                    return True
                
                # 获取窗口类名
                class_name = win32gui.GetClassName(hwnd)
                if class_name in FILTERED_CLASSES:
                    return True
                
                # 获取进程信息
                try:
                    thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
                    process_name = self._get_process_name(process_id)
                except Exception:
                    process_id = 0
                    process_name = "Unknown"
                
                # 获取窗口位置
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                except Exception:
                    rect = (0, 0, 0, 0)
                
                # 检查窗口是否启用
                is_enabled = win32gui.IsWindowEnabled(hwnd)
                
                # 创建窗口信息对象
                window_info = WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    class_name=class_name,
                    process_id=process_id,
                    process_name=process_name,
                    is_visible=True,
                    is_enabled=is_enabled,
                    rect=rect
                )
                
                windows_list.append(window_info)
                
            except Exception as e:
                # 忽略单个窗口的错误，继续枚举其他窗口
                print(f"枚举窗口时出错 (hwnd={hwnd}): {e}")
            
            return True  # 继续枚举
        
        try:
            # 枚举所有顶级窗口
            win32gui.EnumWindows(enum_callback, windows)
            
            # 按进程名和标题排序
            windows.sort(key=lambda w: (w.process_name.lower(), w.title.lower()))
            
            # 更新缓存
            self.cache_manager.update_cache(windows)
            
        except Exception as e:
            print(f"枚举窗口失败: {e}")
            return []
        
        return windows
    
    def get_window_info(self, hwnd: int) -> Optional[WindowInfo]:
        """获取指定窗口的信息
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            窗口信息，如果窗口不存在则返回None
        """
        try:
            if not self.is_window_valid(hwnd):
                return None
            
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            # 获取进程信息
            try:
                thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
                process_name = self._get_process_name(process_id)
            except Exception:
                process_id = 0
                process_name = "Unknown"
            
            rect = win32gui.GetWindowRect(hwnd)
            is_visible = win32gui.IsWindowVisible(hwnd)
            is_enabled = win32gui.IsWindowEnabled(hwnd)
            
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_id=process_id,
                process_name=process_name,
                is_visible=is_visible,
                is_enabled=is_enabled,
                rect=rect
            )
            
        except Exception as e:
            print(f"获取窗口信息失败 (hwnd={hwnd}): {e}")
            return None
    
    def is_window_valid(self, hwnd: int) -> bool:
        """检查窗口是否仍然存在和有效
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            窗口是否有效
        """
        try:
            return win32gui.IsWindow(hwnd)
        except Exception:
            return False
    
    def get_window_process(self, hwnd: int) -> str:
        """获取窗口的进程名
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            进程名，如果获取失败则返回"Unknown"
        """
        try:
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            return self._get_process_name(process_id)
        except Exception:
            return "Unknown"
    
    def _get_process_name(self, process_id: int) -> str:
        """获取进程名（内部辅助方法）
        
        Args:
            process_id: 进程ID
            
        Returns:
            进程名
        """
        try:
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, process_id
            )
            process_name = win32process.GetModuleFileNameEx(process_handle, 0)
            win32api.CloseHandle(process_handle)
            
            # 只保留进程名，不要完整路径
            return process_name.split('\\')[-1] if process_name else "Unknown"
            
        except Exception:
            return "Unknown"