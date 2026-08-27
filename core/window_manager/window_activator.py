"""
窗口激活策略模块

提供多种窗口激活策略，确保在不同Windows环境下都能成功激活窗口。
从原始 window_manager.py 中提取窗口激活逻辑。
"""

import time

try:
    import win32gui
    import win32con
    import win32process
    import win32api
except ImportError:
    print("错误: 请先安装pywin32库")
    print("运行: pip install pywin32")
    raise

from .window_enumerator import WindowEnumerator


class WindowActivator:
    """窗口激活器
    
    提供多种窗口激活策略，处理Windows系统的各种激活限制。
    """
    
    def __init__(self, enumerator: WindowEnumerator):
        """初始化窗口激活器
        
        Args:
            enumerator: 窗口枚举器实例
        """
        self.enumerator = enumerator
    
    def activate_window(self, hwnd: int) -> bool:
        """使用多阶段策略激活指定窗口到前台
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            是否成功激活
        """
        try:
            if not self.enumerator.is_window_valid(hwnd):
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