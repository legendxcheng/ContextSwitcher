"""
FreeSimpleGUI 现代化界面配置文件
================================

包含推荐的主题、配色方案、窗口配置等最佳实践设置。
专为Windows桌面任务管理工具优化。
"""

import FreeSimpleGUI as sg
from typing import Dict, Any, Optional, Tuple

class ModernUIConfig:
    """现代化UI配置管理"""
    
    # Windows 11 风格配色方案
    WINDOWS_11_COLORS = {
        'primary': '#0078D4',           # 主色调 - Windows蓝
        'primary_dark': '#005A9E',      # 深色主色调
        'primary_light': '#40E0D0',     # 浅色主色调
        'background': '#202020',         # 主背景色
        'surface': '#2D2D2D',           # 表面色（卡片、面板）
        'surface_variant': '#404040',    # 表面变体色
        'text': '#FFFFFF',              # 主文字色
        'text_secondary': '#CCCCCC',    # 次要文字色
        'text_disabled': '#808080',     # 禁用文字色
        'success': '#107C10',           # 成功状态色
        'warning': '#FF8C00',           # 警告状态色
        'error': '#D13438',             # 错误状态色
        'info': '#0078D4',              # 信息状态色
        'border': '#404040',            # 边框色
        'shadow': '#000000',            # 阴影色
        'transparent': '#00000000'       # 透明
    }
    
    # macOS Big Sur 风格配色
    MACOS_COLORS = {
        'primary': '#007AFF',
        'primary_dark': '#0056CC',
        'primary_light': '#40A9FF',
        'background': '#1C1C1E',
        'surface': '#2C2C2E',
        'surface_variant': '#3A3A3C',
        'text': '#FFFFFF',
        'text_secondary': '#8E8E93',
        'text_disabled': '#636366',
        'success': '#30D158',
        'warning': '#FF9F0A',
        'error': '#FF453A',
        'info': '#64D2FF',
        'border': '#38383A',
        'shadow': '#000000',
        'transparent': '#00000000'
    }
    
    # Material Design 3 配色
    MATERIAL_COLORS = {
        'primary': '#1976D2',
        'primary_dark': '#1565C0',
        'primary_light': '#42A5F5',
        'background': '#121212',
        'surface': '#1F1F1F',
        'surface_variant': '#2E2E2E',
        'text': '#FFFFFF',
        'text_secondary': '#AAAAAA',
        'text_disabled': '#666666',
        'success': '#4CAF50',
        'warning': '#FF9800',
        'error': '#F44336',
        'info': '#2196F3',
        'border': '#333333',
        'shadow': '#000000',
        'transparent': '#00000000'
    }
    
    # 推荐的深色主题列表
    RECOMMENDED_DARK_THEMES = [
        'DarkGrey13',    # 最推荐 - 现代灰色
        'DarkBlue3',     # Windows风格蓝色
        'DarkTeal9',     # 清新青色
        'DarkPurple6',   # 优雅紫色
        'DarkGrey14',    # 深灰色
        'Black',         # 纯黑极简
        'DarkGrey11',    # 中性灰色
        'DarkTeal11'     # 深青色
    ]
    
    def __init__(self, color_scheme: str = 'windows11'):
        """
        初始化现代化UI配置
        
        Args:
            color_scheme: 配色方案 ('windows11', 'macos', 'material')
        """
        self.color_scheme = color_scheme
        self.colors = self._get_color_scheme(color_scheme)
        self._setup_fonts()
    
    def _get_color_scheme(self, scheme: str) -> Dict[str, str]:
        """获取配色方案"""
        schemes = {
            'windows11': self.WINDOWS_11_COLORS,
            'macos': self.MACOS_COLORS,
            'material': self.MATERIAL_COLORS
        }
        return schemes.get(scheme, self.WINDOWS_11_COLORS)
    
    def _setup_fonts(self):
        """设置字体配置"""
        self.fonts = {
            'title': ('Segoe UI', 16, 'bold'),      # 标题字体
            'heading': ('Segoe UI', 14, 'bold'),    # 小标题字体
            'body': ('Segoe UI', 10),               # 正文字体
            'caption': ('Segoe UI', 9),             # 说明文字字体
            'button': ('Segoe UI', 10),             # 按钮字体
            'code': ('Consolas', 9),                # 代码字体
            'small': ('Segoe UI', 8)                # 小字体
        }
    
    def create_custom_theme(self, theme_name: str = 'ModernDark') -> None:
        """创建自定义现代化主题"""
        theme_dict = {
            'BACKGROUND': self.colors['background'],
            'TEXT': self.colors['text'],
            'INPUT': self.colors['surface'],
            'TEXT_INPUT': self.colors['text'],
            'SCROLL': self.colors['surface_variant'],
            'BUTTON': (self.colors['text'], self.colors['primary']),
            'PROGRESS': (self.colors['primary'], self.colors['surface']),
            'BORDER': 1,
            'SLIDER_DEPTH': 0,
            'PROGRESS_DEPTH': 0,
        }
        
        sg.theme_add_new(theme_name, theme_dict)
        sg.theme(theme_name)
        print(f"✓ 创建并应用自定义主题: {theme_name}")
    
    def get_borderless_window_config(self, 
                                   size: Optional[Tuple[int, int]] = None,
                                   location: Optional[Tuple[int, int]] = None,
                                   transparency: float = 0.95,
                                   margins: Tuple[int, int] = (15, 15)) -> Dict[str, Any]:
        """
        获取无标题栏窗口配置
        
        Args:
            size: 窗口大小 (width, height)
            location: 窗口位置 (x, y)
            transparency: 透明度 (0.0-1.0)
            margins: 内边距 (horizontal, vertical)
            
        Returns:
            窗口配置字典
        """
        config = {
            'no_titlebar': True,        # 无标题栏
            'keep_on_top': True,        # 置顶显示
            'grab_anywhere': True,      # 可拖拽移动
            'resizable': False,         # 禁用调整大小
            'finalize': True,          # 自动完成
            'alpha_channel': transparency,  # 透明度
            'margins': margins,         # 内边距
            'element_padding': (5, 3),  # 元素间距
            'background_color': self.colors['background'],
            'use_default_focus': False  # 禁用默认焦点
        }
        
        if size:
            config['size'] = size
        if location:
            config['location'] = location
            
        return config
    
    def get_modern_widget_config(self) -> Dict[str, Any]:
        """获取现代化Widget配置"""
        return {
            'no_titlebar': True,
            'keep_on_top': True,
            'grab_anywhere': True,
            'resizable': False,
            'finalize': True,
            'alpha_channel': 0.92,
            'margins': (12, 8),
            'element_padding': (3, 2),
            'background_color': self.colors['background'],
            'use_default_focus': False,
            'disable_minimize': True,
            'disable_close': False
        }
    
    def get_task_manager_config(self) -> Dict[str, Any]:
        """获取任务管理器风格配置"""
        return {
            'resizable': True,
            'size': (800, 600),
            'finalize': True,
            'margins': (10, 10),
            'element_padding': (5, 3),
            'background_color': self.colors['background'],
            'keep_on_top': False,
            'grab_anywhere': False
        }
    
    def create_modern_button(self, 
                           text: str, 
                           key: str, 
                           button_type: str = 'primary',
                           size: Optional[Tuple[int, int]] = None) -> sg.Button:
        """
        创建现代化按钮
        
        Args:
            text: 按钮文字
            key: 按钮键值
            button_type: 按钮类型 ('primary', 'secondary', 'success', 'warning', 'error')
            size: 按钮大小
            
        Returns:
            配置好的按钮对象
        """
        button_colors = {
            'primary': (self.colors['text'], self.colors['primary']),
            'secondary': (self.colors['text'], self.colors['surface_variant']),
            'success': (self.colors['text'], self.colors['success']),
            'warning': (self.colors['text'], self.colors['warning']),
            'error': (self.colors['text'], self.colors['error']),
            'info': (self.colors['text'], self.colors['info'])
        }
        
        color = button_colors.get(button_type, button_colors['primary'])
        
        return sg.Button(
            text,
            key=key,
            button_color=color,
            font=self.fonts['button'],
            size=size,
            border_width=0,
            focus=False
        )
    
    def create_modern_table(self,
                          values: list,
                          headings: list,
                          key: str,
                          num_rows: int = 10) -> sg.Table:
        """创建现代化表格"""
        return sg.Table(
            values=values,
            headings=headings,
            key=key,
            enable_events=True,
            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            auto_size_columns=False,
            justification='left',
            alternating_row_color=self.colors['surface'],
            selected_row_colors=(self.colors['text'], self.colors['primary']),
            header_text_color=self.colors['text'],
            header_background_color=self.colors['surface_variant'],
            header_font=self.fonts['caption'] + ('bold',),
            font=self.fonts['caption'],
            num_rows=num_rows,
            expand_x=True,
            expand_y=True,
            row_height=25,
            background_color=self.colors['background'],
            text_color=self.colors['text'],
            border_width=1
        )
    
    def create_status_bar(self, 
                         left_text: str = '就绪',
                         right_text: str = '') -> list:
        """创建现代化状态栏"""
        return [
            sg.Text(left_text, key='-STATUS_LEFT-', 
                   font=self.fonts['small'], 
                   text_color=self.colors['text_secondary']),
            sg.Push(),
            sg.Text(right_text, key='-STATUS_RIGHT-', 
                   font=self.fonts['small'], 
                   text_color=self.colors['text_secondary'])
        ]
    
    def create_progress_bar(self, 
                          max_value: int = 100,
                          size: Tuple[int, int] = (30, 20),
                          key: str = '-PROGRESS-') -> sg.ProgressBar:
        """创建现代化进度条"""
        return sg.ProgressBar(
            max_value,
            orientation='h',
            size=size,
            key=key,
            bar_color=(self.colors['primary'], self.colors['surface']),
            border_width=0,
            relief=sg.RELIEF_FLAT
        )
    
    def apply_modern_theme(self, theme_name: str = 'DarkGrey13') -> None:
        """应用现代化主题"""
        if theme_name in self.RECOMMENDED_DARK_THEMES:
            sg.theme(theme_name)
            print(f"✓ 应用推荐主题: {theme_name}")
        else:
            print(f"⚠ 主题 '{theme_name}' 不在推荐列表中")
            sg.theme(theme_name)
    
    def get_window_shadow_effect(self) -> Dict[str, Any]:
        """获取窗口阴影效果配置（模拟）"""
        # FreeSimpleGUI 本身不支持真正的阴影，但可以通过多层窗口模拟
        return {
            'shadow_offset': (5, 5),
            'shadow_color': self.colors['shadow'],
            'shadow_alpha': 0.3,
            'blur_radius': 10  # 概念性的，实际实现需要特殊处理
        }
    
    def print_configuration_guide(self) -> None:
        """打印配置指南"""
        print("\n" + "="*60)
        print("现代化UI配置指南")
        print("="*60)
        
        print(f"\n当前配色方案: {self.color_scheme.upper()}")
        print("\n主要颜色:")
        for name, color in self.colors.items():
            print(f"  {name:15}: {color}")
        
        print("\n推荐主题:")
        for theme in self.RECOMMENDED_DARK_THEMES:
            print(f"  - {theme}")
        
        print("\n字体配置:")
        for name, font in self.fonts.items():
            print(f"  {name:10}: {font}")
        
        print("\n无标题栏窗口最佳实践:")
        print("  - 使用 no_titlebar=True")
        print("  - 启用 grab_anywhere=True 允许拖拽")
        print("  - 设置 keep_on_top=True 用于工具窗口")
        print("  - 透明度 0.92-0.95 效果最佳")
        print("  - 内边距 (12-15, 8-10) 提供良好视觉效果")
        
        print("\n现代化设计原则:")
        print("  - 使用深色主题提高专业感")
        print("  - 保持一致的颜色语义")
        print("  - 适当的留白和间距")
        print("  - 清晰的层次结构")
        print("  - 响应式的状态反馈")


