"""
窗口状态管理器模块

负责窗口拖拽检测、位置保存等状态管理逻辑
从MainWindow中提取，遵循单一职责原则
"""

import time
from typing import Optional, Tuple
from abc import ABC, abstractmethod

try:
    import win32api
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("警告: win32api不可用，拖拽检测功能将被禁用")


class IWindowManager(ABC):
    """窗口管理器接口"""
    
    @abstractmethod
    def save_position(self) -> None:
        """保存窗口位置"""
        pass
    
    @abstractmethod
    def restore_position(self) -> None:
        """恢复窗口位置"""
        pass
    
    @abstractmethod
    def detect_drag(self) -> bool:
        """检测窗口是否被拖拽"""
        pass
    
    @abstractmethod
    def reset_drag_state(self) -> None:
        """重置拖拽状态"""
        pass


class IWindowProvider(ABC):
    """窗口提供器接口 - 定义WindowStateManager需要的窗口操作"""
    
    @abstractmethod
    def get_window(self):
        """获取窗口对象"""
        pass
    
    @abstractmethod
    def get_config(self):
        """获取配置对象"""
        pass


class WindowStateManager(IWindowManager):
    """窗口状态管理器实现"""
    
    def __init__(self, window_provider: IWindowProvider):
        """初始化窗口状态管理器
        
        Args:
            window_provider: 窗口提供器接口实现
        """
        self.window_provider = window_provider
        
        # 拖拽状态跟踪
        self.window_was_dragged = False
        self.last_mouse_pos: Optional[Tuple[int, int]] = None
        self.mouse_press_time: Optional[float] = None

        # 拖拽检测参数 - 优化以减少误触
        self.drag_threshold = 5  # 拖拽检测阈值（像素）- 从3增加到5
        self.drag_time_threshold = 0.2  # 拖拽时间阈值（秒）- 少于200ms视为点击
        
        print("[OK] 窗口状态管理器初始化完成")
    
    def detect_drag(self) -> bool:
        """检测窗口是否被拖拽

        Returns:
            bool: 当前是否处于拖拽状态
        """
        if not WIN32_AVAILABLE:
            return False

        try:
            # 获取当前鼠标位置
            current_mouse_pos = win32api.GetCursorPos()

            # 检查鼠标左键状态
            left_button_pressed = win32api.GetKeyState(0x01) < 0

            if left_button_pressed:
                # 鼠标按下，记录起始位置和时间
                if self.last_mouse_pos is None:
                    self.last_mouse_pos = current_mouse_pos
                    self.mouse_press_time = time.time()
                    self.window_was_dragged = False
                else:
                    # 计算鼠标按下的持续时间
                    press_duration = time.time() - self.mouse_press_time if self.mouse_press_time else 0

                    # 如果按下时间很短，视为点击而非拖拽
                    if press_duration < self.drag_time_threshold:
                        self.window_was_dragged = False
                        return False

                    # 检查鼠标是否移动了
                    dx = abs(current_mouse_pos[0] - self.last_mouse_pos[0])
                    dy = abs(current_mouse_pos[1] - self.last_mouse_pos[1])

                    # 如果移动距离超过阈值，认为是拖拽
                    if dx > self.drag_threshold or dy > self.drag_threshold:
                        self.window_was_dragged = True
            else:
                # 鼠标释放，重置状态（但保留拖拽标记一小段时间）
                if self.last_mouse_pos is not None:
                    self.last_mouse_pos = None
                    self.mouse_press_time = None
                    # 不立即重置 window_was_dragged，让事件处理器有时间检查

        except Exception as e:
            print(f"检查拖拽状态失败: {e}")

        return self.window_was_dragged
    
    def reset_drag_state(self) -> None:
        """重置拖拽状态"""
        self.window_was_dragged = False
        self.last_mouse_pos = None
        self.mouse_press_time = None
    
    def is_dragged(self) -> bool:
        """获取当前拖拽状态"""
        return self.window_was_dragged
    
    def save_position(self) -> None:
        """保存窗口位置"""
        try:
            window = self.window_provider.get_window()
            config = self.window_provider.get_config()
            
            if not window:
                return
            
            window_config = config.get_window_config()
            if not window_config.get("remember_position", True):
                return
            
            location = window.current_location()
            size = window.size
            
            if location and size:
                config.update_window_position(
                    location[0], location[1], size[0], size[1]
                )
                print(f"[OK] 窗口位置已保存: {location}, 大小: {size}")
            
        except Exception as e:
            print(f"保存窗口位置失败: {e}")
    
    def get_current_window_position(self) -> Optional[Tuple[int, int]]:
        """获取当前窗口位置
        
        Returns:
            当前窗口位置 (x, y) 或 None
        """
        try:
            window = self.window_provider.get_window()
            if window and hasattr(window, 'current_location'):
                location = window.current_location()
                if location and len(location) == 2:
                    return location
        except Exception as e:
            print(f"获取当前窗口位置失败: {e}")
        return None
    
    def get_current_window_size(self) -> Optional[Tuple[int, int]]:
        """获取当前窗口尺寸
        
        Returns:
            当前窗口尺寸 (width, height) 或 None
        """
        try:
            window = self.window_provider.get_window()
            if window and hasattr(window, 'size'):
                size = window.size
                if size and len(size) == 2:
                    return size
        except Exception as e:
            print(f"获取当前窗口尺寸失败: {e}")
        return None
    
    def get_window_info_for_dialogs(self) -> dict:
        """获取用于对话框位置计算的窗口信息
        
        Returns:
            包含位置和尺寸信息的字典
        """
        try:
            position = self.get_current_window_position()
            size = self.get_current_window_size()
            
            return {
                'position': position,
                'size': size,
                'has_position': position is not None,
                'has_size': size is not None
            }
        except Exception as e:
            print(f"获取窗口信息失败: {e}")
            return {
                'position': None,
                'size': None,
                'has_position': False,
                'has_size': False
            }

    def restore_position(self) -> None:
        """恢复窗口位置"""
        try:
            config = self.window_provider.get_config()
            window_config = config.get_window_config()
            
            if window_config.get("remember_position", True):
                x = window_config.get("x", 200)
                y = window_config.get("y", 100)
                print(f"[OK] 窗口位置将恢复到: ({x}, {y})")
                return (x, y)
            
        except Exception as e:
            print(f"恢复窗口位置失败: {e}")
        
        return None
    
    def get_drag_threshold(self) -> int:
        """获取拖拽检测阈值"""
        return self.drag_threshold
    
    def set_drag_threshold(self, threshold: int) -> None:
        """设置拖拽检测阈值
        
        Args:
            threshold: 拖拽检测阈值（像素）
        """
        if threshold > 0:
            self.drag_threshold = threshold
            print(f"[OK] 拖拽检测阈值设置为: {threshold}px")
    
    def get_mouse_info(self) -> dict:
        """获取鼠标状态信息（用于调试）"""
        return {
            "was_dragged": self.window_was_dragged,
            "last_pos": self.last_mouse_pos,
            "press_time": self.mouse_press_time,
            "threshold": self.drag_threshold
        }