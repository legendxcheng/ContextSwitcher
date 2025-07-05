"""
任务管理器UI现代化升级示例
===========================

展示如何将现代化UI配置应用到ContextSwitcher任务管理工具中。
包含多种UI风格的实现示例。
"""

import FreeSimpleGUI as sg
import time
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

class ModernTaskManagerUI:
    """现代化任务管理器UI"""
    
    def __init__(self):
        """初始化现代化UI"""
        self.setup_colors()
        self.setup_fonts()
        self.setup_themes()
        
        # 模拟任务数据
        self.tasks = [
            {
                'id': 1,
                'name': 'Web开发环境',
                'windows': ['Chrome', 'VS Code', 'Terminal'],
                'status': 'active',
                'last_accessed': datetime.now(),
                'cpu_usage': 15.2,
                'memory_usage': '512MB'
            },
            {
                'id': 2,
                'name': '文档编写',
                'windows': ['Word', 'Browser'],
                'status': 'idle',
                'last_accessed': datetime.now(),
                'cpu_usage': 2.1,
                'memory_usage': '128MB'
            },
            {
                'id': 3,
                'name': '设计工作',
                'windows': ['Figma', 'Photoshop'],
                'status': 'active',
                'last_accessed': datetime.now(),
                'cpu_usage': 25.8,
                'memory_usage': '1.2GB'
            }
        ]
        
        self.current_task = 0
        self.current_window = None
    
    def setup_colors(self):
        """设置现代化配色方案"""
        self.colors = {
            # Windows 11 配色
            'primary': '#0078D4',
            'primary_hover': '#106EBE',
            'secondary': '#6C757D',
            'success': '#198754',
            'warning': '#FFC107',
            'danger': '#DC3545',
            'info': '#0DCAF0',
            
            # 背景和表面
            'background': '#202020',
            'surface': '#2D2D2D',
            'surface_variant': '#404040',
            'elevated': '#383838',
            
            # 文字
            'text_primary': '#FFFFFF',
            'text_secondary': '#CCCCCC',
            'text_disabled': '#808080',
            'text_accent': '#40E0D0',
            
            # 边框和分割线
            'border': '#404040',
            'divider': '#333333',
            
            # 状态色
            'status_active': '#00FF7F',
            'status_idle': '#FFD700',
            'status_inactive': '#808080',
            
            # 特殊效果
            'shadow': '#000000',
            'highlight': '#FFFFFF20',
            'glow': '#0078D440'
        }
    
    def setup_fonts(self):
        """设置字体配置"""
        self.fonts = {
            'title': ('Segoe UI', 16, 'bold'),
            'heading': ('Segoe UI', 14, 'bold'),
            'subheading': ('Segoe UI', 12, 'bold'),
            'body': ('Segoe UI', 10),
            'caption': ('Segoe UI', 9),
            'small': ('Segoe UI', 8),
            'code': ('Consolas', 9),
            'icon': ('Segoe UI Symbol', 12)
        }
    
    def setup_themes(self):
        """设置自定义主题"""
        # 创建自定义现代主题
        modern_theme = {
            'BACKGROUND': self.colors['background'],
            'TEXT': self.colors['text_primary'],
            'INPUT': self.colors['surface'],
            'TEXT_INPUT': self.colors['text_primary'],
            'SCROLL': self.colors['surface_variant'],
            'BUTTON': (self.colors['text_primary'], self.colors['primary']),
            'PROGRESS': (self.colors['primary'], self.colors['surface']),
            'BORDER': 1,
            'SLIDER_DEPTH': 0,
            'PROGRESS_DEPTH': 0,
        }
        
        sg.theme_add_new('ModernTaskManager', modern_theme)
        sg.theme('ModernTaskManager')
    
    def show_style_selector(self):
        """显示界面风格选择器"""
        sg.theme('DarkGrey13')
        
        layout = [
            [sg.Text('ContextSwitcher 现代化界面', 
                    font=self.fonts['title'], 
                    text_color=self.colors['primary'])],
            [sg.Text('选择您喜欢的界面风格：', font=self.fonts['body'])],
            [sg.HSeparator()],
            
            # 风格选项
            [sg.Button('🎯 紧凑Widget风格', key='-COMPACT-', 
                      size=(25, 2), font=self.fonts['body'])],
            [sg.Text('适合任务快速切换，小巧精致', 
                    font=self.fonts['caption'], text_color=self.colors['text_secondary'])],
            
            [sg.Button('📋 任务管理器风格', key='-MANAGER-', 
                      size=(25, 2), font=self.fonts['body'])],
            [sg.Text('完整功能面板，详细信息显示', 
                    font=self.fonts['caption'], text_color=self.colors['text_secondary'])],
            
            [sg.Button('🎨 卡片式风格', key='-CARDS-', 
                      size=(25, 2), font=self.fonts['body'])],
            [sg.Text('现代卡片布局，视觉层次清晰', 
                    font=self.fonts['caption'], text_color=self.colors['text_secondary'])],
            
            [sg.Button('⚡ 悬浮助手风格', key='-FLOATING-', 
                      size=(25, 2), font=self.fonts['body'])],
            [sg.Text('半透明悬浮，快捷键展示', 
                    font=self.fonts['caption'], text_color=self.colors['text_secondary'])],
            
            [sg.HSeparator()],
            [sg.Button('退出', key='-EXIT-', size=(10, 1))]
        ]
        
        window = sg.Window(
            'ContextSwitcher 风格选择',
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
            elif event == '-COMPACT-':
                window.close()
                self.show_compact_widget()
            elif event == '-MANAGER-':
                window.close()
                self.show_task_manager()
            elif event == '-CARDS-':
                window.close()
                self.show_card_style()
            elif event == '-FLOATING-':
                window.close()
                self.show_floating_assistant()
        
        window.close()
    
    def show_compact_widget(self):
        """显示紧凑Widget风格"""
        sg.theme('ModernTaskManager')
        
        layout = [
            # 标题栏
            [sg.Text('📋', font=self.fonts['icon'], text_color=self.colors['primary']),
             sg.Text('ContextSwitcher', font=self.fonts['subheading'], 
                    text_color=self.colors['text_primary']),
             sg.Push(),
             sg.Text('●', font=self.fonts['icon'], text_color=self.colors['status_active']),
             sg.Text('3', font=self.fonts['caption'], text_color=self.colors['text_secondary'])],
            
            # 快速任务切换按钮
            [sg.Frame('', [
                [sg.Button('1', key='-TASK1-', size=(4, 1),
                          button_color=(self.colors['text_primary'], self.colors['success']),
                          font=self.fonts['body']),
                 sg.Button('2', key='-TASK2-', size=(4, 1),
                          button_color=(self.colors['text_primary'], self.colors['surface_variant']),
                          font=self.fonts['body']),
                 sg.Button('3', key='-TASK3-', size=(4, 1),
                          button_color=(self.colors['text_primary'], self.colors['surface_variant']),
                          font=self.fonts['body']),
                 sg.Button('+', key='-ADD-', size=(4, 1),
                          button_color=(self.colors['text_primary'], self.colors['warning']),
                          font=self.fonts['body'])]
            ], border_width=0, relief=sg.RELIEF_FLAT)],
            
            # 当前任务信息
            [sg.Text('当前任务:', font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary'])],
            [sg.Text('Web开发环境', key='-CURRENT_TASK-', 
                    font=self.fonts['body'], text_color=self.colors['text_primary'])],
            [sg.Text('3个窗口活跃', key='-WINDOW_COUNT-', 
                    font=self.fonts['caption'], text_color=self.colors['text_accent'])],
            
            # 系统资源
            [sg.Text('资源使用:', font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary'])],
            [sg.ProgressBar(100, orientation='h', size=(20, 8),
                          bar_color=(self.colors['primary'], self.colors['surface']),
                          key='-CPU_USAGE-'),
             sg.Text('CPU', font=self.fonts['small'], text_color=self.colors['text_secondary'])],
            [sg.ProgressBar(100, orientation='h', size=(20, 8),
                          bar_color=(self.colors['info'], self.colors['surface']),
                          key='-MEM_USAGE-'),
             sg.Text('内存', font=self.fonts['small'], text_color=self.colors['text_secondary'])],
            
            # 快捷键提示
            [sg.HSeparator()],
            [sg.Text('Ctrl+Alt+1-9', font=self.fonts['small'], 
                    text_color=self.colors['text_disabled'])]
        ]
        
        window = sg.Window(
            'ContextSwitcher Widget',
            layout,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            resizable=False,
            finalize=True,
            margins=(12, 8),
            element_padding=(3, 2),
            background_color=self.colors['background'],
            alpha_channel=0.95,
            location=(100, 100)
        )
        
        self._run_widget_loop(window)
    
    def show_task_manager(self):
        """显示任务管理器风格"""
        sg.theme('ModernTaskManager')
        
        # 工具栏
        toolbar = [
            [sg.Text('⚡ ContextSwitcher Pro', 
                    font=self.fonts['heading'], 
                    text_color=self.colors['primary']),
             sg.Push(),
             sg.Text('系统资源', font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary']),
             sg.Text('CPU: 15.2%', font=self.fonts['caption'], 
                    text_color=self.colors['text_accent']),
             sg.Text('内存: 8.5GB', font=self.fonts['caption'], 
                    text_color=self.colors['text_accent'])]
        ]
        
        # 任务表格
        headers = ['任务', '状态', '窗口', 'CPU%', '内存', '最后访问']
        table_data = []
        
        for task in self.tasks:
            status_icon = '🟢' if task['status'] == 'active' else '🟡'
            table_data.append([
                task['name'],
                f"{status_icon} {task['status']}",
                f"{len(task['windows'])}个",
                f"{task['cpu_usage']:.1f}%",
                task['memory_usage'],
                task['last_accessed'].strftime('%H:%M')
            ])
        
        table_section = [
            [sg.Table(
                values=table_data,
                headings=headers,
                key='-TASK_TABLE-',
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[20, 12, 8, 8, 8, 10],
                justification='left',
                alternating_row_color=self.colors['surface'],
                selected_row_colors=(self.colors['text_primary'], self.colors['primary']),
                header_text_color=self.colors['text_primary'],
                header_background_color=self.colors['surface_variant'],
                header_font=self.fonts['caption'] + ('bold',),
                font=self.fonts['caption'],
                num_rows=8,
                expand_x=True,
                expand_y=True,
                row_height=28,
                background_color=self.colors['background'],
                text_color=self.colors['text_primary']
            )]
        ]
        
        # 操作按钮
        button_section = [
            [sg.Button('新建任务', key='-NEW_TASK-',
                      button_color=(self.colors['text_primary'], self.colors['success']),
                      font=self.fonts['body']),
             sg.Button('切换到任务', key='-SWITCH_TASK-',
                      button_color=(self.colors['text_primary'], self.colors['primary']),
                      font=self.fonts['body']),
             sg.Button('编辑任务', key='-EDIT_TASK-',
                      button_color=(self.colors['text_primary'], self.colors['warning']),
                      font=self.fonts['body']),
             sg.Button('删除任务', key='-DELETE_TASK-',
                      button_color=(self.colors['text_primary'], self.colors['danger']),
                      font=self.fonts['body']),
             sg.Push(),
             sg.Button('设置', key='-SETTINGS-',
                      button_color=(self.colors['text_primary'], self.colors['secondary']),
                      font=self.fonts['body']),
             sg.Button('关于', key='-ABOUT-',
                      button_color=(self.colors['text_primary'], self.colors['info']),
                      font=self.fonts['body'])]
        ]
        
        # 状态栏
        status_bar = [
            [sg.Text('就绪', key='-STATUS-', 
                    font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary']),
             sg.Push(),
             sg.Text(f'总任务: {len(self.tasks)}', 
                    font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary']),
             sg.Text('|', text_color=self.colors['divider']),
             sg.Text(f'活跃: {sum(1 for t in self.tasks if t["status"] == "active")}', 
                    font=self.fonts['caption'], 
                    text_color=self.colors['status_active'])]
        ]
        
        # 组合布局
        layout = [
            *toolbar,
            [sg.HSeparator()],
            *table_section,
            [sg.HSeparator()],
            *button_section,
            [sg.HSeparator()],
            *status_bar
        ]
        
        window = sg.Window(
            'ContextSwitcher Pro',
            layout,
            finalize=True,
            resizable=True,
            size=(900, 600),
            margins=(15, 15),
            element_padding=(5, 5),
            background_color=self.colors['background']
        )
        
        self._run_manager_loop(window)
    
    def show_card_style(self):
        """显示卡片式风格"""
        sg.theme('ModernTaskManager')
        
        def create_task_card(task, is_current=False):
            """创建任务卡片"""
            border_color = self.colors['primary'] if is_current else self.colors['border']
            bg_color = self.colors['elevated'] if is_current else self.colors['surface']
            
            status_color = self.colors['status_active'] if task['status'] == 'active' else self.colors['status_idle']
            
            return sg.Frame('', [
                [sg.Text(task['name'], font=self.fonts['subheading'], 
                        text_color=self.colors['text_primary'])],
                [sg.Text(f"● {task['status']}", font=self.fonts['caption'],
                        text_color=status_color),
                 sg.Push(),
                 sg.Text(f"{len(task['windows'])} 窗口", font=self.fonts['caption'],
                        text_color=self.colors['text_accent'])],
                [sg.Text('窗口: ' + ', '.join(task['windows'][:2]) + 
                        (f' +{len(task["windows"])-2}' if len(task['windows']) > 2 else ''),
                        font=self.fonts['caption'],
                        text_color=self.colors['text_secondary'])],
                [sg.HSeparator()],
                [sg.Text(f"CPU: {task['cpu_usage']:.1f}%", 
                        font=self.fonts['small'],
                        text_color=self.colors['text_secondary']),
                 sg.Push(),
                 sg.Text(f"内存: {task['memory_usage']}", 
                        font=self.fonts['small'],
                        text_color=self.colors['text_secondary'])],
                [sg.Button('切换', key=f'-SWITCH_{task["id"]}-', 
                          size=(8, 1),
                          button_color=(self.colors['text_primary'], self.colors['primary']),
                          font=self.fonts['caption']),
                 sg.Push(),
                 sg.Button('编辑', key=f'-EDIT_{task["id"]}-', 
                          size=(8, 1),
                          button_color=(self.colors['text_primary'], self.colors['warning']),
                          font=self.fonts['caption'])]
            ], border_width=2, relief=sg.RELIEF_SOLID,
            background_color=bg_color,
            title_color=border_color,
            element_justification='left')
        
        # 标题区域
        header = [
            [sg.Text('📋 任务卡片', font=self.fonts['title'], 
                    text_color=self.colors['primary']),
             sg.Push(),
             sg.Button('+ 新建', key='-NEW_CARD-',
                      button_color=(self.colors['text_primary'], self.colors['success']),
                      font=self.fonts['body'])]
        ]
        
        # 卡片网格
        cards = []
        for i, task in enumerate(self.tasks):
            is_current = i == self.current_task
            cards.append([create_task_card(task, is_current)])
        
        # 底部信息
        footer = [
            [sg.Text('提示: 点击切换按钮快速切换任务', 
                    font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary']),
             sg.Push(),
             sg.Text('Ctrl+Alt+1-9 快速切换', 
                    font=self.fonts['caption'], 
                    text_color=self.colors['text_disabled'])]
        ]
        
        layout = [
            *header,
            [sg.HSeparator()],
            *cards,
            [sg.HSeparator()],
            *footer
        ]
        
        window = sg.Window(
            'ContextSwitcher Cards',
            layout,
            finalize=True,
            resizable=False,
            margins=(20, 20),
            element_padding=(8, 8),
            background_color=self.colors['background'],
            grab_anywhere=True
        )
        
        self._run_cards_loop(window)
    
    def show_floating_assistant(self):
        """显示悬浮助手风格"""
        sg.theme('ModernTaskManager')
        
        layout = [
            # 标题
            [sg.Text('⚡', font=self.fonts['icon'], text_color=self.colors['primary']),
             sg.Text('Quick Switch', font=self.fonts['subheading'], 
                    text_color=self.colors['text_primary'])],
            
            # 快捷键列表
            [sg.Text('快捷键:', font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary'])],
        ]
        
        # 添加快捷键项
        shortcuts = [
            ('Ctrl+Alt+1', 'Web开发环境'),
            ('Ctrl+Alt+2', '文档编写'),
            ('Ctrl+Alt+3', '设计工作'),
            ('Ctrl+Alt+N', '新建任务'),
            ('Ctrl+Alt+S', '设置')
        ]
        
        for shortcut, description in shortcuts:
            layout.append([
                sg.Text(shortcut, font=self.fonts['code'], 
                       text_color=self.colors['text_accent'], size=(12, 1)),
                sg.Text('→', font=self.fonts['caption'], 
                       text_color=self.colors['text_secondary']),
                sg.Text(description, font=self.fonts['caption'], 
                       text_color=self.colors['text_primary'])
            ])
        
        layout.extend([
            [sg.HSeparator()],
            [sg.Text('当前任务:', font=self.fonts['caption'], 
                    text_color=self.colors['text_secondary'])],
            [sg.Text(self.tasks[self.current_task]['name'], 
                    font=self.fonts['body'], 
                    text_color=self.colors['primary'])],
            [sg.Text(f"{len(self.tasks[self.current_task]['windows'])} 个窗口活跃", 
                    font=self.fonts['caption'], 
                    text_color=self.colors['text_accent'])]
        ])
        
        window = sg.Window(
            'Quick Switch',
            layout,
            no_titlebar=True,
            keep_on_top=True,
            grab_anywhere=True,
            resizable=False,
            finalize=True,
            margins=(15, 15),
            element_padding=(5, 3),
            background_color=self.colors['background'],
            alpha_channel=0.9,
            location=(200, 200)
        )
        
        self._run_floating_loop(window)
    
    def _run_widget_loop(self, window):
        """运行Widget事件循环"""
        start_time = time.time()
        
        while True:
            event, values = window.read(timeout=100)
            
            if event == sg.WIN_CLOSED:
                break
            elif event in ['-TASK1-', '-TASK2-', '-TASK3-']:
                task_num = int(event[-2]) - 1
                if task_num < len(self.tasks):
                    self.current_task = task_num
                    window['-CURRENT_TASK-'].update(self.tasks[task_num]['name'])
                    window['-WINDOW_COUNT-'].update(f"{len(self.tasks[task_num]['windows'])}个窗口活跃")
                    
                    # 更新按钮状态
                    for i in range(3):
                        color = self.colors['success'] if i == task_num else self.colors['surface_variant']
                        window[f'-TASK{i+1}-'].update(button_color=(self.colors['text_primary'], color))
            elif event == '-ADD-':
                sg.popup_quick_message('添加新任务', auto_close_duration=1)
            
            # 更新资源使用率动画
            cpu_usage = 15 + 10 * (0.5 + 0.5 * time.sin(time.time() * 2))
            mem_usage = 65 + 15 * (0.5 + 0.5 * time.cos(time.time() * 1.5))
            
            window['-CPU_USAGE-'].update(int(cpu_usage))
            window['-MEM_USAGE-'].update(int(mem_usage))
        
        window.close()
        self.show_style_selector()
    
    def _run_manager_loop(self, window):
        """运行管理器事件循环"""
        while True:
            event, values = window.read()
            
            if event == sg.WIN_CLOSED:
                break
            elif event == '-TASK_TABLE-':
                if values['-TASK_TABLE-']:
                    selected_index = values['-TASK_TABLE-'][0]
                    task_name = self.tasks[selected_index]['name']
                    window['-STATUS-'].update(f'选中: {task_name}')
            elif event == '-SWITCH_TASK-':
                if values['-TASK_TABLE-']:
                    selected_index = values['-TASK_TABLE-'][0]
                    self.current_task = selected_index
                    sg.popup_quick_message(f'切换到: {self.tasks[selected_index]["name"]}', 
                                         auto_close_duration=1)
            elif event == '-NEW_TASK-':
                sg.popup('新建任务', '这里可以创建新任务')
            elif event in ['-EDIT_TASK-', '-DELETE_TASK-', '-SETTINGS-', '-ABOUT-']:
                sg.popup(f'功能: {event}', '此功能正在开发中')
        
        window.close()
        self.show_style_selector()
    
    def _run_cards_loop(self, window):
        """运行卡片事件循环"""
        while True:
            event, values = window.read()
            
            if event == sg.WIN_CLOSED:
                break
            elif event.startswith('-SWITCH_'):
                task_id = int(event.split('_')[1].replace('-', ''))
                task_index = next(i for i, t in enumerate(self.tasks) if t['id'] == task_id)
                self.current_task = task_index
                sg.popup_quick_message(f'切换到: {self.tasks[task_index]["name"]}', 
                                     auto_close_duration=1)
                # 重新创建界面以更新卡片状态
                window.close()
                self.show_card_style()
                return
            elif event.startswith('-EDIT_'):
                task_id = int(event.split('_')[1].replace('-', ''))
                sg.popup('编辑任务', f'编辑任务 ID: {task_id}')
            elif event == '-NEW_CARD-':
                sg.popup('新建任务', '创建新任务卡片')
        
        window.close()
        self.show_style_selector()
    
    def _run_floating_loop(self, window):
        """运行悬浮助手事件循环"""
        start_time = time.time()
        
        while True:
            event, values = window.read(timeout=100)
            
            if event == sg.WIN_CLOSED:
                break
            
            # 5秒后自动关闭（演示用）
            if time.time() - start_time > 8:
                break
        
        window.close()
        self.show_style_selector()


def main():
    """主函数"""
    print("ContextSwitcher 现代化UI演示")
    print("="*40)
    
    # 设置全局字体
    sg.set_options(font=('Segoe UI', 10))
    
    # 创建UI实例
    ui = ModernTaskManagerUI()
    
    # 显示风格选择器
    ui.show_style_selector()


if __name__ == "__main__":
    main()