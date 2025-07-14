"""
Explorer窗口辅助模块

提供Explorer窗口的路径获取和恢复功能:
- 获取Explorer窗口的当前文件夹路径
- 重新创建Explorer窗口并定位到指定路径
- 窗口位置和大小控制
- 多显示器支持
"""

import time
import subprocess
import win32gui
import win32con
import win32api
import win32process
import win32com.client
from typing import Optional, List, Tuple
from urllib.parse import unquote
from pythoncom import CoInitialize, CoUninitialize

from utils.screen_helper import ScreenHelper


class ExplorerHelper:
    """Explorer窗口辅助类"""
    
    def __init__(self):
        """初始化Explorer辅助类"""
        self.screen_helper = ScreenHelper()
    
    def is_explorer_window(self, hwnd: int) -> bool:
        """检查窗口是否为Explorer窗口
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            是否为Explorer窗口
        """
        try:
            class_name = win32gui.GetClassName(hwnd)
            return class_name == 'CabinetWClass'
        except Exception:
            return False
    
    def get_explorer_folder_path(self, hwnd: int) -> Optional[str]:
        """获取Explorer窗口的当前文件夹路径
        
        Args:
            hwnd: Explorer窗口句柄
            
        Returns:
            文件夹路径，如果获取失败返回None
        """
        if not self.is_explorer_window(hwnd):
            return None
        
        try:
            # 初始化COM
            CoInitialize()
            
            # 获取Shell.Application对象
            shell = win32com.client.Dispatch("Shell.Application")
            
            # 遍历所有窗口查找匹配的HWND
            for window in shell.Windows():
                try:
                    if window.HWND == hwnd:
                        location_url = window.LocationURL
                        if location_url:
                            # 处理file:///格式的URL
                            if location_url.startswith("file:///"):
                                folder_path = unquote(location_url[8:])  # 移除"file:///"
                                return folder_path
                            # 处理特殊位置（如库、桌面等）
                            elif hasattr(window, 'LocationName'):
                                return window.LocationName
                except Exception as e:
                    # 单个窗口处理失败不影响其他窗口
                    continue
            
            return None
            
        except Exception as e:
            print(f"获取Explorer路径失败: {e}")
            return None
        finally:
            try:
                CoUninitialize()
            except:
                pass
    
    def get_hwnds_for_pid(self, pid: int) -> List[int]:
        """根据进程ID获取所有窗口句柄
        
        Args:
            pid: 进程ID
            
        Returns:
            窗口句柄列表
        """
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                try:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == pid:
                        hwnds.append(hwnd)
                except Exception:
                    pass
            return True
        
        hwnds = []
        try:
            win32gui.EnumWindows(callback, hwnds)
        except Exception:
            pass
        
        return hwnds
    
    def create_explorer_window(self, folder_path: str, 
                             target_rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """创建Explorer窗口并定位到指定路径和位置
        
        Args:
            folder_path: 要打开的文件夹路径
            target_rect: 目标窗口位置 (left, top, right, bottom)，None则使用默认位置
            
        Returns:
            是否成功创建和定位窗口
        """
        if not folder_path:
            return False
        
        try:
            # 方法1: 使用ShellExecute（更可靠）
            result = win32api.ShellExecute(
                0, "open", folder_path, None, None, win32con.SW_SHOWNORMAL
            )
            
            # 等待窗口创建
            time.sleep(0.5)
            
            # 如果没有指定目标位置，直接返回成功
            if not target_rect:
                return True
            
            # 查找新创建的Explorer窗口
            new_hwnd = self._find_latest_explorer_window(folder_path)
            if new_hwnd:
                return self._position_and_maximize_window(new_hwnd, target_rect)
            
            return True  # 即使定位失败，窗口创建成功
            
        except Exception as e:
            print(f"创建Explorer窗口失败: {e}")
            try:
                # 方法2: 使用subprocess作为后备
                subprocess.Popen(f'explorer "{folder_path}"', shell=True)
                return True
            except Exception as e2:
                print(f"后备方法也失败: {e2}")
                return False
    
    def _find_latest_explorer_window(self, folder_path: str, 
                                   timeout: float = 2.0) -> Optional[int]:
        """查找最新创建的Explorer窗口
        
        Args:
            folder_path: 预期的文件夹路径
            timeout: 查找超时时间（秒）
            
        Returns:
            窗口句柄，如果未找到返回None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 获取当前所有Explorer窗口
                explorer_hwnds = self._get_all_explorer_windows()
                
                # 检查每个窗口的路径
                for hwnd in explorer_hwnds:
                    current_path = self.get_explorer_folder_path(hwnd)
                    if current_path and self._paths_match(current_path, folder_path):
                        return hwnd
                
                time.sleep(0.1)  # 短暂等待
                
            except Exception:
                continue
        
        # 如果找不到匹配路径的窗口，返回最新的Explorer窗口
        try:
            explorer_hwnds = self._get_all_explorer_windows()
            if explorer_hwnds:
                return explorer_hwnds[-1]  # 返回最后一个（通常是最新的）
        except Exception:
            pass
        
        return None
    
    def _get_all_explorer_windows(self) -> List[int]:
        """获取所有Explorer窗口句柄"""
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd) and self.is_explorer_window(hwnd):
                hwnds.append(hwnd)
            return True
        
        hwnds = []
        try:
            win32gui.EnumWindows(callback, hwnds)
        except Exception:
            pass
        
        return hwnds
    
    def _paths_match(self, path1: str, path2: str) -> bool:
        """检查两个路径是否匹配"""
        if not path1 or not path2:
            return False
        
        try:
            # 标准化路径格式
            path1 = path1.replace('/', '\\').rstrip('\\').lower()
            path2 = path2.replace('/', '\\').rstrip('\\').lower()
            return path1 == path2
        except Exception:
            return False
    
    def _position_and_maximize_window(self, hwnd: int, 
                                    target_rect: Optional[Tuple[int, int, int, int]]) -> bool:
        """定位窗口到指定屏幕并最大化
        
        Args:
            hwnd: 窗口句柄
            target_rect: 目标位置 (left, top, right, bottom)
            
        Returns:
            是否成功定位和最大化
        """
        try:
            # 如果没有目标位置信息，只进行最大化
            if not target_rect:
                print(f"    没有位置信息，只进行最大化")
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                win32gui.SetForegroundWindow(hwnd)
                return True
            
            # 获取目标位置所在的显示器
            target_point = (target_rect[0], target_rect[1])
            print(f"    目标点: {target_point}")
            target_monitor = self.screen_helper.get_monitor_from_point(target_point)
            
            if target_monitor:
                # 获取显示器的工作区域
                work_area = target_monitor.get('work_rect')
                print(f"    目标显示器工作区: {work_area}")
                if work_area:
                    # 先将窗口移动到目标显示器
                    print(f"    正在将窗口移动到显示器: {work_area}")
                    win32gui.SetWindowPos(
                        hwnd, 0,
                        work_area[0], work_area[1],
                        work_area[2] - work_area[0],
                        work_area[3] - work_area[1],
                        win32con.SWP_NOZORDER
                    )
                    
                    # 短暂等待位置生效
                    time.sleep(0.1)
                else:
                    print(f"    警告: 无法获取显示器工作区域")
            else:
                print(f"    警告: 无法找到目标点对应的显示器")
            
            # 最大化窗口
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            
            # 确保窗口在前台
            win32gui.SetForegroundWindow(hwnd)
            
            return True
            
        except Exception as e:
            print(f"定位和最大化窗口失败: {e}")
            try:
                # 降级处理：只尝试最大化
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return True
            except Exception:
                return False
    
    def get_window_rect(self, hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口位置和大小
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            窗口矩形 (left, top, right, bottom)，失败返回None
        """
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None
    
    def restore_explorer_window(self, folder_path: str, 
                              original_rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """恢复Explorer窗口到指定路径和位置
        
        这是主要的公共接口，用于恢复失效的Explorer窗口
        
        Args:
            folder_path: 要恢复的文件夹路径
            original_rect: 原始窗口位置
            
        Returns:
            是否成功恢复
        """
        if not folder_path:
            return False
        
        print(f"正在恢复Explorer窗口: {folder_path}")
        
        success = self.create_explorer_window(folder_path, original_rect)
        
        if success:
            print(f"✓ Explorer窗口恢复成功: {folder_path}")
        else:
            print(f"✗ Explorer窗口恢复失败: {folder_path}")
        
        return success