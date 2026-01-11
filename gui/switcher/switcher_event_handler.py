"""
任务切换器事件处理模块

负责处理任务切换器的事件循环和用户输入：
- 键盘事件（上下箭头、数字键、回车、ESC）
- 鼠标滚轮事件
- 自动超时处理
"""

import time
from typing import List, Callable, Optional, Any
from core.task_manager import Task
try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise


class SwitcherEventHandler:
    """任务切换器事件处理类"""

    # 退出事件列表
    EXIT_EVENTS = ["Escape:27", "Escape", "escape", "esc"]

    # 确认事件列表
    CONFIRM_EVENTS = ["Return:13", "Return", "return", "enter", "\r"]

    # 上箭头事件列表
    UP_EVENTS = ["Up:38", "Up", "up", "Key_Up", "VK_UP", "Special 38"]

    # 下箭头事件列表
    DOWN_EVENTS = ["Down:40", "Down", "down", "Key_Down", "VK_DOWN", "Special 40"]

    # 滚轮向上事件列表
    WHEEL_UP_EVENTS = ["MouseWheel:Up", "MouseWheel::Up", "WheelUp", "Wheel::Up", "Mouse Wheel Up"]

    # 滚轮向下事件列表
    WHEEL_DOWN_EVENTS = ["MouseWheel:Down", "MouseWheel::Down", "WheelDown", "Wheel::Down", "Mouse Wheel Down"]

    def __init__(self, config, ui_updater):
        """初始化事件处理器

        Args:
            config: SwitcherConfig配置实例
            ui_updater: SwitcherUIUpdater实例
        """
        self.config = config
        self.ui_updater = ui_updater
        self.auto_close_start_time = 0
        self._auto_executed = False

    def start_auto_close_timer(self):
        """启动自动关闭定时器"""
        self.auto_close_start_time = time.time()
        print(f"⏰ 自动关闭定时器已启动，{self.config.auto_close_delay}秒后自动切换")

    def reset_auto_close_timer(self):
        """重置自动关闭定时器"""
        self.auto_close_start_time = time.time()

    def run_event_loop(
        self,
        window,
        tasks: List[Task],
        execute_callback: Callable[[int], bool],
        move_callback: Callable[[int], None]
    ) -> bool:
        """运行事件循环

        Args:
            window: FreeSimpleGUI窗口对象
            tasks: 任务列表
            execute_callback: 执行任务切换的回调函数，接收任务索引，返回是否成功
            move_callback: 移动选择的回调函数，接收方向参数

        Returns:
            是否成功执行了任务切换
        """
        try:
            while True:
                # 检查是否被自动执行中断
                if self._auto_executed:
                    return True

                # 计算剩余时间，检查超时
                result = self._check_timeout(window, tasks, execute_callback)
                if result is not None:
                    return result

                # 计算动态超时时间
                timeout = self._calculate_timeout()

                # 读取事件
                event, values = window.read(timeout=timeout)

                # 处理事件
                result = self._handle_event(event, window, tasks, execute_callback, move_callback)
                if result is not None:
                    return result

        except Exception as e:
            print(f"事件循环异常: {e}")
            return False

    def _check_timeout(
        self,
        window,
        tasks: List[Task],
        execute_callback: Callable[[int], bool]
    ) -> Optional[bool]:
        """检查是否超时

        Args:
            window: FreeSimpleGUI窗口对象
            tasks: 任务列表
            execute_callback: 执行任务切换的回调函数

        Returns:
            如果超时则返回执行结果，否则返回None
        """
        if self.auto_close_start_time <= 0:
            return None

        elapsed = time.time() - self.auto_close_start_time
        if elapsed >= self.config.auto_close_delay:
            # 时间到了，执行自动切换
            print("⏰ 自动关闭时间到，执行任务切换")
            self._auto_executed = True
            selected_index = self.ui_updater.selected_index
            return execute_callback(selected_index)
        else:
            # 更新倒计时显示
            remaining_time = self.config.auto_close_delay - elapsed
            self.ui_updater.update_countdown_display(window, remaining_time)
            return None

    def _calculate_timeout(self) -> int:
        """计算读取事件的超时时间

        Returns:
            超时时间（毫秒）
        """
        if self.auto_close_start_time > 0:
            elapsed = time.time() - self.auto_close_start_time
            remaining_time = self.config.auto_close_delay - elapsed
            # 动态调整超时时间，便于及时响应
            return min(100, int(remaining_time * 1000))
        return 100

    def _handle_event(
        self,
        event: Any,
        window,
        tasks: List[Task],
        execute_callback: Callable[[int], bool],
        move_callback: Callable[[int], None]
    ) -> Optional[bool]:
        """处理单个事件

        Args:
            event: 事件对象
            window: FreeSimpleGUI窗口对象
            tasks: 任务列表
            execute_callback: 执行任务切换的回调函数
            move_callback: 移动选择的回调函数

        Returns:
            如果事件导致对话框关闭则返回执行结果，否则返回None
        """
        # 超时事件 - 继续循环
        if event == sg.TIMEOUT_EVENT:
            return None

        # 窗口关闭或ESC键 - 取消
        if event == sg.WIN_CLOSED or event in self.EXIT_EVENTS:
            return False

        # 回车键 - 确认切换
        if event in self.CONFIRM_EVENTS:
            selected_index = self.ui_updater.selected_index
            return execute_callback(selected_index)

        # 上箭头或滚轮向上
        if event in self.UP_EVENTS or event in self.WHEEL_UP_EVENTS:
            try:
                new_index = self.ui_updater.move_selection(-1, len(tasks))
                self.ui_updater.update_selection_display(window, tasks)
                self.reset_auto_close_timer()
            except Exception as e:
                print(f"处理向上导航失败: {e}")

        # 下箭头或滚轮向下
        elif event in self.DOWN_EVENTS or event in self.WHEEL_DOWN_EVENTS:
            try:
                new_index = self.ui_updater.move_selection(1, len(tasks))
                self.ui_updater.update_selection_display(window, tasks)
                self.reset_auto_close_timer()
            except Exception as e:
                print(f"处理向下导航失败: {e}")

        # 数字键1-9快速选择
        elif self._is_number_key(event):
            return self._handle_number_key(event, tasks, execute_callback)

        # 双击事件 - 确认切换
        elif event and event.endswith("Double"):
            selected_index = self.ui_updater.selected_index
            return execute_callback(selected_index)

        return None

    def _is_number_key(self, event: Any) -> bool:
        """判断是否为数字键事件

        Args:
            event: 事件对象

        Returns:
            是否为数字键1-9
        """
        event_str = str(event)
        # 检查是否为单个数字字符
        if event_str in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            return True
        # 检查是否以数字开头
        if any(event_str.startswith(str(i)) for i in range(1, 10)):
            return True
        return False

    def _handle_number_key(
        self,
        event: Any,
        tasks: List[Task],
        execute_callback: Callable[[int], bool]
    ) -> bool:
        """处理数字键快速选择

        Args:
            event: 事件对象
            tasks: 任务列表
            execute_callback: 执行任务切换的回调函数

        Returns:
            是否成功执行了任务切换
        """
        try:
            event_str = str(event)
            # 提取数字
            if event_str in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                key_num = int(event_str) - 1
            else:
                key_num = int(event_str[0]) - 1

            if 0 <= key_num < len(tasks):
                # 数字键快速选择
                self.ui_updater.set_selected_index(key_num)
                return execute_callback(key_num)
        except:
            pass

        return False
