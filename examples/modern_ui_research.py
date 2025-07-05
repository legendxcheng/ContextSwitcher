"""
FreeSimpleGUI 现代化界面研究
===========================

本文件展示FreeSimpleGUI的现代化界面功能，特别针对Windows桌面任务管理工具的界面设计。

功能研究：
1. 无标题栏窗口（Widget效果）
2. 现代化深色主题配置
3. 窗口边框、圆角、透明度等现代UI效果
4. 推荐的现代UI设计模式和配色方案
"""

import FreeSimpleGUI as sg
import time
import threading
from typing import Dict, List, Any, Optional

class ModernUIResearch:
    """现代化UI研究类"""
    
    def __init__(self):
        """初始化研究环境"""
        self.examples = {}
        self.current_window = None
        
        # 设置默认字体（Windows推荐）
        sg.set_options(font=('Segoe UI', 10))
        
    def show_menu(self):
        """显示功能菜单"""
        # 使用现代化主题
        sg.theme('DarkBlue3')
        
        layout = [
            [sg.Text('FreeSimpleGUI 现代化界面研究', 
                    font=('Segoe UI', 16, 'bold'), 
                    text_color='#FFFFFF',
                    justification='center')],
            [sg.HSeparator()],
            [sg.Text('选择要研究的功能：', font=('Segoe UI', 12))],
            [sg.Button('1. 无标题栏窗口示例', key='-BORDERLESS-', size=(25, 2))],
            [sg.Button('2. 深色主题配置', key='-DARK_THEMES-', size=(25, 2))],
            [sg.Button('3. 透明度和圆角效果', key='-TRANSPARENCY-', size=(25, 2))],
            [sg.Button('4. 现代化Widget设计', key='-MODERN_WIDGET-', size=(25, 2))],
            [sg.Button('5. 任务管理器样式', key='-TASK_MANAGER-', size=(25, 2))],
            [sg.Button('6. 所有主题预览', key='-ALL_THEMES-', size=(25, 2))],
            [sg.HSeparator()],
            [sg.Button('退出', key='-EXIT-', size=(10, 1))]
        ]
        
        window = sg.Window(
            'FreeSimpleGUI 现代化研究',
            layout,
            finalize=True,
            keep_on_top=True,
            resizable=False,
            grab_anywhere=True,
            margins=(20, 20),
            element_padding=(5, 5)
        )
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '-EXIT-'):
                break
            elif event == '-BORDERLESS-':
                self.show_borderless_examples()
            elif event == '-DARK_THEMES-':
                self.show_dark_themes()
            elif event == '-TRANSPARENCY-':
                self.show_transparency_examples()
            elif event == '-MODERN_WIDGET-':
                self.show_modern_widget()
            elif event == '-TASK_MANAGER-':
                self.show_task_manager_style()
            elif event == '-ALL_THEMES-':
                self.show_all_themes()
        
        window.close()
    
    def show_borderless_examples(self):
        """展示无标题栏窗口示例"""
        print("\n=== 无标题栏窗口示例 ===")
        
        # 示例1：基本无标题栏窗口
        self._demo_basic_borderless()
        
        # 示例2：带自定义标题栏的无标题栏窗口
        self._demo_custom_titlebar()
        
        # 示例3：悬浮Widget样式
        self._demo_floating_widget()
    
    def _demo_basic_borderless(self):
        """基本无标题栏窗口"""
        sg.theme('DarkGrey13')
        
        layout = [
            [sg.Text('无标题栏窗口示例', font=('Segoe UI', 14, 'bold'), 
                    text_color='#FFFFFF', background_color='#2B2B2B')],
            [sg.Text('这是一个没有标题栏的窗口', 
                    background_color='#2B2B2B', text_color='#CCCCCC')],
            [sg.Text('你可以拖拽任意位置移动窗口', 
                    background_color='#2B2B2B', text_color='#CCCCCC')],
            [sg.HSeparator()],
            [sg.Button('关闭', key='-CLOSE-', button_color=('#FFFFFF', '#E74C3C')),
             sg.Button('最小化', key='-MINIMIZE-', button_color=('#FFFFFF', '#3498DB'))]
        ]
        
        window = sg.Window(
            'Borderless Window',
            layout,
            no_titlebar=True,           # 关键参数：无标题栏
            keep_on_top=True,           # 置顶显示
            grab_anywhere=True,         # 可以在任意位置拖拽
            finalize=True,
            margins=(10, 10),
            background_color='#2B2B2B',
            alpha_channel=0.95,         # 轻微透明
            location=(100, 100)
        )
        
        print("无标题栏窗口参数说明：")
        print("- no_titlebar=True: 移除标题栏")
        print("- grab_anywhere=True: 允许拖拽移动")
        print("- alpha_channel=0.95: 设置透明度")
        print("- keep_on_top=True: 窗口置顶")
        
        while True:
            event, values = window.read(timeout=100)
            
            if event in (sg.WIN_CLOSED, '-CLOSE-'):
                break
            elif event == '-MINIMIZE-':
                window.minimize()
        
        window.close()
    
    def _demo_custom_titlebar(self):
        """带自定义标题栏的无标题栏窗口"""
        sg.theme('DarkBlue3')
        
        # 自定义标题栏
        titlebar = [
            [sg.Text('📋 ContextSwitcher', 
                    font=('Segoe UI', 11, 'bold'),
                    text_color='#FFFFFF',
                    background_color='#1E3A5F',
                    expand_x=True,
                    justification='left'),
             sg.Push(),
             sg.Button('─', key='-MINIMIZE-', 
                      size=(3, 1), button_color=('#FFFFFF', '#34495E')),
             sg.Button('✕', key='-CLOSE-', 
                      size=(3, 1), button_color=('#FFFFFF', '#E74C3C'))]
        ]
        
        # 主要内容区域
        content = [
            [sg.Text('自定义标题栏示例', font=('Segoe UI', 12, 'bold'))],
            [sg.Text('这展示了如何在无标题栏窗口中实现自定义标题栏')],
            [sg.HSeparator()],
            [sg.Text('任务列表:')],
            [sg.Listbox(['任务 1: 编写代码', '任务 2: 测试功能', '任务 3: 文档编写'], 
                       size=(40, 4), key='-TASKS-')],
            [sg.Button('添加任务', button_color=('#FFFFFF', '#27AE60')),
             sg.Button('删除任务', button_color=('#FFFFFF', '#E67E22'))]
        ]
        
        layout = titlebar + [[sg.Column(content, background_color=sg.theme_background_color())]]
        
        window = sg.Window(
            'Custom Titlebar',
            layout,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            finalize=True,
            margins=(0, 0),
            background_color='#1E3A5F',
            location=(200, 200)
        )
        
        print("\n自定义标题栏实现要点：")
        print("- 使用列布局分离标题栏和内容区")
        print("- 标题栏包含应用名称和控制按钮")
        print("- 背景色统一以创建整体感")
        print("- 最小化和关闭按钮功能完整")
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '-CLOSE-'):
                break
            elif event == '-MINIMIZE-':
                window.minimize()
        
        window.close()
    
    def _demo_floating_widget(self):
        """悬浮Widget样式"""
        sg.theme('DarkGrey14')
        
        layout = [
            [sg.Text('⚡', font=('Segoe UI', 20), text_color='#F39C12'),
             sg.Text('Quick Switch', font=('Segoe UI', 12, 'bold'), 
                    text_color='#FFFFFF')],
            [sg.HSeparator()],
            [sg.Text('Ctrl+1', font=('Segoe UI', 9), text_color='#BDC3C7'),
             sg.Text('→ Browser', font=('Segoe UI', 9), text_color='#ECF0F1')],
            [sg.Text('Ctrl+2', font=('Segoe UI', 9), text_color='#BDC3C7'),
             sg.Text('→ Editor', font=('Segoe UI', 9), text_color='#ECF0F1')],
            [sg.Text('Ctrl+3', font=('Segoe UI', 9), text_color='#BDC3C7'),
             sg.Text('→ Terminal', font=('Segoe UI', 9), text_color='#ECF0F1')],
        ]
        
        window = sg.Window(
            'Widget',
            layout,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            finalize=True,
            margins=(15, 15),
            alpha_channel=0.9,
            background_color='#2C3E50',
            location=(300, 300),
            auto_size_text=True,
            auto_size_buttons=False,
            element_padding=(3, 2)
        )
        
        print("\n悬浮Widget设计特点：")
        print("- 紧凑的尺寸和布局")
        print("- 高透明度(alpha_channel=0.9)")
        print("- 深色背景配合亮色文字")
        print("- 图标和快捷键的清晰展示")
        print("- 最小的边距和内边距")
        
        # 自动关闭演示
        start_time = time.time()
        while True:
            event, values = window.read(timeout=100)
            
            if event == sg.WIN_CLOSED:
                break
            
            # 5秒后自动关闭
            if time.time() - start_time > 5:
                break
        
        window.close()
    
    def show_dark_themes(self):
        """展示深色主题配置"""
        print("\n=== 深色主题配置 ===")
        
        # 获取所有可用的深色主题
        dark_themes = [
            'DarkBlue', 'DarkBlue3', 'DarkBrown', 'DarkGreen', 'DarkGrey',
            'DarkGrey1', 'DarkGrey2', 'DarkGrey3', 'DarkGrey4', 'DarkGrey5',
            'DarkGrey6', 'DarkGrey7', 'DarkGrey8', 'DarkGrey9', 'DarkGrey10',
            'DarkGrey11', 'DarkGrey12', 'DarkGrey13', 'DarkGrey14', 'DarkPurple',
            'DarkPurple1', 'DarkPurple2', 'DarkPurple3', 'DarkPurple4', 'DarkPurple5',
            'DarkPurple6', 'DarkRed', 'DarkRed1', 'DarkTeal', 'DarkTeal1',
            'DarkTeal2', 'DarkTeal3', 'DarkTeal4', 'DarkTeal5', 'DarkTeal6',
            'DarkTeal7', 'DarkTeal8', 'DarkTeal9', 'DarkTeal10', 'DarkTeal11',
            'DarkTeal12', 'Black'
        ]
        
        print(f"找到 {len(dark_themes)} 个深色主题:")
        for theme in dark_themes:
            print(f"  - {theme}")
        
        # 推荐的现代化深色主题
        recommended_themes = {
            'DarkGrey13': '现代化灰色，适合专业应用',
            'DarkBlue3': '深蓝色，Windows 11风格',
            'DarkTeal9': '深青色，清新现代',
            'DarkPurple6': '深紫色，独特设计',
            'Black': '纯黑色，极简风格'
        }
        
        sg.theme('DarkGrey13')
        
        layout = [
            [sg.Text('推荐的现代化深色主题', font=('Segoe UI', 14, 'bold'))],
            [sg.HSeparator()],
        ]
        
        # 添加推荐主题按钮
        for theme, description in recommended_themes.items():
            layout.append([
                sg.Button(theme, key=f'-THEME-{theme}-', size=(15, 1),
                         button_color=('#FFFFFF', '#34495E')),
                sg.Text(description, font=('Segoe UI', 10))
            ])
        
        layout.extend([
            [sg.HSeparator()],
            [sg.Text('当前主题配色信息:', font=('Segoe UI', 11, 'bold'))],
            [sg.Multiline('', key='-THEME_INFO-', size=(60, 10), 
                         font=('Consolas', 9), disabled=True)],
            [sg.Button('关闭', key='-CLOSE-')]
        ])
        
        window = sg.Window(
            '深色主题配置',
            layout,
            finalize=True,
            keep_on_top=True,
            resizable=False,
            grab_anywhere=True
        )
        
        # 显示当前主题信息
        self._update_theme_info(window)
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '-CLOSE-'):
                break
            elif event.startswith('-THEME-'):
                theme_name = event.replace('-THEME-', '').replace('-', '')
                sg.theme(theme_name)
                self._update_theme_info(window)
                sg.popup(f'已切换到主题: {theme_name}', 
                        title='主题切换', keep_on_top=True)
        
        window.close()
    
    def _update_theme_info(self, window):
        """更新主题信息显示"""
        theme_dict = sg.theme_global()
        theme_info = f"当前主题: {sg.theme()}\n\n"
        theme_info += "主题配色:\n"
        
        for key, value in theme_dict.items():
            theme_info += f"  {key}: {value}\n"
        
        theme_info += "\n自定义配色示例:\n"
        theme_info += """
# 设置自定义主题
sg.theme_add_new('CustomDark', {
    'BACKGROUND': '#2B2B2B',
    'TEXT': '#FFFFFF', 
    'INPUT': '#404040',
    'TEXT_INPUT': '#FFFFFF',
    'SCROLL': '#404040',
    'BUTTON': ('#FFFFFF', '#0078D4'),
    'PROGRESS': ('#FFFFFF', '#0078D4'),
    'BORDER': 1,
    'SLIDER_DEPTH': 0,
    'PROGRESS_DEPTH': 0
})

# 使用自定义主题
sg.theme('CustomDark')
"""
        
        window['-THEME_INFO-'].update(theme_info)
    
    def show_transparency_examples(self):
        """展示透明度和圆角效果"""
        print("\n=== 透明度和圆角效果 ===")
        
        # 注意：FreeSimpleGUI的圆角支持有限，主要通过透明度实现现代效果
        
        # 透明度示例
        self._demo_transparency_levels()
        
        # 毛玻璃效果模拟
        self._demo_glass_effect()
    
    def _demo_transparency_levels(self):
        """透明度级别演示"""
        transparency_levels = [1.0, 0.95, 0.9, 0.8, 0.7]
        
        for i, alpha in enumerate(transparency_levels):
            sg.theme('DarkBlue3')
            
            layout = [
                [sg.Text(f'透明度: {int(alpha * 100)}%', 
                        font=('Segoe UI', 14, 'bold'), 
                        text_color='#FFFFFF')],
                [sg.Text(f'Alpha值: {alpha}', 
                        font=('Segoe UI', 11), 
                        text_color='#BDC3C7')],
                [sg.Text('这展示了不同透明度级别的视觉效果')],
                [sg.HSeparator()],
                [sg.Button('下一个', key='-NEXT-'),
                 sg.Button('关闭', key='-CLOSE-')]
            ]
            
            window = sg.Window(
                f'透明度 {int(alpha * 100)}%',
                layout,
                alpha_channel=alpha,
                no_titlebar=True,
                keep_on_top=True,
                grab_anywhere=True,
                finalize=True,
                margins=(20, 20),
                location=(100 + i * 50, 100 + i * 50)
            )
            
            print(f"透明度级别 {alpha}: alpha_channel={alpha}")
            
            while True:
                event, values = window.read()
                
                if event in (sg.WIN_CLOSED, '-CLOSE-', '-NEXT-'):
                    break
            
            window.close()
            
            if event == '-CLOSE-':
                break
    
    def _demo_glass_effect(self):
        """毛玻璃效果模拟"""
        sg.theme('DarkGrey13')
        
        # 背景窗口
        bg_layout = [
            [sg.Text('背景内容区域', font=('Segoe UI', 16, 'bold'), 
                    text_color='#FFFFFF', justification='center')],
            [sg.Text('这是背景窗口，用于展示毛玻璃效果', 
                    font=('Segoe UI', 12), text_color='#CCCCCC')],
            [sg.Image(data=self._create_pattern_image(), key='-PATTERN-')]
        ]
        
        bg_window = sg.Window(
            '背景窗口',
            bg_layout,
            finalize=True,
            size=(400, 300),
            location=(200, 200),
            background_color='#34495E'
        )
        
        # 毛玻璃前景窗口
        fg_layout = [
            [sg.Text('毛玻璃效果', font=('Segoe UI', 14, 'bold'), 
                    text_color='#FFFFFF', background_color='#2C3E50')],
            [sg.Text('半透明覆盖层', font=('Segoe UI', 11), 
                    text_color='#BDC3C7', background_color='#2C3E50')],
            [sg.HSeparator()],
            [sg.Button('确定', button_color=('#FFFFFF', '#3498DB')),
             sg.Button('取消', button_color=('#FFFFFF', '#95A5A6'))]
        ]
        
        fg_window = sg.Window(
            '毛玻璃',
            fg_layout,
            alpha_channel=0.85,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            finalize=True,
            margins=(20, 20),
            background_color='#2C3E50',
            location=(280, 280)
        )
        
        print("毛玻璃效果实现要点：")
        print("- 使用多层窗口叠加")
        print("- 前景窗口设置适当透明度(0.85)")
        print("- 颜色搭配营造深度感")
        print("- 保持前景窗口在最顶层")
        
        while True:
            bg_event, bg_values = bg_window.read(timeout=100)
            fg_event, fg_values = fg_window.read(timeout=100)
            
            if bg_event == sg.WIN_CLOSED or fg_event in (sg.WIN_CLOSED, '确定', '取消'):
                break
        
        bg_window.close()
        fg_window.close()
    
    def _create_pattern_image(self):
        """创建简单的图案数据（用于演示）"""
        # 这里返回一个简单的图像数据，实际项目中可以使用真实图片
        return b''  # 简化实现
    
    def show_modern_widget(self):
        """展示现代化Widget设计"""
        print("\n=== 现代化Widget设计 ===")
        
        # 现代化的紧凑Widget
        self._demo_compact_widget()
        
        # 卡片式布局
        self._demo_card_layout()
    
    def _demo_compact_widget(self):
        """紧凑型现代Widget"""
        sg.theme('DarkGrey13')
        
        # 定义现代化颜色方案
        colors = {
            'primary': '#0078D4',      # Windows 11蓝
            'success': '#107C10',      # 成功绿
            'warning': '#FF8C00',      # 警告橙
            'danger': '#D13438',       # 危险红
            'background': '#202020',    # 深色背景
            'surface': '#2D2D2D',      # 表面色
            'text': '#FFFFFF',         # 主文字
            'text_secondary': '#CCCCCC' # 次要文字
        }
        
        layout = [
            # 标题栏
            [sg.Text('📋', font=('Segoe UI', 16), text_color=colors['primary']),
             sg.Text('ContextSwitcher', font=('Segoe UI', 12, 'bold'), 
                    text_color=colors['text']),
             sg.Push(),
             sg.Text('●●●', font=('Segoe UI', 8), text_color=colors['text_secondary'])],
            
            # 状态指示器
            [sg.Text('活跃任务', font=('Segoe UI', 9), text_color=colors['text_secondary']),
             sg.Push(),
             sg.Text('3/5', font=('Segoe UI', 9, 'bold'), text_color=colors['success'])],
            
            [sg.ProgressBar(60, orientation='h', size=(30, 8), 
                           bar_color=(colors['primary'], colors['surface']), 
                           key='-PROGRESS-')],
            
            # 快速操作按钮
            [sg.Button('1', key='-TASK1-', size=(3, 1), 
                      button_color=(colors['text'], colors['primary']),
                      font=('Segoe UI', 10, 'bold')),
             sg.Button('2', key='-TASK2-', size=(3, 1), 
                      button_color=(colors['text'], colors['surface']),
                      font=('Segoe UI', 10)),
             sg.Button('3', key='-TASK3-', size=(3, 1), 
                      button_color=(colors['text'], colors['success']),
                      font=('Segoe UI', 10, 'bold')),
             sg.Button('+', key='-ADD-', size=(3, 1), 
                      button_color=(colors['text'], colors['warning']),
                      font=('Segoe UI', 10, 'bold'))],
            
            # 底部状态
            [sg.Text('Ctrl+Alt+1-9 快速切换', 
                    font=('Segoe UI', 8), text_color=colors['text_secondary'])]
        ]
        
        window = sg.Window(
            'Modern Widget',
            layout,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            finalize=True,
            margins=(12, 8),
            element_padding=(3, 2),
            background_color=colors['background'],
            alpha_channel=0.95,
            location=(100, 100)
        )
        
        print("现代化Widget设计原则：")
        print("- 使用Windows 11配色方案")
        print("- 紧凑的布局和适当的间距")
        print("- 状态指示器和进度条")
        print("- 颜色编码的功能区分")
        print("- 简洁的图标和文字")
        
        # 模拟进度更新
        progress = 60
        direction = 1
        
        while True:
            event, values = window.read(timeout=50)
            
            if event == sg.WIN_CLOSED:
                break
            elif event in ['-TASK1-', '-TASK2-', '-TASK3-']:
                task_num = event[-2]
                sg.popup_quick_message(f'切换到任务 {task_num}', 
                                     auto_close_duration=1, 
                                     background_color=colors['surface'],
                                     text_color=colors['text'])
            elif event == '-ADD-':
                sg.popup_quick_message('添加新任务', 
                                     auto_close_duration=1,
                                     background_color=colors['warning'],
                                     text_color=colors['text'])
            
            # 更新进度条动画
            progress += direction * 2
            if progress >= 100:
                direction = -1
            elif progress <= 0:
                direction = 1
            
            window['-PROGRESS-'].update(progress)
        
        window.close()
    
    def _demo_card_layout(self):
        """卡片式布局演示"""
        sg.theme('DarkGrey13')
        
        # 定义卡片颜色
        card_colors = {
            'background': '#2D2D2D',
            'border': '#404040',
            'text': '#FFFFFF',
            'secondary': '#CCCCCC',
            'accent': '#0078D4'
        }
        
        # 创建任务卡片
        def create_task_card(title, status, time_info):
            return [
                [sg.Frame('', [
                    [sg.Text(title, font=('Segoe UI', 11, 'bold'), 
                            text_color=card_colors['text'])],
                    [sg.Text(status, font=('Segoe UI', 9), 
                            text_color=card_colors['secondary'])],
                    [sg.Push(), sg.Text(time_info, font=('Segoe UI', 8), 
                                       text_color=card_colors['accent'])]
                ], border_width=1, relief=sg.RELIEF_SOLID,
                background_color=card_colors['background'],
                element_justification='left')]
            ]
        
        layout = [
            [sg.Text('任务卡片视图', font=('Segoe UI', 14, 'bold'))],
            [sg.HSeparator()],
        ]
        
        # 添加任务卡片
        tasks = [
            ('Web开发项目', '3个窗口活跃', '2小时前'),
            ('文档编写', '1个窗口活跃', '30分钟前'),
            ('代码审查', '2个窗口活跃', '刚刚')
        ]
        
        for task in tasks:
            layout.extend(create_task_card(*task))
        
        layout.extend([
            [sg.HSeparator()],
            [sg.Button('添加任务', button_color=('#FFFFFF', '#28A745')),
             sg.Push(),
             sg.Button('关闭', button_color=('#FFFFFF', '#6C757D'))]
        ])
        
        window = sg.Window(
            '卡片式布局',
            layout,
            finalize=True,
            keep_on_top=True,
            margins=(15, 15),
            element_padding=(5, 5),
            background_color='#1E1E1E'
        )
        
        print("卡片式布局特点：")
        print("- 使用Frame创建卡片边框")
        print("- 统一的卡片内间距")
        print("- 层次化的文字样式")
        print("- 清晰的信息组织")
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '关闭'):
                break
        
        window.close()
    
    def show_task_manager_style(self):
        """展示任务管理器风格界面"""
        print("\n=== 任务管理器风格界面 ===")
        
        sg.theme('DarkGrey13')
        
        # 现代化任务管理器界面
        colors = {
            'header_bg': '#1F1F1F',
            'row_even': '#2D2D2D', 
            'row_odd': '#262626',
            'selected': '#0078D4',
            'text': '#FFFFFF',
            'text_dim': '#CCCCCC',
            'accent': '#00BCF2'
        }
        
        # 顶部工具栏
        toolbar = [
            [sg.Text('⚡ ContextSwitcher Pro', 
                    font=('Segoe UI', 12, 'bold'), 
                    text_color=colors['accent']),
             sg.Push(),
             sg.Text('CPU: 15%', font=('Segoe UI', 9), text_color=colors['text_dim']),
             sg.Text('内存: 8.2GB', font=('Segoe UI', 9), text_color=colors['text_dim'])]
        ]
        
        # 任务列表表头
        headers = ['任务名称', '状态', '窗口数', 'CPU%', '内存', '最后活跃']
        
        # 模拟任务数据
        task_data = [
            ['Web Browser', '运行中', '5', '12.5', '512MB', '刚刚'],
            ['Code Editor', '运行中', '3', '8.2', '256MB', '2分钟前'],
            ['Terminal', '空闲', '2', '0.1', '32MB', '5分钟前'],
            ['Design Tool', '运行中', '4', '15.8', '1.2GB', '1分钟前'],
            ['Documentation', '空闲', '1', '0.0', '64MB', '10分钟前']
        ]
        
        # 主表格
        table_section = [
            [sg.Table(
                values=task_data,
                headings=headers,
                key='-TASK_TABLE-',
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[20, 8, 6, 6, 8, 12],
                justification='left',
                alternating_row_color=colors['row_odd'],
                selected_row_colors=(colors['text'], colors['selected']),
                header_text_color=colors['text'],
                header_background_color=colors['header_bg'],
                header_font=('Segoe UI', 10, 'bold'),
                font=('Segoe UI', 9),
                num_rows=10,
                expand_x=True,
                expand_y=True,
                row_height=25,
                background_color=colors['row_even'],
                text_color=colors['text']
            )]
        ]
        
        # 底部操作栏
        bottom_toolbar = [
            [sg.Button('新建任务', key='-NEW-', 
                      button_color=(colors['text'], '#28A745')),
             sg.Button('切换到', key='-SWITCH-', 
                      button_color=(colors['text'], colors['selected'])),
             sg.Button('结束任务', key='-END-', 
                      button_color=(colors['text'], '#DC3545')),
             sg.Push(),
             sg.Text('选中行: 无', key='-SELECTION-', 
                    font=('Segoe UI', 9), text_color=colors['text_dim']),
             sg.Push(),
             sg.Button('刷新', key='-REFRESH-'),
             sg.Button('设置', key='-SETTINGS-')]
        ]
        
        # 状态栏
        status_bar = [
            [sg.Text('就绪', key='-STATUS-', 
                    font=('Segoe UI', 9), text_color=colors['text_dim']),
             sg.Push(),
             sg.Text('总任务: 5', font=('Segoe UI', 9), text_color=colors['text_dim']),
             sg.Text('|', text_color=colors['text_dim']),
             sg.Text('活跃: 3', font=('Segoe UI', 9), text_color=colors['accent'])]
        ]
        
        layout = [
            *toolbar,
            [sg.HSeparator()],
            *table_section,
            [sg.HSeparator()],
            *bottom_toolbar,
            [sg.HSeparator()],
            *status_bar
        ]
        
        window = sg.Window(
            'ContextSwitcher Pro - 任务管理器风格',
            layout,
            finalize=True,
            resizable=True,
            size=(800, 500),
            margins=(10, 10),
            element_padding=(5, 3),
            background_color='#1E1E1E'
        )
        
        print("任务管理器风格特点：")
        print("- 完整的工具栏和状态栏")
        print("- 专业的表格样式")
        print("- 系统资源信息显示")
        print("- 多列数据展示")
        print("- 状态颜色编码")
        
        while True:
            event, values = window.read()
            
            if event == sg.WIN_CLOSED:
                break
            elif event == '-TASK_TABLE-':
                if values['-TASK_TABLE-']:
                    row_index = values['-TASK_TABLE-'][0]
                    task_name = task_data[row_index][0]
                    window['-SELECTION-'].update(f'选中行: {task_name}')
                    window['-STATUS-'].update(f'已选择任务: {task_name}')
            elif event == '-NEW-':
                sg.popup('新建任务功能', '这里可以创建新的任务配置')
            elif event == '-SWITCH-':
                if values['-TASK_TABLE-']:
                    row_index = values['-TASK_TABLE-'][0]
                    task_name = task_data[row_index][0]
                    sg.popup_quick_message(f'切换到: {task_name}', auto_close_duration=1)
            elif event == '-REFRESH-':
                window['-STATUS-'].update('刷新完成')
        
        window.close()
    
    def show_all_themes(self):
        """显示所有主题预览"""
        print("\n=== 所有主题预览 ===")
        
        # 获取所有主题
        all_themes = sg.theme_list()
        
        # 过滤推荐的现代主题
        modern_themes = [theme for theme in all_themes 
                        if any(keyword in theme.lower() 
                              for keyword in ['dark', 'blue', 'grey', 'teal', 'purple', 'black'])]
        
        sg.theme('DarkGrey13')
        
        layout = [
            [sg.Text('现代主题预览', font=('Segoe UI', 14, 'bold'))],
            [sg.Text(f'找到 {len(modern_themes)} 个现代主题')],
            [sg.HSeparator()],
            [sg.Listbox(modern_themes, size=(30, 15), key='-THEME_LIST-', 
                       enable_events=True)],
            [sg.Button('预览选中主题', key='-PREVIEW-'),
             sg.Button('应用主题', key='-APPLY-'),
             sg.Button('关闭', key='-CLOSE-')]
        ]
        
        window = sg.Window(
            '主题预览器',
            layout,
            finalize=True,
            keep_on_top=True
        )
        
        preview_window = None
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '-CLOSE-'):
                break
            elif event == '-PREVIEW-' or event == '-THEME_LIST-':
                if values['-THEME_LIST-']:
                    selected_theme = values['-THEME_LIST-'][0]
                    
                    # 关闭之前的预览窗口
                    if preview_window:
                        preview_window.close()
                    
                    # 创建新的预览窗口
                    preview_window = self._create_theme_preview(selected_theme)
            elif event == '-APPLY-':
                if values['-THEME_LIST-']:
                    selected_theme = values['-THEME_LIST-'][0]
                    sg.theme(selected_theme)
                    sg.popup(f'已应用主题: {selected_theme}', title='主题应用')
        
        if preview_window:
            preview_window.close()
        window.close()
    
    def _create_theme_preview(self, theme_name):
        """创建主题预览窗口"""
        # 临时切换主题
        original_theme = sg.theme()
        sg.theme(theme_name)
        
        layout = [
            [sg.Text(f'主题预览: {theme_name}', font=('Segoe UI', 12, 'bold'))],
            [sg.HSeparator()],
            [sg.Text('这是普通文本')],
            [sg.InputText('这是输入框', key='-INPUT-')],
            [sg.Combo(['选项1', '选项2', '选项3'], default_value='选项1', key='-COMBO-')],
            [sg.Checkbox('复选框', default=True)],
            [sg.Radio('单选按钮1', 'radio1', default=True),
             sg.Radio('单选按钮2', 'radio1')],
            [sg.ProgressBar(75, orientation='h', size=(20, 20))],
            [sg.Button('普通按钮'), sg.Button('确定', button_color=('white', 'green')),
             sg.Button('取消', button_color=('white', 'red'))],
            [sg.Multiline('多行文本框\n展示主题效果', size=(30, 3), key='-MULTILINE-')],
            [sg.HSeparator()],
            [sg.Text('主题配色信息:')],
            [sg.Text(f'背景色: {sg.theme_background_color()}', font=('Consolas', 9))],
            [sg.Text(f'文字色: {sg.theme_text_color()}', font=('Consolas', 9))],
            [sg.Text(f'输入框: {sg.theme_input_background_color()}', font=('Consolas', 9))]
        ]
        
        preview_window = sg.Window(
            f'预览: {theme_name}',
            layout,
            finalize=True,
            location=(600, 100),
            keep_on_top=True,
            alpha_channel=0.9
        )
        
        # 恢复原主题
        sg.theme(original_theme)
        
        return preview_window


