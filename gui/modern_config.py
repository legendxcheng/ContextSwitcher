"""
现代化UI配置模块
专为ContextSwitcher优化的现代化界面配置
"""

import FreeSimpleGUI as sg
from typing import Dict, Any, Tuple


class ModernUIConfig:
    """现代化UI配置"""
    
    # Windows 11 风格配色方案
    COLORS = {
        'primary': '#0078D4',           # 主色调 - Windows蓝
        'success': '#107C10',           # 成功状态色
        'warning': '#FF8C00',           # 警告状态色
        'error': '#D13438',             # 错误状态色
        'background': '#202020',        # 主背景色
        'surface': '#2D2D2D',           # 表面色
        'surface_variant': '#404040',   # 表面变体色
        'text': '#FFFFFF',              # 主文字色
        'text_secondary': '#CCCCCC',    # 次要文字色
        'text_disabled': '#808080',     # 禁用文字色
        'border': '#404040',            # 边框色
    }
    
    # 字体配置
    FONTS = {
        'title': ('Segoe UI', 12, 'bold'),
        'heading': ('Segoe UI', 10, 'bold'),
        'body': ('Segoe UI', 9),
        'caption': ('Segoe UI', 8),
        'button': ('Segoe UI', 9),
        'small': ('Segoe UI', 8)
    }
    
    @classmethod
    def setup_theme(cls):
        """设置现代化主题"""
        sg.theme('DarkGrey13')
    
    @classmethod
    def get_widget_window_config(cls, size: Tuple[int, int] = None, 
                                location: Tuple[int, int] = None) -> Dict[str, Any]:
        """获取Widget风格窗口配置"""
        config = {
            'title': '',
            'no_titlebar': True,
            'keep_on_top': True,
            'grab_anywhere': True,
            'finalize': True,
            'resizable': False,
            'alpha_channel': 0.95,
            'margins': (8, 6),
            'element_padding': (3, 2),
            'background_color': cls.COLORS['background'],
            'use_default_focus': False,
            'disable_minimize': True,
            'auto_size_text': False,
            'auto_size_buttons': False
        }
        
        if size:
            config['size'] = size
        if location:
            config['location'] = location
            
        return config
    
    @classmethod
    def get_dialog_window_config(cls, title: str, size: Tuple[int, int]) -> Dict[str, Any]:
        """获取对话框窗口配置"""
        return {
            'title': title,
            'modal': True,
            'keep_on_top': True,
            'finalize': True,
            'resizable': True,
            'size': size,
            'no_titlebar': False,
            'alpha_channel': 0.98,
            'background_color': cls.COLORS['background'],
            'margins': (12, 10),
            'element_padding': (4, 3)
        }
    
    @classmethod
    def create_modern_button(cls, text: str, key: str, 
                           button_type: str = 'primary', 
                           size: Tuple[int, int] = None,
                           tooltip: str = None) -> sg.Button:
        """创建现代化按钮"""
        colors = {
            'primary': (cls.COLORS['text'], cls.COLORS['primary']),
            'success': (cls.COLORS['text'], cls.COLORS['success']),
            'warning': (cls.COLORS['text'], cls.COLORS['warning']),
            'error': (cls.COLORS['text'], cls.COLORS['error']),
            'secondary': (cls.COLORS['text'], cls.COLORS['surface_variant'])
        }
        
        color = colors.get(button_type, colors['primary'])
        
        return sg.Button(
            text,
            key=key,
            button_color=color,
            font=cls.FONTS['button'],
            size=size,
            border_width=0,
            focus=False,
            tooltip=tooltip
        )
    
    @classmethod
    def create_modern_table(cls, values: list, headings: list, key: str,
                          num_rows: int = 4, col_widths: list = None) -> sg.Table:
        """创建现代化表格"""
        return sg.Table(
            values=values,
            headings=headings,
            key=key,
            enable_events=True,
            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            auto_size_columns=False,
            col_widths=col_widths or [3, 20, 15, 8],
            justification='left',
            alternating_row_color=cls.COLORS['surface'],
            selected_row_colors=(cls.COLORS['text'], cls.COLORS['primary']),
            header_text_color=cls.COLORS['text'],
            header_background_color=cls.COLORS['surface_variant'],
            header_font=cls.FONTS['caption'] + ('bold',),
            font=cls.FONTS['caption'],
            num_rows=num_rows,
            expand_x=True,
            expand_y=False,
            row_height=22,
            background_color=cls.COLORS['background'],
            text_color=cls.COLORS['text'],
            border_width=0
        )