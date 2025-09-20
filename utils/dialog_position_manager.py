"""
对话框位置管理器模块

统一管理所有弹窗的位置计算，确保弹窗始终显示在主窗口所在的屏幕上。
提供简单易用的API，支持不同类型弹窗的位置策略。
"""

from typing import Tuple, Optional, Any
from utils.screen_helper import ScreenHelper


class DialogPositionManager:
    """对话框位置管理器"""
    
    def __init__(self):
        """初始化对话框位置管理器"""
        self.screen_helper = ScreenHelper()
        
        # 默认位置策略
        self.default_strategy = "screen_center"  # 可选: "screen_center", "main_window_center", "main_window_offset"
        
        # 位置偏移量（用于避免完全重叠）
        self.dialog_offset = (20, 20)
        
        print("✓ 对话框位置管理器初始化完成")
    
    def get_dialog_position(self, dialog_size: Tuple[int, int], 
                           main_window_position: Tuple[int, int] = None,
                           main_window_size: Tuple[int, int] = None,
                           strategy: str = None) -> Tuple[int, int]:
        """获取对话框最佳显示位置
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)，可选
            main_window_size: 主窗口尺寸 (width, height)，可选  
            strategy: 位置策略，可选 ("screen_center", "main_window_center", "main_window_offset")
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        try:
            strategy = strategy or self.default_strategy
            
            print(f"🎯 计算对话框位置: 策略={strategy}, 尺寸={dialog_size}")
            
            if strategy == "main_window_center" and main_window_position and main_window_size:
                # 相对于主窗口中心显示
                return self.screen_helper.get_main_window_center_offset(
                    dialog_size, main_window_position, main_window_size
                )
                
            elif strategy == "main_window_offset" and main_window_position:
                # 相对于主窗口位置偏移显示
                return self._get_offset_position(dialog_size, main_window_position)
                
            else:
                # 默认策略：在主窗口所在屏幕中央显示
                return self.screen_helper.get_optimal_dialog_position(
                    dialog_size, main_window_position
                )
                
        except Exception as e:
            print(f"计算对话框位置失败: {e}")
            # 回退到基础位置计算
            return self.screen_helper.get_optimal_window_position(dialog_size)
    
    def _get_offset_position(self, dialog_size: Tuple[int, int], 
                           main_window_position: Tuple[int, int]) -> Tuple[int, int]:
        """计算相对于主窗口的偏移位置
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        try:
            main_x, main_y = main_window_position
            offset_x, offset_y = self.dialog_offset
            
            # 基础偏移位置
            dialog_x = main_x + offset_x
            dialog_y = main_y + offset_y
            
            # 获取主窗口所在屏幕信息，确保对话框在屏幕边界内
            monitor_info = self.screen_helper.get_window_screen_position(main_window_position)
            
            if monitor_info:
                work_rect = monitor_info['work_rect']
                work_left, work_top, work_right, work_bottom = work_rect
                
                dialog_width, dialog_height = dialog_size
                
                # 确保对话框完全在工作区域内
                dialog_x = max(work_left, min(dialog_x, work_right - dialog_width))
                dialog_y = max(work_top, min(dialog_y, work_bottom - dialog_height))
            
            print(f"偏移定位: 主窗口({main_x}, {main_y}) + 偏移({offset_x}, {offset_y}) -> 对话框({dialog_x}, {dialog_y})")
            
            return (dialog_x, dialog_y)
            
        except Exception as e:
            print(f"计算偏移位置失败: {e}")
            # 回退到屏幕中央
            return self.screen_helper.get_optimal_dialog_position(dialog_size, main_window_position)
    
    def get_task_dialog_position(self, dialog_size: Tuple[int, int], 
                               main_window_position: Tuple[int, int] = None) -> Tuple[int, int]:
        """获取任务对话框位置（任务添加/编辑对话框）
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)，可选
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        # 任务对话框使用屏幕中央策略
        return self.get_dialog_position(
            dialog_size, main_window_position, strategy="screen_center"
        )
    
    def get_settings_dialog_position(self, dialog_size: Tuple[int, int], 
                                   main_window_position: Tuple[int, int] = None) -> Tuple[int, int]:
        """获取设置对话框位置
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)，可选
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        # 设置对话框使用屏幕中央策略
        return self.get_dialog_position(
            dialog_size, main_window_position, strategy="screen_center"
        )
    
    def get_selector_dialog_position(self, dialog_size: Tuple[int, int], 
                                   main_window_position: Tuple[int, int] = None) -> Tuple[int, int]:
        """获取选择器对话框位置（窗口选择器等）
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)，可选
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        # 选择器对话框使用偏移策略，避免遮挡主窗口
        return self.get_dialog_position(
            dialog_size, main_window_position, strategy="main_window_offset"
        )
    
    def get_switcher_dialog_position(self, dialog_size: Tuple[int, int], 
                                   main_window_position: Tuple[int, int] = None) -> Tuple[int, int]:
        """获取任务切换器对话框位置
        
        Args:
            dialog_size: 对话框尺寸 (width, height)
            main_window_position: 主窗口位置 (x, y)，可选
            
        Returns:
            对话框左上角坐标 (x, y)
        """
        # 任务切换器使用屏幕中央策略，便于快速识别
        return self.get_dialog_position(
            dialog_size, main_window_position, strategy="screen_center"
        )
    
    def set_default_strategy(self, strategy: str):
        """设置默认位置策略
        
        Args:
            strategy: 位置策略 ("screen_center", "main_window_center", "main_window_offset")
        """
        valid_strategies = ["screen_center", "main_window_center", "main_window_offset"]
        
        if strategy in valid_strategies:
            self.default_strategy = strategy
            print(f"✓ 默认位置策略设置为: {strategy}")
        else:
            print(f"⚠️ 无效的位置策略: {strategy}，支持的策略: {valid_strategies}")
    
    def set_dialog_offset(self, offset: Tuple[int, int]):
        """设置对话框偏移量
        
        Args:
            offset: 偏移量 (x_offset, y_offset)
        """
        if isinstance(offset, tuple) and len(offset) == 2:
            self.dialog_offset = offset
            print(f"✓ 对话框偏移量设置为: {offset}")
        else:
            print(f"⚠️ 无效的偏移量格式: {offset}")
    
    def get_popup_position(self, popup_size: Tuple[int, int] = (300, 150), 
                         main_window_position: Tuple[int, int] = None) -> Tuple[int, int]:
        """获取弹出提示位置（用于替换sg.popup）
        
        Args:
            popup_size: 弹出框尺寸 (width, height)，默认为标准大小
            main_window_position: 主窗口位置 (x, y)，可选
            
        Returns:
            弹出框左上角坐标 (x, y)
        """
        # 弹出提示使用屏幕中央策略
        return self.get_dialog_position(
            popup_size, main_window_position, strategy="screen_center"
        )
    
    def clear_cache(self):
        """清除位置计算缓存"""
        if self.screen_helper:
            self.screen_helper.clear_cache()
            print("✓ 对话框位置管理器缓存已清除")


# 全局单例实例，便于在整个应用中使用
_dialog_position_manager = None

def get_dialog_position_manager() -> DialogPositionManager:
    """获取对话框位置管理器单例实例"""
    global _dialog_position_manager
    if _dialog_position_manager is None:
        _dialog_position_manager = DialogPositionManager()
    return _dialog_position_manager