# 配色方案推荐
def print_color_recommendations():
    """打印现代化配色方案推荐"""
    print("\n" + "="*60)
    print("现代化配色方案推荐")
    print("="*60)
    
    color_schemes = {
        "Windows 11 Style": {
            "primary": "#0078D4",
            "background": "#202020", 
            "surface": "#2D2D2D",
            "text": "#FFFFFF",
            "text_secondary": "#CCCCCC",
            "success": "#107C10",
            "warning": "#FF8C00",
            "error": "#D13438"
        },
        "macOS Dark": {
            "primary": "#007AFF",
            "background": "#1C1C1E",
            "surface": "#2C2C2E", 
            "text": "#FFFFFF",
            "text_secondary": "#8E8E93",
            "success": "#30D158",
            "warning": "#FF9F0A",
            "error": "#FF453A"
        },
        "Material Design": {
            "primary": "#1976D2",
            "background": "#121212",
            "surface": "#1F1F1F",
            "text": "#FFFFFF", 
            "text_secondary": "#AAAAAA",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }
    }
    
    for scheme_name, colors in color_schemes.items():
        print(f"\n{scheme_name}:")
        for color_name, color_value in colors.items():
            print(f"  {color_name:15}: {color_value}")
    
    print("\n使用建议:")
    print("- 主色调用于按钮、链接等交互元素")
    print("- 背景色用于窗口背景")
    print("- 表面色用于卡片、面板等")
    print("- 文字色保证足够的对比度")
    print("- 状态色用于成功、警告、错误状态")


