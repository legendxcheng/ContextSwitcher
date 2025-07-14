"""
Window Manager 模块

重构后的窗口管理器，按功能领域拆分为多个专职模块。
这个文件提供外观模式接口，保持向后兼容性。
"""

from typing import List, Tuple, Optional, Dict, Any

# 导入数据类和常量
from .window_info import WindowInfo

# 导入各个功能模块（延迟导入以避免循环依赖）
from .window_enumerator import WindowEnumerator
from .window_activator import WindowActivator
from .window_analyzer import WindowAnalyzer
from .window_finder import WindowFinder
from .switch_controller import SwitchController
from .cache_manager import CacheManager


class WindowManager:
    """Windows窗口管理器 - 外观模式接口
    
    这个类保持了原有的所有公共API，内部委托给专门的模块处理。
    确保了向后兼容性，同时享受模块化重构的好处。
    """
    
    def __init__(self):
        """初始化窗口管理器"""
        # 初始化各个功能模块
        self.cache_manager = CacheManager()
        self.enumerator = WindowEnumerator(self.cache_manager)
        self.activator = WindowActivator(self.enumerator)
        self.analyzer = WindowAnalyzer(self.enumerator)
        self.finder = WindowFinder(self.enumerator)
        self.switch_controller = SwitchController(self.activator, self.enumerator)
    
    # ========== 窗口枚举相关方法 ==========
    
    def enumerate_windows(self, use_cache: bool = True) -> List[WindowInfo]:
        """枚举所有可见窗口"""
        return self.enumerator.enumerate_windows(use_cache)
    
    def get_window_info(self, hwnd: int) -> Optional[WindowInfo]:
        """获取指定窗口的信息"""
        return self.enumerator.get_window_info(hwnd)
    
    def is_window_valid(self, hwnd: int) -> bool:
        """检查窗口是否仍然存在和有效"""
        return self.enumerator.is_window_valid(hwnd)
    
    def get_window_process(self, hwnd: int) -> str:
        """获取窗口的进程名"""
        return self.enumerator.get_window_process(hwnd)
    
    def invalidate_cache(self):
        """清除窗口缓存，强制下次重新枚举"""
        return self.cache_manager.invalidate_cache()
    
    # ========== 窗口激活相关方法 ==========
    
    def activate_window(self, hwnd: int) -> bool:
        """使用多阶段策略激活指定窗口到前台"""
        return self.activator.activate_window(hwnd)
    
    def activate_multiple_windows(self, hwnds: List[int], delay: float = 0.1, switch_id: str = None) -> Dict[int, bool]:
        """批量激活多个窗口（支持中止）"""
        return self.switch_controller.activate_multiple_windows(hwnds, delay, switch_id)
    
    # ========== 窗口分析相关方法 ==========
    
    def get_foreground_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口信息"""
        return self.analyzer.get_foreground_window()
    
    def get_active_windows_info(self) -> Dict[str, Any]:
        """获取活跃窗口信息（包括多屏幕环境）"""
        return self.analyzer.get_active_windows_info()
    
    # ========== 窗口查找相关方法 ==========
    
    def find_windows_by_title(self, title: str, exact_match: bool = False) -> List[WindowInfo]:
        """根据标题查找窗口"""
        return self.finder.find_windows_by_title(title, exact_match)
    
    def find_windows_by_process(self, process_name: str) -> List[WindowInfo]:
        """根据进程名查找窗口"""
        return self.finder.find_windows_by_process(process_name)
    
    def get_window_summary(self) -> Dict[str, Any]:
        """获取窗口管理器状态摘要"""
        return self.finder.get_window_summary()
    
    # ========== 切换控制相关方法 ==========
    
    def abort_current_switch(self, new_switch_id: str = None) -> bool:
        """中止当前正在进行的切换操作"""
        return self.switch_controller.abort_current_switch(new_switch_id)
    
    def get_current_switch_id(self) -> Optional[str]:
        """获取当前正在执行的切换ID"""
        return self.switch_controller.get_current_switch_id()


# 为了保持向后兼容，也导出WindowInfo
__all__ = ['WindowManager', 'WindowInfo']