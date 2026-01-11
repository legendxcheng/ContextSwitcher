"""
弹出式任务切换器对话框模块

提供大尺寸的任务切换界面：
- 800x700像素窗口，显示在屏幕中央
- 支持键盘方向键和鼠标滚轮导航
- 2秒自动超时切换
- 丰富的任务信息展示

重构说明：
- 配置管理已移至 switcher_config.py
- 布局创建已移至 switcher_layout.py
- UI更新已移至 switcher_ui_updater.py
- 事件处理已移至 switcher_event_handler.py
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
from utils.screen_helper import ScreenHelper
from utils.dialog_position_manager import get_dialog_position_manager
from gui.switcher import SwitcherConfig, SwitcherLayout, SwitcherUIUpdater, SwitcherEventHandler


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

        # 初始化子模块
        self.config = SwitcherConfig()
        self.layout_builder = SwitcherLayout(self.config)
        self.ui_updater = SwitcherUIUpdater(self.config)
        self.event_handler = SwitcherEventHandler(self.config, self.ui_updater)

        # 窗口实例
        self.window: Optional[sg.Window] = None
        self.is_showing = False  # 防止重复打开（线程安全：只在主线程中访问）

        # 任务数据
        self.selected_task_index = 0
        self.tasks: List[Task] = []

        # 提示窗口冷却机制
        self.last_hint_time = 0
        self.hint_cooldown = 5.0  # 提示冷却时间（秒）

        # 任务切换器显示冷却机制（防止重复触发）
        self.last_show_time = 0
        self.show_cooldown = 1.0  # 显示冷却时间（秒）

        # 事件回调
        self.on_task_selected: Optional[Callable[[int], None]] = None
        self.on_dialog_closed: Optional[Callable] = None

        print("✓ 任务切换器对话框初始化完成")

    def show(self, main_window_position: Tuple[int, int] = None) -> bool:
        """显示任务切换器对话框

        Args:
            main_window_position: 主窗口位置 (x, y)，用于计算最佳显示位置

        Returns:
            是否成功执行了任务切换
        """
        try:
            # 检查功能是否启用
            if not self.config.enabled:
                print("任务切换器功能已禁用")
                return False

            # 检查显示冷却时间，防止重复触发
            current_time = time.time()
            if current_time - self.last_show_time < self.show_cooldown:
                remaining_cooldown = self.show_cooldown - (current_time - self.last_show_time)
                print(f"任务切换器在冷却期内，剩余 {remaining_cooldown:.1f} 秒")
                return False

            # 防止重复打开，如果已经显示则重置定时器
            if self.is_showing:
                print("任务切换器已在显示中，重置定时器")
                self.event_handler.reset_auto_close_timer()
                return False

            self.is_showing = True
            self.last_show_time = current_time

            # 获取当前任务列表
            self.tasks = self.task_manager.get_all_tasks()

            if not self.tasks:
                print("没有可切换的任务")
                self._handle_no_tasks()
                return False

            # 根据任务数量动态计算窗口尺寸
            dynamic_window_size = self.config.calculate_window_size(len(self.tasks))

            # 计算窗口显示位置
            window_position = self._calculate_window_position(dynamic_window_size, main_window_position)

            # 创建并显示窗口
            result = self._create_and_show_window(dynamic_window_size, window_position)

            return result

        except Exception as e:
            print(f"显示任务切换器失败: {e}")
            return False
        finally:
            self._cleanup()
            self.is_showing = False

    def _handle_no_tasks(self):
        """处理没有任务的情况"""
        current_time = time.time()
        if current_time - self.last_hint_time > self.hint_cooldown:
            print("显示无任务提示（在冷却期外）")
            self._show_no_tasks_message()
            self.last_hint_time = current_time
        else:
            remaining_cooldown = self.hint_cooldown - (current_time - self.last_hint_time)
            print(f"无任务提示在冷却期内，剩余 {remaining_cooldown:.1f} 秒")

    def _calculate_window_position(self, window_size: Tuple[int, int], main_window_position: Optional[Tuple[int, int]]) -> Tuple[int, int]:
        """计算窗口显示位置

        Args:
            window_size: 窗口尺寸
            main_window_position: 主窗口位置

        Returns:
            窗口位置 (x, y)
        """
        if main_window_position:
            return self.position_manager.get_switcher_dialog_position(
                window_size, main_window_position
            )
        else:
            # 回退到基于鼠标位置的多屏幕计算
            return self.screen_helper.get_optimal_window_position_multiscreen(window_size)

    def _create_and_show_window(self, window_size: Tuple[int, int], window_position: Tuple[int, int]) -> bool:
        """创建并显示窗口

        Args:
            window_size: 窗口尺寸
            window_position: 窗口位置

        Returns:
            是否成功执行了任务切换
        """
        # 创建窗口布局
        layout = self.layout_builder.create_layout(self.tasks, self.selected_task_index)

        # 创建窗口
        self.window = sg.Window(
            "任务切换器",
            layout,
            keep_on_top=True,
            no_titlebar=True,
            modal=False,
            finalize=True,
            resizable=False,
            size=window_size,
            location=window_position,
            alpha_channel=0.95,
            margins=(8, 8),
            element_padding=(3, 3),
            background_color=self.config.colors['background'],
            return_keyboard_events=True,
            use_default_focus=True,
            grab_anywhere=False
        )

        # 确保窗口获得焦点
        self.window.bring_to_front()
        self.window.refresh()

        # 初始化选中状态
        self.selected_task_index = 0
        self.ui_updater.set_selected_index(0)
        self.ui_updater.update_selection_display(self.window, self.tasks)

        # 启动自动关闭定时器
        self.event_handler.start_auto_close_timer()

        # 运行事件循环
        return self._run_event_loop()

    def _run_event_loop(self) -> bool:
        """运行事件循环（委托给事件处理器）"""
        return self.event_handler.run_event_loop(
            self.window,
            self.tasks,
            self._execute_task_switch,
            self._on_selection_moved
        )

    def _on_selection_moved(self, direction: int):
        """选中位置移动回调"""
        # 实际移���逻辑已在事件处理器中完成
        pass

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
                auto_close_duration=2
            )

            print("💡 显示无任务提示窗口")

            # 简单的事件循环
            start_time = time.time()
            while time.time() - start_time < 2.5:
                event, values = hint_window.read(timeout=100)
                if event in (sg.WIN_CLOSED, sg.TIMEOUT_EVENT):
                    break

            hint_window.close()

        except Exception as e:
            print(f"显示提示信息失败: {e}")
            print("💡 提示: 请先在主窗口添加任务，然后使用 Ctrl+Alt+空格 切换")

    def _execute_task_switch(self) -> bool:
        """执行任务切换

        Returns:
            是否成功切换
        """
        try:
            task_index = self.ui_updater.selected_index

            if 0 <= task_index < len(self.tasks):
                task = self.tasks[task_index]

                print(f"🔄 正在切换到任务: {task.name}")

                success = self.task_manager.switch_to_task(task_index)

                if success:
                    print(f"✅ 成功切换到任务: {task.name}")

                    # 触发回调
                    if self.on_task_selected:
                        self.on_task_selected(task_index)

                    return True
                else:
                    print(f"❌ 任务切换失败: {task.name}")
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
        except Exception as e:
            print(f"强制关闭窗口失败: {e}")

    def _cleanup(self):
        """清理资源（线程安全）"""
        try:
            # 重置时间戳
            self.event_handler.auto_close_start_time = 0

            # 安全关闭窗口
            if self.window:
                try:
                    window = self.window
                    self.window = None
                    window.close()
                except Exception as e:
                    print(f"关闭窗口时出错: {e}")
                    self.window = None

            # 重置状态
            self.is_showing = False
            self.event_handler._auto_executed = False

            # 触发关闭回调
            if self.on_dialog_closed:
                try:
                    self.on_dialog_closed()
                except Exception as e:
                    print(f"关闭回调执行失败: {e}")

            print("✓ 任务切换器资源已清理")

        except Exception as e:
            print(f"清理任务切换器资源失败: {e}")