# 无标题栏窗口配置参数说明
def print_borderless_window_guide():
    """打印无标题栏窗口配置指南"""
    print("\n" + "="*60)
    print("无标题栏窗口配置指南")
    print("="*60)
    
    print("""
关键参数说明:

1. no_titlebar=True
   - 移除窗口标题栏
   - 创建现代化Widget效果

2. grab_anywhere=True  
   - 允许在窗口任意位置拖拽移动
   - 补偿失去标题栏的移动功能

3. keep_on_top=True
   - 窗口始终在最前面
   - 适合任务切换工具

4. alpha_channel=0.9
   - 设置窗口透明度 (0.0-1.0)
   - 0.9-0.95 是推荐的透明度

5. resizable=False
   - 禁用窗口大小调整
   - 保持Widget固定尺寸

6. margins=(10, 10)
   - 设置窗口内边距
   - 影响整体视觉效果

完整示例:
window = sg.Window(
    'Widget Title',
    layout,
    no_titlebar=True,       # 无标题栏
    keep_on_top=True,       # 置顶
    grab_anywhere=True,     # 可拖拽
    alpha_channel=0.95,     # 透明度
    resizable=False,        # 固定大小
    margins=(15, 15),       # 内边距
    finalize=True
)
""")


if __name__ == "__main__":
    print("FreeSimpleGUI 现代化界面研究")
    print("="*50)
    
    # 打印配色推荐
    print_color_recommendations()
    
    # 打印配置指南
    print_borderless_window_guide()
    
    # 启动交互式研究
    research = ModernUIResearch()
    research.show_menu()