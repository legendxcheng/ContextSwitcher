"""
弹窗辅助工具模块

提供统一的弹窗接口，替代FreeSimpleGUI的popup函数，
确保所有弹窗都能显示在主窗口所在的屏幕上。
"""

from typing import Tuple, Optional, Any
from gui.modern_config import ModernUIConfig


def show_message(message: str, title: str = "提示", 
               main_window_position: Tuple[int, int] = None) -> None:
    """显示信息提示弹窗
    
    Args:
        message: 消息内容
        title: 弹窗标题
        main_window_position: 主窗口位置，用于计算弹窗位置
    """
    ModernUIConfig.create_message_dialog(
        message=message, 
        title=title, 
        dialog_type="info",
        main_window_position=main_window_position
    )


def show_warning(message: str, title: str = "警告", 
               main_window_position: Tuple[int, int] = None) -> None:
    """显示警告弹窗
    
    Args:
        message: 消息内容
        title: 弹窗标题
        main_window_position: 主窗口位置，用于计算弹窗位置
    """
    ModernUIConfig.create_message_dialog(
        message=message, 
        title=title, 
        dialog_type="warning",
        main_window_position=main_window_position
    )


def show_error(message: str, title: str = "错误", 
             main_window_position: Tuple[int, int] = None) -> None:
    """显示错误弹窗
    
    Args:
        message: 消息内容
        title: 弹窗标题
        main_window_position: 主窗口位置，用于计算弹窗位置
    """
    ModernUIConfig.create_message_dialog(
        message=message, 
        title=title, 
        dialog_type="error",
        main_window_position=main_window_position
    )


def show_question(message: str, title: str = "确认", 
                main_window_position: Tuple[int, int] = None) -> bool:
    """显示确认弹窗
    
    Args:
        message: 消息内容
        title: 弹窗标题
        main_window_position: 主窗口位置，用于计算弹窗位置
        
    Returns:
        用户选择结果（True=是，False=否）
    """
    return ModernUIConfig.create_message_dialog(
        message=message, 
        title=title, 
        dialog_type="question",
        main_window_position=main_window_position
    )


def show_timed_message(message: str, duration: int = 2, title: str = "提示",
                     main_window_position: Tuple[int, int] = None) -> None:
    """显示定时自动关闭的消息弹窗
    
    Args:
        message: 消息内容
        duration: 自动关闭时间（秒）
        title: 弹窗标题
        main_window_position: 主窗口位置，用于计算弹窗位置
    """
    try:
        import FreeSimpleGUI as sg
        from utils.dialog_position_manager import get_dialog_position_manager
        
        # 计算弹窗位置
        dialog_size = (350, 120)
        dialog_position = None
        
        if main_window_position:
            try:
                position_manager = get_dialog_position_manager()
                dialog_position = position_manager.get_popup_position(
                    dialog_size, main_window_position
                )
            except Exception as e:
                print(f"计算定时弹窗位置失败: {e}")
        
        # 创建布局
        layout = [
            [sg.Text(f"ℹ️ {message}", font=ModernUIConfig.FONTS['body'], 
                    text_color=ModernUIConfig.COLORS['text'], justification='center')],
            [sg.Text("")],  # 空行
            [sg.Text(f"将在 {duration} 秒后自动关闭", 
                    font=ModernUIConfig.FONTS['small'], 
                    text_color=ModernUIConfig.COLORS['text_secondary'], 
                    justification='center')]
        ]
        
        # 窗口配置
        window_config = {
            'title': title,
            'modal': False,  # 定时弹窗不阻塞
            'keep_on_top': True,
            'finalize': True,
            'resizable': False,
            'size': dialog_size,
            'no_titlebar': True,  # 定时弹窗无标题栏
            'alpha_channel': 0.9,
            'background_color': ModernUIConfig.COLORS['background'],
            'margins': (15, 12),
            'element_padding': (5, 4),
            'auto_close': True,
            'auto_close_duration': duration
        }
        
        if dialog_position:
            window_config['location'] = dialog_position
        
        # 获取图标
        icon_path = ModernUIConfig._get_icon_path()
        if icon_path:
            window_config['icon'] = icon_path
        
        # 创建并显示定时弹窗
        dialog = sg.Window(layout=layout, **window_config)
        
        # 简单的事件循环，等待自动关闭
        import time
        start_time = time.time()
        while time.time() - start_time < duration + 0.5:  # 多等0.5秒确保关闭
            event, values = dialog.read(timeout=100)
            if event in (sg.WIN_CLOSED, sg.TIMEOUT_EVENT):
                break
        
        dialog.close()
        
    except Exception as e:
        print(f"显示定时弹窗失败: {e}")
        # 回退到标准弹窗
        try:
            import FreeSimpleGUI as sg
            sg.popup_timed(message, auto_close_duration=duration, title=title)
        except:
            print(f"回退弹窗也失败，消息: {message}")


class PopupManager:
    """弹窗管理器，用于在有父窗口上下文时自动获取位置"""
    
    def __init__(self, parent_window = None):
        """初始化弹窗管理器
        
        Args:
            parent_window: 父窗口对象
        """
        self.parent_window = parent_window
    
    def _get_main_window_position(self) -> Optional[Tuple[int, int]]:
        """获取主窗口位置"""
        try:
            if self.parent_window and hasattr(self.parent_window, 'current_location'):
                location = self.parent_window.current_location()
                if location and len(location) == 2:
                    return location
        except Exception as e:
            print(f"获取主窗口位置失败: {e}")
        return None
    
    def show_message(self, message: str, title: str = "提示") -> None:
        """显示信息提示弹窗"""
        show_message(message, title, self._get_main_window_position())
    
    def show_warning(self, message: str, title: str = "警告") -> None:
        """显示警告弹窗"""
        show_warning(message, title, self._get_main_window_position())
    
    def show_error(self, message: str, title: str = "错误") -> None:
        """显示错误弹窗"""
        show_error(message, title, self._get_main_window_position())
    
    def show_question(self, message: str, title: str = "确认") -> bool:
        """显示确认弹窗"""
        return show_question(message, title, self._get_main_window_position())
    
    def show_timed_message(self, message: str, duration: int = 2, title: str = "提示") -> None:
        """显示定时自动关闭的消息弹窗"""
        show_timed_message(message, duration, title, self._get_main_window_position())


# 全局便捷函数，兼容原有sg.popup调用方式
def popup(message: str, title: str = "提示", 
         main_window_position: Tuple[int, int] = None) -> None:
    """兼容sg.popup的便捷函数"""
    show_message(message, title, main_window_position)


def popup_yes_no(message: str, title: str = "确认", 
               main_window_position: Tuple[int, int] = None) -> str:
    """兼容sg.popup_yes_no的便捷函数"""
    result = show_question(message, title, main_window_position)
    return "Yes" if result else "No"


def popup_timed(message: str, auto_close_duration: int = 2, title: str = "提示",
              main_window_position: Tuple[int, int] = None) -> None:
    """兼容sg.popup_timed的便捷函数"""
    show_timed_message(message, auto_close_duration, title, main_window_position)