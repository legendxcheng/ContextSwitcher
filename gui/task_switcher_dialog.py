"""
弹出式任务切换器对话框模块

提供大尺寸的任务切换界面：
- 800x700像素窗口，显示在屏幕中央
- 支持键盘方向键和鼠标滚轮导航
- 2秒自动超时切换
- 丰富的任务信息展示
"""

import time
from typing import List, Dict, Any, Optional, Callable, Tuple

try:
    import FreeSimpleGUI as sg
    sg.theme('DarkGrey13')
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise

from core.task_manager import TaskManager, Task
from gui.modern_config import ModernUIConfig
from utils.screen_helper import ScreenHelper
from utils.dialog_position_manager import get_dialog_position_manager


class TaskSwitcherDialog:
    """弹出式任务切换器对话框"""
    
    def __init__(self, task_manager: TaskManager):
        """初始化任务切换器
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.screen_helper = ScreenHelper()
        self.position_manager = get_dialog_position_manager()
        
        # 加载配置
        from utils.config import get_config
        config = get_config()
        switcher_config = config.get_task_switcher_config()
        
        # 窗口配置 - 缩小尺寸
        self.window_size = tuple(switcher_config.get("window_size", [500, 200]))
        self.auto_close_delay = switcher_config.get("auto_close_delay", 2.0)
        self.show_empty_slots = switcher_config.get("show_empty_slots", True)
        self.enabled = switcher_config.get("enabled", True)
        
        self.window: Optional[sg.Window] = None
        self.is_showing = False  # 防止重复打开（线程安全：只在主线程中访问）
        
        # 选中状态
        self.selected_task_index = 0
        self.tasks: List[Task] = []
        
        # 自动超时控制（使用时间戳，完全避免线程定时器）
        self._auto_executed = False  # 标记是否自动执行
        self.auto_close_start_time = 0  # 自动关闭开始时间
        
        # 提示窗口冷却机制
        self.last_hint_time = 0  # 上次显示提示的时间
        self.hint_cooldown = 5.0  # 提示冷却时间（秒）
        
        # 任务切换器显示冷却机制（防止重复触发）
        self.last_show_time = 0  # 上次显示的时间
        self.show_cooldown = 1.0  # 显示冷却时间（秒）
        
        # 字体配置 - 适配小界面
        self.fonts = {
            'task_title': ('Segoe UI', 12, 'bold'),    # 任务名称
            'task_info': ('Segoe UI', 10),             # 任务详情
            'hotkey': ('Segoe UI', 11, 'bold'),        # 快捷键编号
            'status': ('Segoe UI', 9, 'bold'),         # 状态信息
            'timestamp': ('Segoe UI', 8),              # 时间戳
            'instruction': ('Segoe UI', 9),            # 操作说明
        }
        
        # 颜色配置
        self.colors = ModernUIConfig.COLORS
        
        # 事件回调
        self.on_task_selected: Optional[Callable[[int], None]] = None
        self.on_dialog_closed: Optional[Callable] = None
        
        print("✓ 任务切换器对话框初始化完成")
    
    def _calculate_window_size(self, task_count: int) -> Tuple[int, int]:
        """根据任务数量计算窗口尺寸
        
        Args:
            task_count: 任务数量
            
        Returns:
            (width, height) 窗口尺寸
        """
        # 基础尺寸
        base_width = 400
        base_height = 80   # 标题 + 分隔线 + 底部说明的基础高度
        
        # 每个任务行的高度（包括间距）
        task_row_height = 25  # 进一步减小行高
        
        # 根据任务数量计算高度
        tasks_height = task_count * task_row_height
        
        # 总高度 = 基础高度 + 任务行高度
        total_height = base_height + tasks_height
        
        # 设置最小和最大尺寸
        min_width, min_height = 350, 100
        max_width, max_height = 600, 400
        
        width = max(min_width, min(max_width, base_width))
        height = max(min_height, min(max_height, total_height))
        
        print(f"📏 窗口尺寸计算: {task_count}个任务 -> {width}x{height}")
        return (width, height)
    
    def _show_no_tasks_message(self):
        """显示没有任务时的提示信息"""
        try:
            # 创建简单的提示布局
            layout = [
                [sg.Text("📝 还没有任何任务", font=('Segoe UI', 13, 'bold'), 
                        text_color='#FFFFFF', justification='center')],
                [sg.Text("")],  # 空行
                [sg.Text("请先在主窗口中点击 ＋ 添加任务", font=('Segoe UI', 10), 
                        text_color='#CCCCCC', justification='center')],
                [sg.Text("")],  # 空行
                [sg.Text("5秒内不会再次显示此提示", font=('Segoe UI', 8), 
                        text_color='#888888', justification='center')]
            ]
            
            # 计算提示窗口位置（屏幕中央）
            screen_info = self.screen_helper.get_screen_metrics()
            window_width, window_height = 300, 120
            window_x = screen_info['width'] // 2 - window_width // 2
            window_y = screen_info['height'] // 2 - window_height // 2
            
            # 创建提示窗口
            hint_window = sg.Window(
                "任务切换器 - 提示",
                layout,
                keep_on_top=True,
                no_titlebar=True,
                modal=False,
                finalize=True,
                resizable=False,
                size=(window_width, window_height),
                location=(window_x, window_y),
                alpha_channel=0.95,
                margins=(15, 15),
                element_padding=(5, 5),
                background_color='#2D2D2D',
                auto_close=True,
                auto_close_duration=2  # 2秒后自动关闭
            )
            
            print("💡 显示无任务提示窗口")
            
            # 简单的事件循环，或者等待自动关闭
            start_time = time.time()
            while time.time() - start_time < 2.5:  # 最多等待2.5秒
                event, values = hint_window.read(timeout=100)
                if event in (sg.WIN_CLOSED, sg.TIMEOUT_EVENT):
                    break
            
            hint_window.close()
            
        except Exception as e:
            print(f"显示提示信息失败: {e}")
            # 备用方案：只在控制台输出
            print("💡 提示: 请先在主窗口添加任务，然后使用 Ctrl+Alt+空格 切换")
    
    def show(self, main_window_position: Tuple[int, int] = None) -> bool:
        """显示任务切换器对话框
        
        Args:
            main_window_position: 主窗口位置 (x, y)，用于计算最佳显示位置
        
        Returns:
            是否成功执行了任务切换
        """
        try:
            # 检查功能是否启用
            if not self.enabled:
                print("任务切换器功能已禁用")
                return False
            
            # 检查显示冷却时间，防止重复触发
            current_time = time.time()
            if current_time - self.last_show_time < self.show_cooldown:
                remaining_cooldown = self.show_cooldown - (current_time - self.last_show_time)
                print(f"任务切换器在冷却期内，剩余 {remaining_cooldown:.1f} 秒")
                return False
            
            # 防止重复打开，如果已经显示则重置定时器（线程安全检查）
            if self.is_showing:
                print("任务切换器已在显示中，重置定时器")
                self._reset_auto_close_timer()
                return False
            
            self.is_showing = True
            
            # 更新显示时间
            self.last_show_time = current_time
            
            # 获取当前任务列表
            self.tasks = self.task_manager.get_all_tasks()
            
            if not self.tasks:
                print("没有可切换的任务")
                # 检查冷却时间，避免重复显示提示
                current_time = time.time()
                if current_time - self.last_hint_time > self.hint_cooldown:
                    print("显示无任务提示（在冷却期外）")
                    self._show_no_tasks_message()
                    self.last_hint_time = current_time
                else:
                    remaining_cooldown = self.hint_cooldown - (current_time - self.last_hint_time)
                    print(f"无任务提示在冷却期内，剩余 {remaining_cooldown:.1f} 秒")
                return False
            
            # 根据任务数量动态计算窗口尺寸
            dynamic_window_size = self._calculate_window_size(len(self.tasks))
            
            # 计算窗口显示位置 - 使用多屏幕优化和主窗口位置
            if main_window_position:
                window_position = self.position_manager.get_switcher_dialog_position(
                    dynamic_window_size, main_window_position
                )
            else:
                # 回退到基于鼠标位置的多屏幕计算
                window_position = self.screen_helper.get_optimal_window_position_multiscreen(dynamic_window_size)
            
            # 创建窗口布局
            layout = self._create_layout()
            
            # 创建窗口
            self.window = sg.Window(
                "任务切换器",
                layout,
                keep_on_top=True,
                no_titlebar=True,
                modal=False,  # 修复：改为非模态避免事件阻塞
                finalize=True,
                resizable=False,
                size=dynamic_window_size,
                location=window_position,
                alpha_channel=0.95,
                margins=(8, 8),        # 减小边距
                element_padding=(3, 3), # 减小元素间距
                background_color=self.colors['background'],
                return_keyboard_events=True,
                use_default_focus=False,
                grab_anywhere=True
            )
            
            # 初始化选中状态为第一个任务
            self.selected_task_index = 0
            # 初始化选中状态
            # 立即更新选中状态显示
            self._update_selection_display()
            
            # 启动自动关闭定时器
            self._start_auto_close_timer()
            
            # 运行事件循环
            result = self._run_event_loop()
            
            return result
            
        except Exception as e:
            print(f"显示任务切换器失败: {e}")
            return False
        finally:
            self._cleanup()
            self.is_showing = False
    
    def _create_layout(self) -> List[List[Any]]:
        """创建窗口布局"""
        layout = []
        
        # 标题行
        title_row = [
            sg.Text("任务切换器", font=self.fonts['task_title'], 
                   text_color=self.colors['text'], pad=(0, 5))  # 减小间距
        ]
        layout.append(title_row)
        
        # 分隔线
        layout.append([sg.HorizontalSeparator()])
        
        # 任务列表区域 - 只显示实际存在的任务
        task_list_column = []
        
        for i in range(len(self.tasks)):  # 只显示实际任务数量
            task = self.tasks[i]
            task_row = self._create_task_row(i, task)
            task_list_column.append(task_row)
            
            # 添加行间距（除了最后一行） - 缩小间距
            if i < len(self.tasks) - 1:
                task_list_column.append([sg.Text("", size=(1, 0))])
        
        # 将任务列表放在紧凑的列中
        layout.append([
            sg.Column(
                task_list_column,
                expand_x=True,
                expand_y=False,  # 不强制垂直展开
                scrollable=False,
                background_color=self.colors['background'],
                pad=(0, 5)  # 减小间距
            )
        ])
        
        # 分隔线
        layout.append([sg.HorizontalSeparator()])
        
        # 底部操作说明（带倒计时显示）
        instruction_row = [
            sg.Text("↑↓ 选择 | 回车确认 | ESC取消",
                   font=self.fonts['instruction'],
                   text_color=self.colors['text_secondary'],
                   pad=(0, 5)),
            sg.Push(),
            sg.Text("⏱", font=self.fonts['status'], text_color=self.colors['warning']),
            sg.Text("2.0", key="-COUNTDOWN-", font=self.fonts['status'],
                   text_color=self.colors['warning'], size=(3, 1)),
            sg.Text("秒", font=self.fonts['instruction'], text_color=self.colors['text_secondary'])
        ]
        layout.append(instruction_row)

        return layout
    
    def _create_task_row(self, index: int, task: Task) -> List[Any]:
        """创建简化的任务行（只显示编号和任务名）"""
        # 判断是否为选中状态
        is_selected = (index == self.selected_task_index)
        
        # 选中状态的颜色配置
        if is_selected:
            bg_color = self.colors['primary']  # 蓝色背景
            text_color = '#FFFFFF'  # 白色文字
            hotkey_color = '#FFFFFF'  # 白色编号
            prefix = "▶ "  # 播放符号
        else:
            bg_color = self.colors['surface']  # 默认背景
            text_color = self.colors['text']  # 默认文字
            hotkey_color = self.colors['primary']  # 蓝色编号
            prefix = "  "  # 空格
        
        # 任务编号
        hotkey_text = sg.Text(
            f"[{index + 1}]",
            font=self.fonts['hotkey'],
            text_color=hotkey_color,
            size=(3, 1),  # 缩小编号宽度
            key=f"-HOTKEY-{index}-",
            background_color=bg_color
        )
        
        # 任务名称（加上选中指示符）
        display_name = f"{prefix}{task.name}"
        task_name = sg.Text(
            display_name,
            font=self.fonts['task_title'],
            text_color=text_color,
            size=(25, 1),  # 减小宽度适配小界面
            key=f"-TASK_NAME-{index}-",
            background_color=bg_color
        )
        
        # 创建简化的任务行（只有编号和名称）
        row_elements = [hotkey_text, task_name]
        
        return [sg.Frame(
            "",
            [row_elements],
            border_width=2 if is_selected else 1,
            background_color=bg_color,
            key=f"-TASK_ROW-{index}-",
            expand_x=True,
            element_justification='left',
            pad=(4, 1),  # 进一步减小垂直间距
            relief=sg.RELIEF_RAISED if is_selected else sg.RELIEF_FLAT
        )]
    
    def _create_empty_task_row(self, index: int) -> List[Any]:
        """创建简化的空任务行"""
        hotkey_text = sg.Text(
            f"[{index + 1}]",
            font=self.fonts['hotkey'],
            text_color=self.colors['text_disabled'],
            size=(4, 1),
            background_color=self.colors['background']
        )
        
        empty_text = sg.Text(
            "  （空）",
            font=self.fonts['task_info'],
            text_color=self.colors['text_disabled'],
            size=(35, 1),
            background_color=self.colors['background']
        )
        
        return [sg.Frame(
            "",
            [[hotkey_text, empty_text]],
            border_width=1,
            background_color=self.colors['background'],
            key=f"-EMPTY_ROW-{index}-",
            expand_x=True,
            element_justification='left',
            pad=(8, 6),  # 与任务行保持一致的间距
            relief=sg.RELIEF_FLAT
        )]
    
    def _get_status_color(self, status) -> str:
        """获取状态对应的颜色"""
        status_colors = {
            "todo": self.colors['text_secondary'],
            "in_progress": self.colors['primary'],
            "blocked": self.colors['warning'],
            "review": self.colors['warning'],
            "completed": self.colors['success'],
            "paused": self.colors['text_disabled']
        }
        return status_colors.get(status.value, self.colors['text'])
    
    def _get_time_display(self, timestamp: str) -> str:
        """获取时间显示文本"""
        try:
            from datetime import datetime
            last_time = datetime.fromisoformat(timestamp)
            now = datetime.now()
            diff = now - last_time
            
            if diff.days > 0:
                return f"{diff.days}天前"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours}小时前"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes}分钟前"
            else:
                return "刚刚"
        except:
            return "未知"
    
    def _update_selection_display(self):
        """更新选中状态的显示（简化版，避免不支持的API）"""
        if not self.window:
            return

        try:
            # 简化版本：只更新文字内容，避免颜色更新导致的API错误
            for i in range(min(9, len(self.tasks))):
                task = self.tasks[i]
                is_selected = (i == self.selected_task_index)

                # 更新任务名称显示
                task_name_key = f"-TASK_NAME-{i}-"

                if task_name_key in self.window.AllKeysDict:
                    # 更新任务名称显示（只更新文字内容）
                    if is_selected:
                        display_name = f"▶ {task.name}"
                    else:
                        display_name = f"  {task.name}"

                    # 只更新文字内容，避免颜色更新
                    self.window[task_name_key].update(value=display_name)

            # print(f"🎯 选中状态已更新: 第{self.selected_task_index + 1}个任务")  # 减少log输出

        except Exception as e:
            print(f"更新选中状态显示失败: {e}")
            # 不打印完整traceback，避免日志过多

    def _update_countdown_display(self, remaining_time: float):
        """更新倒计时显示

        Args:
            remaining_time: 剩余时间（秒）
        """
        if not self.window:
            return

        try:
            countdown_key = "-COUNTDOWN-"
            if countdown_key in self.window.AllKeysDict:
                # 格式化显示
                display_text = f"{remaining_time:.1f}"

                # 根据剩余时间改变颜色
                if remaining_time <= 0.5:
                    color = self.colors['error']  # 红色 - 即将切换
                elif remaining_time <= 1.0:
                    color = self.colors['warning']  # 橙色 - 警告
                else:
                    color = self.colors['primary']  # 蓝色 - 正常

                self.window[countdown_key].update(display_text, text_color=color)
        except:
            pass  # 忽略更新失败
    
    def _start_auto_close_timer(self):
        """启动自动关闭定时器（只使用时间戳，完全避免线程定时器）"""
        # 只记录开始时间，在事件循环中检查（完全线程安全）
        import time
        self.auto_close_start_time = time.time()
        print(f"⏰ 自动关闭定时器已启动，{self.auto_close_delay}秒后自动切换")
    
    def _reset_auto_close_timer(self):
        """重置自动关闭定时器（只重置时间戳）"""
        # 重新记录开始时间，完全避免线程操作
        import time
        self.auto_close_start_time = time.time()
        # print("⏰ 自动关闭定时器已重置")  # 减少log输出
    
    def _auto_execute_selection(self):
        """自动执行选中的任务切换（已弃用，避免线程问题）"""
        # 不再使用此方法，所有操作在事件循环中进行
        pass
    
    def _run_event_loop(self) -> bool:
        """运行事件循环"""
        try:
            while True:
                # 检查是否被自动执行中断
                if self._auto_executed:
                    # 检测到自动执行，退出事件循环
                    return True
                
                # 计算剩余时间，优化超时检查
                remaining_time = None
                if self.auto_close_start_time > 0:
                    import time
                    elapsed = time.time() - self.auto_close_start_time
                    if elapsed >= self.auto_close_delay:
                        # 时间到了，执行自动切换
                        print("⏰ 自动关闭时间到，执行任务切换")
                        self._auto_executed = True
                        success = self._execute_task_switch()
                        return success
                    else:
                        # 计算剩余时间，优化timeout设置
                        remaining_time = self.auto_close_delay - elapsed
                        # 更新倒计时显示
                        self._update_countdown_display(remaining_time)
                
                # 动态调整超时时间：如果有倒计时，使用较短的timeout便于及时响应
                timeout = min(100, int(remaining_time * 1000)) if remaining_time else 100
                event, values = self.window.read(timeout=timeout)
                
                # 过滤超时事件
                
                # 超时事件 - 继续循环
                if event == sg.TIMEOUT_EVENT:
                    continue
                
                if event == sg.WIN_CLOSED or event in ["Escape:27", "Escape", "escape", "esc"]:
                    # 用户取消或关闭窗口
                    return False
                
                elif event in ["Return:13", "Return", "return", "enter", "\r"]:
                    # 回车确认
                    # 用户按回车确认
                    success = self._execute_task_switch()
                    return success
                
                elif event in ["Up:38", "Up", "up", "Key_Up", "VK_UP", "Special 38"]:
                    # 上箭头（扩展事件支持）
                    try:
                        self._move_selection(-1)
                        self._reset_auto_close_timer()
                    except Exception as e:
                        print(f"处理上箭头键失败: {e}")
                
                elif event in ["Down:40", "Down", "down", "Key_Down", "VK_DOWN", "Special 40"]:
                    # 下箭头（扩展事件支持）
                    try:
                        self._move_selection(1)
                        self._reset_auto_close_timer()
                    except Exception as e:
                        print(f"处理下箭头键失败: {e}")
                
                elif (event.startswith("1") or event.startswith("2") or event.startswith("3") or 
                      event.startswith("4") or event.startswith("5") or event.startswith("6") or 
                      event.startswith("7") or event.startswith("8") or event.startswith("9") or
                      event in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]):
                    # 数字键1-9快速选择
                    try:
                        # 提取数字
                        if event in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                            key_num = int(event) - 1
                        else:
                            key_num = int(event[0]) - 1
                        
                        if 0 <= key_num < len(self.tasks):
                            # 数字键快速选择
                            self.selected_task_index = key_num
                            self._update_selection_display()
                            success = self._execute_task_switch()
                            return success
                    except:
                        pass
                
                # 处理鼠标滚轮事件（扩展支持多种格式）
                elif event in ["MouseWheel:Up", "MouseWheel::Up", "WheelUp", "Wheel::Up", "Mouse Wheel Up"]:
                    self._move_selection(-1)
                    self._reset_auto_close_timer()
                
                elif event in ["MouseWheel:Down", "MouseWheel::Down", "WheelDown", "Wheel::Down", "Mouse Wheel Down"]:
                    self._move_selection(1)
                    self._reset_auto_close_timer()
                
                # 处理双击事件
                elif event and event.endswith("Double"):
                    # 双击立即切换
                    # 双击确认
                    success = self._execute_task_switch()
                    return success
                
        except Exception as e:
            print(f"事件循环异常: {e}")
            return False
    
    def _move_selection(self, direction: int):
        """移动选中位置（线程安全版本）"""
        if not self.tasks or not self.window:
            return
        
        try:
            new_index = self.selected_task_index + direction
            
            # 循环选择
            if new_index < 0:
                new_index = len(self.tasks) - 1
            elif new_index >= len(self.tasks):
                new_index = 0
            
            self.selected_task_index = new_index
            self._update_selection_display()
            
        except Exception as e:
            print(f"移动选择失败: {e}")
            # 不传播异常，保持界面稳定
    
    def _execute_task_switch(self) -> bool:
        """执行任务切换"""
        try:
            if 0 <= self.selected_task_index < len(self.tasks):
                task = self.tasks[self.selected_task_index]
                task_index = self.selected_task_index
                
                print(f"🔄 正在切换到任务: {task.name}")
                
                # 显示切换状态
                if self.window:
                    # 更新标题显示切换状态
                    for key in self.window.AllKeysDict:
                        if "任务切换器" in str(key):
                            break
                
                success = self.task_manager.switch_to_task(task_index)
                
                if success:
                    print(f"✅ 成功切换到任务: {task.name}")
                    
                    # 显示成功消息（短暂显示）
                    if self.window:
                        try:
                            # 可以在这里添加成功提示
                            pass
                        except:
                            pass
                    
                    # 触发回调
                    if self.on_task_selected:
                        self.on_task_selected(task_index)
                    
                    return True
                else:
                    print(f"❌ 任务切换失败: {task.name}")
                    
                    # 输出失败消息到控制台
                    print(f"❌ 切换到任务 '{task.name}' 失败 - 可能没有可用的窗口")
            
            return False
            
        except Exception as e:
            print(f"执行任务切换失败: {e}")
            return False
    
    def _force_close(self):
        """强制关闭窗口（用于自动超时）"""
        try:
            if self.window:
                self.window.close()
                self.window = None
            # 强制关闭任务切换器窗口
        except Exception as e:
            print(f"强制关闭窗口失败: {e}")
    
    def _cleanup(self):
        """清理资源（线程安全）"""
        try:
            # 重置时间戳（无需取消定时器，已改为时间戳机制）
            self.auto_close_start_time = 0
            
            # 安全关闭窗口（在主线程中）
            if self.window:
                try:
                    # 先设置为None避免其他地方继续使用
                    window = self.window
                    self.window = None
                    # 然后关闭
                    window.close()
                except Exception as e:
                    print(f"关闭窗口时出错: {e}")
                    # 确保window被设置为None
                    self.window = None
            
            # 重置状态
            self.is_showing = False
            self._auto_executed = False
            
            # 触发关闭回调
            if self.on_dialog_closed:
                try:
                    self.on_dialog_closed()
                except Exception as e:
                    print(f"关闭回调执行失败: {e}")
            
            print("✓ 任务切换器资源已清理")
            
        except Exception as e:
            print(f"清理任务切换器资源失败: {e}")