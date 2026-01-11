"""
切换控制和批量操作模块

提供批量窗口操作和切换控制功能。
"""

import time
import threading
from typing import List, Dict, Optional

from .window_activator import WindowActivator
from .window_enumerator import WindowEnumerator


class SwitchController:
    """切换控制器"""
    
    def __init__(self, activator: WindowActivator, enumerator: WindowEnumerator):
        self.activator = activator
        self.enumerator = enumerator
        
        # 切换中止机制
        self._abort_switch = False
        self._switch_lock = threading.Lock()
        self._current_switch_id = None
    
    def activate_multiple_windows(self, hwnds: List[int], delay: float = 0.1, switch_id: str = None) -> Dict[int, bool]:
        """批量激活多个窗口（支持中止）"""
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
                success = self.activator.activate_window(hwnd)
                results[hwnd] = success
                
                if success:
                    print(f"✓ 已激活窗口 {i+1}/{len(hwnds)}: {hwnd}")
                else:
                    window_info = self.enumerator.get_window_info(hwnd)
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
        print(f"激活完成: {success_count}/{len(hwnds)} 个窗口成功 (ID: {switch_id})")
        
        return results
    
    def abort_current_switch(self, new_switch_id: str = None) -> bool:
        """中止当前正在进行的切换操作"""
        with self._switch_lock:
            if self._current_switch_id is not None:
                print(f"⚠️ 中止当前切换: {self._current_switch_id}")
                self._abort_switch = True
                time.sleep(0.05)
                return True
            return False
    
    def _should_abort_switch(self, switch_id: str) -> bool:
        """检查是否应该中止当前切换"""
        if not switch_id:
            return False
            
        with self._switch_lock:
            if self._abort_switch and self._current_switch_id == switch_id:
                return True
            if self._current_switch_id != switch_id:
                return True
            return False
    
    def get_current_switch_id(self) -> Optional[str]:
        """获取当前正在执行的切换ID"""
        with self._switch_lock:
            return self._current_switch_id