"""
屏幕位置和鼠标检测工具模块

提供屏幕相关的实用功能：
- 获取鼠标当前位置
- 计算窗口最佳显示位置
- 多屏幕环境支持
- 屏幕边界检查
"""

from typing import Tuple, Optional

try:
    import win32gui
    import win32api
    import win32con
except ImportError:
    print("错误: 请先安装pywin32库")
    print("运行: pip install pywin32")
    raise


class ScreenHelper:
    """屏幕位置辅助工具类"""
    
    def __init__(self):
        """初始化屏幕辅助工具"""
        self.cached_screen_info = None
        self.cache_time = 0
        self.cache_duration = 5.0  # 缓存5秒
        
        print("✓ 屏幕辅助工具初始化完成")
    
    def get_cursor_position(self) -> Tuple[int, int]:
        """获取鼠标当前位置
        
        Returns:
            鼠标坐标 (x, y)
        """
        try:
            return win32gui.GetCursorPos()
        except Exception as e:
            print(f"获取鼠标位置失败: {e}")
            # 返回屏幕中心作为默认值
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            return (screen_width // 2, screen_height // 2)
    
    def get_screen_metrics(self) -> dict:
        """获取屏幕尺寸信息
        
        Returns:
            包含屏幕信息的字典
        """
        try:
            import time
            current_time = time.time()
            
            # 检查缓存
            if (self.cached_screen_info and 
                current_time - self.cache_time < self.cache_duration):
                return self.cached_screen_info
            
            # 获取主屏幕信息
            screen_info = {
                'width': win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                'height': win32api.GetSystemMetrics(win32con.SM_CYSCREEN),
                'work_width': win32api.GetSystemMetrics(win32con.SM_CXFULLSCREEN),
                'work_height': win32api.GetSystemMetrics(win32con.SM_CYFULLSCREEN),
                'virtual_width': win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN),
                'virtual_height': win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN),
                'virtual_left': win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN),
                'virtual_top': win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            }
            
            # 更新缓存
            self.cached_screen_info = screen_info
            self.cache_time = current_time
            
            return screen_info
            
        except Exception as e:
            print(f"获取屏幕信息失败: {e}")
            # 返回默认值
            return {
                'width': 1920,
                'height': 1080,
                'work_width': 1920,
                'work_height': 1040,
                'virtual_width': 1920,
                'virtual_height': 1080,
                'virtual_left': 0,
                'virtual_top': 0
            }
    
    def get_screen_center(self) -> Tuple[int, int]:
        """获取屏幕中心位置
        
        Returns:
            屏幕中心坐标 (x, y)
        """
        screen_info = self.get_screen_metrics()
        center_x = screen_info['width'] // 2
        center_y = screen_info['height'] // 2
        return (center_x, center_y)
    
    def get_optimal_window_position(self, window_size: Tuple[int, int]) -> Tuple[int, int]:
        """计算窗口最佳显示位置
        
        Args:
            window_size: 窗口尺寸 (width, height)
            
        Returns:
            窗口左上角坐标 (x, y)
        """
        try:
            # 获取鼠标位置
            cursor_x, cursor_y = self.get_cursor_position()
            
            # 获取屏幕信息
            screen_info = self.get_screen_metrics()
            
            # 计算以鼠标为中心的窗口位置
            window_width, window_height = window_size
            
            # 初始位置：鼠标位置居中
            window_x = cursor_x - window_width // 2
            window_y = cursor_y - window_height // 2
            
            # 边界检查和调整
            window_x, window_y = self._adjust_window_position(
                window_x, window_y, window_width, window_height, screen_info
            )
            
            print(f"计算窗口位置: 鼠标({cursor_x}, {cursor_y}) -> 窗口({window_x}, {window_y})")
            
            return (window_x, window_y)
            
        except Exception as e:
            print(f"计算窗口位置失败: {e}")
            # 返回屏幕中心位置
            center_x, center_y = self.get_screen_center()
            return (center_x - window_size[0] // 2, center_y - window_size[1] // 2)
    
    def _adjust_window_position(self, x: int, y: int, width: int, height: int, 
                              screen_info: dict) -> Tuple[int, int]:
        """调整窗口位置确保在屏幕边界内
        
        Args:
            x, y: 窗口左上角坐标
            width, height: 窗口尺寸
            screen_info: 屏幕信息
            
        Returns:
            调整后的窗口坐标 (x, y)
        """
        # 使用工作区域尺寸（排除任务栏）
        max_x = screen_info['work_width'] - width
        max_y = screen_info['work_height'] - height
        
        # 确保窗口不超出屏幕边界
        adjusted_x = max(0, min(x, max_x))
        adjusted_y = max(0, min(y, max_y))
        
        # 如果窗口太大，居中显示
        if width > screen_info['work_width']:
            adjusted_x = (screen_info['work_width'] - width) // 2
        if height > screen_info['work_height']:
            adjusted_y = (screen_info['work_height'] - height) // 2
        
        return (adjusted_x, adjusted_y)
    
    def get_monitor_from_point(self, point: Tuple[int, int]) -> Optional[dict]:
        """获取指定点所在的显示器信息
        
        Args:
            point: 屏幕坐标 (x, y)
            
        Returns:
            显示器信息字典，如果失败则返回None
        """
        try:
            # 获取指定点的显示器句柄
            monitor_handle = win32api.MonitorFromPoint(point, win32con.MONITOR_DEFAULTTONEAREST)
            
            if monitor_handle:
                # 获取显示器信息
                monitor_info = win32api.GetMonitorInfo(monitor_handle)
                
                return {
                    'handle': monitor_handle,
                    'monitor_rect': monitor_info['Monitor'],      # 显示器完整区域
                    'work_rect': monitor_info['Work'],           # 工作区域（排除任务栏）
                    'is_primary': monitor_info['Flags'] == win32con.MONITORINFOF_PRIMARY
                }
            
        except Exception as e:
            print(f"获取显示器信息失败: {e}")
        
        return None
    
    def get_all_monitors(self) -> list:
        """获取所有显示器信息
        
        Returns:
            显示器信息列表
        """
        monitors = []
        
        def monitor_enum_proc(monitor_handle, device_context, rect, data):
            try:
                monitor_info = win32api.GetMonitorInfo(monitor_handle)
                monitors.append({
                    'handle': monitor_handle,
                    'monitor_rect': monitor_info['Monitor'],
                    'work_rect': monitor_info['Work'],
                    'is_primary': monitor_info['Flags'] == win32con.MONITORINFOF_PRIMARY
                })
            except:
                pass
            return True
        
        try:
            win32api.EnumDisplayMonitors(None, None, monitor_enum_proc, None)
        except Exception as e:
            print(f"枚举显示器失败: {e}")
        
        return monitors
    
    def get_optimal_window_position_multiscreen(self, window_size: Tuple[int, int]) -> Tuple[int, int]:
        """多屏幕环境下计算窗口最佳显示位置
        
        Args:
            window_size: 窗口尺寸 (width, height)
            
        Returns:
            窗口左上角坐标 (x, y)
        """
        try:
            # 获取鼠标位置
            cursor_pos = self.get_cursor_position()
            
            # 获取鼠标所在的显示器
            monitor_info = self.get_monitor_from_point(cursor_pos)
            
            if monitor_info:
                # 使用鼠标所在显示器的工作区域
                work_rect = monitor_info['work_rect']
                work_left, work_top, work_right, work_bottom = work_rect
                
                work_width = work_right - work_left
                work_height = work_bottom - work_top
                
                # 计算在该显示器中的居中位置
                window_x = work_left + (work_width - window_size[0]) // 2
                window_y = work_top + (work_height - window_size[1]) // 2
                
                # 确保窗口完全在工作区域内
                window_x = max(work_left, min(window_x, work_right - window_size[0]))
                window_y = max(work_top, min(window_y, work_bottom - window_size[1]))
                
                print(f"多屏幕定位: 显示器({work_left}, {work_top}, {work_right}, {work_bottom}) -> 窗口({window_x}, {window_y})")
                
                return (window_x, window_y)
            
        except Exception as e:
            print(f"多屏幕窗口定位失败: {e}")
        
        # 回退到单屏幕模式
        return self.get_optimal_window_position(window_size)
    
    def is_point_visible(self, point: Tuple[int, int]) -> bool:
        """检查指定点是否在可见屏幕区域内
        
        Args:
            point: 屏幕坐标 (x, y)
            
        Returns:
            是否可见
        """
        try:
            x, y = point
            screen_info = self.get_screen_metrics()
            
            # 检查是否在虚拟屏幕范围内
            virtual_left = screen_info['virtual_left']
            virtual_top = screen_info['virtual_top']
            virtual_right = virtual_left + screen_info['virtual_width']
            virtual_bottom = virtual_top + screen_info['virtual_height']
            
            return (virtual_left <= x <= virtual_right and 
                   virtual_top <= y <= virtual_bottom)
            
        except:
            return False
    
    def clear_cache(self):
        """清除缓存的屏幕信息"""
        self.cached_screen_info = None
        self.cache_time = 0
        print("✓ 屏幕信息缓存已清除")