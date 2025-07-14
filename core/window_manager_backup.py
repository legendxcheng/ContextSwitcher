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
import threading
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
        
        # 切换中止机制
        self._abort_switch = False
        self._switch_lock = threading.Lock()
        self._current_switch_id = None
        
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
        """使用多阶段策略激活指定窗口到前台
        
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
            current_fg = win32gui.GetForegroundWindow()
            if current_fg == hwnd:
                return True
            
            return self._activate_window_robust(hwnd)
        
        except Exception as e:
            print(f"激活窗口时出错: {e}")
            return False
    
    def _activate_window_robust(self, hwnd: int, max_retries: int = 3) -> bool:
        """强化的窗口激活方法，使用多种策略"""
        
        for attempt in range(max_retries):
            print(f"尝试激活窗口 (第{attempt + 1}次): {hwnd}")
            
            # 策略1: ALT键技巧 + SetForegroundWindow
            if self._try_alt_key_activation(hwnd):
                print(f"✅ ALT键激活成功")
                return True
            
            # 策略2: 传统方法
            if self._try_traditional_activation(hwnd):
                print(f"✅ 传统激活成功")
                return True
            
            # 策略3: 线程输入附加方法
            if self._try_thread_attach_activation(hwnd):
                print(f"✅ 线程附加激活成功")
                return True
            
            # 策略4: 窗口位置激活
            if self._try_window_position_activation(hwnd):
                print(f"✅ 窗口位置激活成功")
                return True
            
            # 重试前等待
            if attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))  # 指数退避
        
        print(f"❌ 所有激活策略都失败了")
        return False
    
    def _try_alt_key_activation(self, hwnd: int) -> bool:
        """策略1: 使用ALT键技巧激活窗口"""
        try:
            # 发送ALT键来解除前台锁定
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')  # 发送ALT键
                time.sleep(0.05)
            except:
                # 如果COM方法失败，使用直接的键盘输入
                win32api.keybd_event(0x12, 0, 0, 0)  # ALT down
                win32api.keybd_event(0x12, 0, win32con.KEYEVENTF_KEYUP, 0)  # ALT up
                time.sleep(0.05)
            
            # 恢复窗口（如果最小化）
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
            
            # 尝试设置前台窗口
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
            
            # 验证是否成功
            return win32gui.GetForegroundWindow() == hwnd
            
        except Exception as e:
            print(f"ALT键激活失败: {e}")
            return False
    
    def _try_traditional_activation(self, hwnd: int) -> bool:
        """策略2: 传统激活方法"""
        try:
            # 恢复窗口
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
            
            # 显示窗口
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            
            # 设置前台窗口
            win32gui.SetForegroundWindow(hwnd)
            
            # 置顶窗口
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOP, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            time.sleep(0.05)
            return win32gui.GetForegroundWindow() == hwnd
            
        except Exception as e:
            print(f"传统激活失败: {e}")
            return False
    
    def _try_thread_attach_activation(self, hwnd: int) -> bool:
        """策略3: 线程输入附加方法"""
        try:
            # 获取前台窗口的线程ID
            current_fg = win32gui.GetForegroundWindow()
            if current_fg == 0:
                return False
            
            current_thread = win32process.GetWindowThreadProcessId(current_fg)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            
            if current_thread != target_thread:
                # 附加线程输入
                win32process.AttachThreadInput(current_thread, target_thread, True)
                try:
                    # 激活窗口
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.SetFocus(hwnd)
                    time.sleep(0.05)
                    result = win32gui.GetForegroundWindow() == hwnd
                finally:
                    # 分离线程输入
                    win32process.AttachThreadInput(current_thread, target_thread, False)
                
                return result
            else:
                return False
                
        except Exception as e:
            print(f"线程附加激活失败: {e}")
            return False
    
    def _try_window_position_activation(self, hwnd: int) -> bool:
        """策略4: 窗口位置激活方法"""
        try:
            # 将窗口置于最顶层
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            time.sleep(0.02)
            
            # 取消置顶，但保持在普通窗口的最前面
            win32gui.SetWindowPos(
                hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            
            # 尝试设置焦点
            try:
                win32gui.SetForegroundWindow(hwnd)
            except:
                pass
            
            time.sleep(0.05)
            return win32gui.GetForegroundWindow() == hwnd
            
        except Exception as e:
            print(f"窗口位置激活失败: {e}")
            return False
    
    def activate_multiple_windows(self, hwnds: List[int], delay: float = 0.1, switch_id: str = None) -> Dict[int, bool]:
        """批量激活多个窗口（支持中止）
        
        Args:
            hwnds: 窗口句柄列表
            delay: 窗口间切换延迟（秒）
            switch_id: 切换操作ID，用于中止检测
            
        Returns:
            每个窗口的激活结果 {hwnd: success}
        """
        results = {}
        
        if not hwnds:
            return results
        
        with self._switch_lock:
            # 设置当前切换ID
            self._current_switch_id = switch_id
            self._abort_switch = False
        
        print(f"正在激活 {len(hwnds)} 个窗口... (ID: {switch_id})")
        
        for i, hwnd in enumerate(hwnds):
            # 检查是否需要中止
            if self._should_abort_switch(switch_id):
                print(f"⚠️ 切换已中止 (ID: {switch_id})")
                # 将剩余窗口标记为失败
                for remaining_hwnd in hwnds[i:]:
                    results[remaining_hwnd] = False
                break
            
            try:
                success = self.activate_window(hwnd)
                results[hwnd] = success
                
                if success:
                    print(f"✓ 已激活窗口 {i+1}/{len(hwnds)}: {hwnd}")
                else:
                    window_info = self.get_window_info(hwnd)
                    title = window_info.title if window_info else "Unknown"
                    print(f"✗ 激活失败 {i+1}/{len(hwnds)}: {hwnd} ({title})")
                
                # 窗口间延迟，同时检查中止
                if i < len(hwnds) - 1 and delay > 0:
                    # 分段延迟，更快响应中止
                    sleep_steps = max(1, int(delay * 10))  # 100ms步长
                    step_delay = delay / sleep_steps
                    
                    for _ in range(sleep_steps):
                        if self._should_abort_switch(switch_id):
                            break
                        time.sleep(step_delay)
                    
            except Exception as e:
                print(f"激活窗口时出错 {hwnd}: {e}")
                results[hwnd] = False
        
        # 清理当前切换ID
        with self._switch_lock:
            if self._current_switch_id == switch_id:
                self._current_switch_id = None
        
        success_count = sum(1 for success in results.values() if success)
        aborted = self._abort_switch and switch_id
        status = "已中止" if aborted else "完成"
        print(f"激活{status}: {success_count}/{len(hwnds)} 个窗口成功 (ID: {switch_id})")
        
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
    
    def get_active_windows_info(self) -> Dict[str, Any]:
        """获取活跃窗口信息（包括多屏幕环境）
        
        Returns:
            包含前台窗口和活跃窗口列表的信息
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
                foreground_info = self.get_window_info(foreground_hwnd)
                if foreground_info:
                    result['foreground_window'] = foreground_info
            
            # 获取所有窗口
            all_windows = self.enumerate_windows()
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
            excluded_classes = {
                'Shell_TrayWnd', 'DV2ControlHost', 'Windows.UI.Core.CoreWindow',
                'WorkerW', 'Progman', 'Button', 'Edit'
            }
            
            if window.class_name in excluded_classes:
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
            
            # 常见的应用程序进程名
            common_apps = {
                'chrome.exe', 'firefox.exe', 'edge.exe',           # 浏览器
                'code.exe', 'devenv.exe', 'notepad++.exe',          # 编辑器
                'explorer.exe', 'cmd.exe', 'powershell.exe',       # 系统工具
                'wechat.exe', 'qq.exe', 'dingding.exe',             # 通讯工具
                'winword.exe', 'excel.exe', 'powerpnt.exe',        # Office
                'photoshop.exe', 'illustrator.exe',                # 设计工具
            }
            
            process_name = window.process_name.lower()
            
            # 如果是常见应用，认为是最近可能使用的
            if process_name in common_apps:
                return True
            
            # 检查窗口标题是否包含文件名或项目名
            title_lower = window.title.lower()
            if any(ext in title_lower for ext in ['.txt', '.doc', '.pdf', '.py', '.js', '.html']):
                return True
            
            return False
            
        except Exception as e:
            print(f"检查窗口最近使用状态失败: {e}")
            return False
    
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
    
    def abort_current_switch(self, new_switch_id: str = None) -> bool:
        """中止当前正在进行的切换操作
        
        Args:
            new_switch_id: 新的切换ID（可选）
            
        Returns:
            是否有切换被中止
        """
        with self._switch_lock:
            if self._current_switch_id is not None:
                print(f"⚠️ 中止当前切换: {self._current_switch_id}")
                self._abort_switch = True
                
                # 等待一小段时间让当前切换检测到中止
                time.sleep(0.05)
                return True
            return False
    
    def _should_abort_switch(self, switch_id: str) -> bool:
        """检查是否应该中止当前切换
        
        Args:
            switch_id: 当前切换ID
            
        Returns:
            是否应该中止
        """
        if not switch_id:
            return False
            
        with self._switch_lock:
            # 如果中止标志为真且当前切换ID匹配
            if self._abort_switch and self._current_switch_id == switch_id:
                return True
            # 如果当前切换ID已经变更，也要中止
            if self._current_switch_id != switch_id:
                return True
            return False
    
    def get_current_switch_id(self) -> Optional[str]:
        """获取当前正在执行的切换ID"""
        with self._switch_lock:
            return self._current_switch_id
    
    def invalidate_cache(self):
        """清除窗口缓存，强制下次重新枚举"""
        self.cached_windows = []
        self.last_enum_time = 0