# 使用示例
def demo_modern_config():
    """演示现代化配置的使用"""
    
    # 创建配置实例
    config = ModernUIConfig('windows11')
    
    # 应用推荐主题
    config.apply_modern_theme('DarkGrey13')
    
    # 创建自定义主题
    config.create_custom_theme('MyModernTheme')
    
    # 创建现代化窗口
    layout = [
        [sg.Text('现代化配置演示', font=config.fonts['heading'])],
        [sg.HSeparator()],
        [config.create_modern_button('主要操作', '-PRIMARY-', 'primary'),
         config.create_modern_button('次要操作', '-SECONDARY-', 'secondary')],
        [config.create_modern_button('成功', '-SUCCESS-', 'success'),
         config.create_modern_button('警告', '-WARNING-', 'warning'),
         config.create_modern_button('错误', '-ERROR-', 'error')],
        [config.create_progress_bar(100, (40, 15), '-DEMO_PROGRESS-')],
        [sg.HSeparator()],
        config.create_status_bar('配置演示运行中', 'v1.0.0')
    ]
    
    # 获取无标题栏窗口配置
    window_config = config.get_borderless_window_config(
        size=(400, 300),
        location=(200, 200),
        transparency=0.95
    )
    
    # 创建窗口
    window = sg.Window('现代化配置演示', layout, **window_config)
    
    # 事件循环
    while True:
        event, values = window.read(timeout=100)
        
        if event == sg.WIN_CLOSED:
            break
        elif event.startswith('-'):
            print(f"按钮点击: {event}")
    
    window.close()


if __name__ == "__main__":
    print("FreeSimpleGUI 现代化配置")
    print("="*40)
    
    # 创建配置实例
    config = ModernUIConfig('windows11')
    
    # 打印配置指南
    config.print_configuration_guide()
    
    # 运行演示
    print("\n启动配置演示...")
    demo_modern_config()