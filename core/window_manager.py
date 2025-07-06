"""
Windows API窗口管理模块

负责与Windows系统交互，管理窗口相关操作:
- 枚举所有可见窗口
- 获取窗口信息（标题、句柄等）
- 激活指定窗口到前台
- 检测窗口状态变化
- 批量操作多个窗口
"""

import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

try:
    import win32gui
    import win32con
    import win32process
    import win32api
except ImportError:
    print("错误: 请先安装pywin32库")
    print("运行: pip install pywin32")
    raise


@dataclass
class WindowInfo:
    """窗口信息数据类"""
    hwnd: int          # 窗口句柄
    title: str         # 窗口标题
    class_name: str    # 窗口类名
    process_id: int    # 进程ID
    process_name: str  # 进程名称
    is_visible: bool   # 是否可见
    is_enabled: bool   # 是否启用
    rect: Tuple[int, int, int, int]  # 窗口位置和大小 (left, top, right, bottom)


class WindowManager:
    """Windows窗口管理器"""
    
    def __init__(self):
        """初始化窗口管理器"""
        self.last_enum_time = 0
        self.cached_windows = []
        self.cache_duration = 2.0  # 缓存2秒
        
        # 需要过滤的窗口类名（系统窗口等）
        self.filtered_classes = {
            'Shell_TrayWnd',        # 任务栏
            'DV2ControlHost',       # Windows 10开始菜单
            'Windows.UI.Core.CoreWindow',  # UWP应用容器
            'ApplicationFrameWindow',      # UWP应用框架
            'WorkerW',              # 桌面工作窗口
            'Progman',              # 程序管理器
            'Button',               # 按钮控件
            'Edit',                 # 编辑控件
            ''                      # 空类名
        }
        
        # 需要过滤的窗口标题
        self.filtered_titles = {
            '',                     # 空标题
            'Program Manager',      # 程序管理器
            'Desktop',              # 桌面
        }
    
    def enumerate_windows(self, use_cache: bool = True) -> List[WindowInfo]:
        """枚举所有可见窗口
        
        Args:
            use_cache: 是否使用缓存（提高性能）
            
        Returns:
            窗口信息列表
        """
        current_time = time.time()
        
        # 检查缓存
        if (use_cache and 
            self.cached_windows and 
            current_time - self.last_enum_time < self.cache_duration):
            return self.cached_windows.copy()
        
        windows = []
        
        def enum_callback(hwnd: int, windows_list: List[WindowInfo]) -> bool:
            """枚举窗口的回调函数"""
            try:
                # 检查窗口是否可见
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                # 获取窗口标题
                title = win32gui.GetWindowText(hwnd)
                if not title or title in self.filtered_titles:
                    return True
                
                # 获取窗口类名
                class_name = win32gui.GetClassName(hwnd)
                if class_name in self.filtered_classes:
                    return True
                
                # 获取进程信息
                try:
                    thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
                    process_handle = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                        False, process_id
                    )
                    process_name = win32process.GetModuleFileNameEx(process_handle, 0)
                    win32api.CloseHandle(process_handle)
                    
                    # 只保留进程名，不要完整路径
                    process_name = process_name.split('\\')[-1] if process_name else "Unknown"
                    
                except Exception:
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
            self.cached_windows = windows.copy()
            self.last_enum_time = current_time
            
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
                process_handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False, process_id
                )
                process_name = win32process.GetModuleFileNameEx(process_handle, 0)
                win32api.CloseHandle(process_handle)
                process_name = process_name.split('\\')[-1] if process_name else "Unknown"
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
    
    def activate_window(self, hwnd: int) -> bool:
        """激活指定窗口到前台
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            是否成功激活
        """
        try:
            if not self.is_window_valid(hwnd):
                print(f"窗口无效: {hwnd}")
                return False
            
            if not win32gui.IsWindowVisible(hwnd):
                print(f"窗口不可见: {hwnd}")
                return False
            
            # 如果窗口已经是前台窗口，直接返回成功
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            
            # 尝试激活窗口
            try:
                # 如果窗口最小化，先恢复
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.1)  # 等待窗口恢复
                
                # 激活窗口
                win32gui.SetForegroundWindow(hwnd)
                
                # 确保窗口在最前面
                win32gui.SetWindowPos(
                    hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
                
                # 短暂等待，确保激活生效
                time.sleep(0.05)
                
                # 验证是否成功
                return win32gui.GetForegroundWindow() == hwnd
                
            except Exception as e:
                print(f"激活窗口失败 (第一次尝试): {e}")
                
                # 备用方法：使用ShowWindow
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.05)
                    return True
                except Exception as e2:
                    print(f"激活窗口失败 (备用方法): {e2}")
                    return False
        
        except Exception as e:
            print(f"激活窗口时出错: {e}")
            return False
    
    def activate_multiple_windows(self, hwnds: List[int], delay: float = 0.1) -> Dict[int, bool]:
        """批量激活多个窗口
        
        Args:
            hwnds: 窗口句柄列表
            delay: 窗口间切换延迟（秒）
            
        Returns:
            每个窗口的激活结果 {hwnd: success}
        """
        results = {}
        
        if not hwnds:
            return results
        
        print(f"正在激活 {len(hwnds)} 个窗口...")
        
        for i, hwnd in enumerate(hwnds):
            try:
                success = self.activate_window(hwnd)
                results[hwnd] = success
                
                if success:
                    print(f"✓ 已激活窗口 {i+1}/{len(hwnds)}: {hwnd}")
                else:
                    window_info = self.get_window_info(hwnd)
                    title = window_info.title if window_info else "Unknown"
                    print(f"✗ 激活失败 {i+1}/{len(hwnds)}: {hwnd} ({title})")
                
                # 窗口间延迟，避免切换过快
                if i < len(hwnds) - 1 and delay > 0:
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"激活窗口时出错 {hwnd}: {e}")
                results[hwnd] = False
        
        success_count = sum(1 for success in results.values() if success)
        print(f"激活完成: {success_count}/{len(hwnds)} 个窗口成功")
        
        return results
    
    def get_foreground_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口信息
        
        Returns:
            前台窗口信息，如果获取失败则返回None
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return self.get_window_info(hwnd)
        except Exception as e:
            print(f"获取前台窗口失败: {e}")
        
        return None
    
    def find_windows_by_title(self, title: str, exact_match: bool = False) -> List[WindowInfo]:
        """根据标题查找窗口
        
        Args:
            title: 窗口标题（或部分标题）
            exact_match: 是否精确匹配
            
        Returns:
            匹配的窗口列表
        """
        windows = self.enumerate_windows()
        
        if exact_match:
            return [w for w in windows if w.title == title]
        else:
            title_lower = title.lower()
            return [w for w in windows if title_lower in w.title.lower()]
    
    def find_windows_by_process(self, process_name: str) -> List[WindowInfo]:
        """根据进程名查找窗口
        
        Args:
            process_name: 进程名（如 "notepad.exe"）
            
        Returns:
            匹配的窗口列表
        """
        windows = self.enumerate_windows()
        process_name_lower = process_name.lower()
        
        return [w for w in windows if process_name_lower in w.process_name.lower()]
    
    def get_window_summary(self) -> Dict[str, Any]:
        """获取窗口管理器状态摘要
        
        Returns:
            状态摘要信息
        """
        windows = self.enumerate_windows()
        
        # 按进程分组统计
        process_count = {}
        for window in windows:
            process_count[window.process_name] = process_count.get(window.process_name, 0) + 1
        
        return {
            "total_windows": len(windows),
            "cached_windows": len(self.cached_windows),
            "cache_age": time.time() - self.last_enum_time,
            "top_processes": dict(sorted(process_count.items(), 
                                       key=lambda x: x[1], reverse=True)[:5])
        }
    
    def get_window_process(self, hwnd: int) -> str:
        """获取窗口的进程名
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            进程名，如果获取失败则返回"Unknown"
        """
        try:
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, process_id
            )
            process_name = win32process.GetModuleFileNameEx(process_handle, 0)
            win32api.CloseHandle(process_handle)
            return process_name.split('\\')[-1] if process_name else "Unknown"
        except Exception:
            return "Unknown"
    
    def invalidate_cache(self):
        """清除窗口缓存，强制下次重新枚举"""
        self.cached_windows = []
        self.last_enum_time = 0