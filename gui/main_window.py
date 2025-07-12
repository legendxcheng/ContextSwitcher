"""
主窗口GUI模块

负责应用程序的主界面:
- Always-on-Top主窗口
- 任务列表显示
- 添加/编辑/删除按钮
- 事件处理
- 窗口状态管理
"""

import time
import threading
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    print("运行: pip install FreeSimpleGUI")
    raise

from core.task_manager import TaskManager, Task, TaskStatus
from utils.config import get_config
from gui.modern_config import ModernUIConfig
from gui.table_data_provider import TableDataProvider, IDataProvider
from gui.event_controller import EventController, IWindowActions
from gui.window_state_manager import WindowStateManager, IWindowProvider
from gui.notification_controller import NotificationController, INotificationProvider
from gui.ui_layout_manager import UILayoutManager, ILayoutProvider
from gui.action_dispatcher import ActionDispatcher, IActionProvider


class MainWindow(IWindowActions, IWindowProvider, INotificationProvider, ILayoutProvider, IActionProvider):
    """主窗口类"""
    
    def __init__(self, task_manager: TaskManager):
        """初始化主窗口
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.config = get_config()
        self.smart_rebind_manager = None  # 将在主程序中设置
        self.task_status_manager = None  # 将在主程序中设置
        
        # 窗口配置
        self.window_config = self.config.get_window_config()
        self.app_name = "ContextSwitcher"
        self.version = "v1.0.0"
        
        # GUI组件
        self.window: Optional[sg.Window] = None
        self.table_widget = None
        
        # 数据提供器
        self.data_provider: IDataProvider = TableDataProvider(task_manager)
        
        # 事件控制器
        self.event_controller: EventController = None  # 将在show方法中初始化
        
        # 窗口状态管理器
        self.window_state_manager: WindowStateManager = WindowStateManager(self)
        
        # 通知控制器
        self.notification_controller: NotificationController = NotificationController(self)
        
        # UI布局管理器
        self.ui_layout_manager: UILayoutManager = UILayoutManager(self)
        
        # 业务动作调度器
        self.action_dispatcher: ActionDispatcher = ActionDispatcher(self)
        
        # 状态
        self.running = False
        self.refresh_timer = None
        self.last_refresh = 0
        self.refresh_interval = 2.0  # 秒
        
        
        
        # 事件回调
        self.on_window_closed: Optional[Callable] = None
        
        
        # 设置现代化主题
        ModernUIConfig.setup_theme()
        
        # 创建窗口布局
        self.layout = self.ui_layout_manager.create_layout()
        
        # 设置数据提供器的状态管理器引用（延迟设置）
        if hasattr(self.data_provider, 'set_task_status_manager'):
            self.data_provider.set_task_status_manager(self.task_status_manager)
        
        print("✓ 主窗口初始化完成")
    
    def create_window(self) -> sg.Window:
        """创建现代化Widget窗口"""
        # 使用UI布局管理器创建窗口
        window = self.ui_layout_manager.create_window(self.layout)
        
        # 设置窗口事件绑定
        window = self.ui_layout_manager.setup_window_events(window)
        
        # 保存表格组件引用
        self.table_widget = self.ui_layout_manager.get_table_widget(window)
        
        return window
    
    def show(self):
        """显示窗口"""
        if not self.window:
            self.window = self.create_window()
        
        self.running = True
        self.action_dispatcher.update_display()
        
        # 初始化通知控制器
        self.notification_controller.initialize()
        
        # 更新数据提供器的状态管理器引用
        if hasattr(self.data_provider, 'set_task_status_manager'):
            self.data_provider.set_task_status_manager(self.task_status_manager)
        
        # 初始化事件控制器
        self.event_controller = EventController(self.task_manager, self)
        
        # 设置任务管理器回调（通过ActionDispatcher）
        self.action_dispatcher.setup_task_manager_callbacks()
        
        print("✓ 主窗口已显示")
    
    def hide(self):
        """隐藏窗口"""
        if self.window:
            self.window.hide()
    
    def close(self):
        """关闭窗口"""
        self.running = False
        
        if self.refresh_timer:
            self.refresh_timer.cancel()
        
        # 保存窗口位置
        if self.window:
            self.window_state_manager.save_position()
        
        if self.window:
            self.window.close()
            self.window = None
        
        # 触发关闭回调
        if self.on_window_closed:
            self.on_window_closed()
        
        print("✓ 主窗口已关闭")
    
    # IWindowActions接口实现
    def update_display(self):
        """更新显示 - IWindowActions接口实现"""
        self.action_dispatcher.update_display()
    
    def set_status(self, message: str, duration_ms: int = 0):
        """设置状态消息 - IWindowActions接口实现"""
        self.action_dispatcher.set_status(message, duration_ms)
    
    def get_window(self):
        """获取窗口对象 - IWindowActions和IWindowProvider接口实现"""
        return self.window
    
    def get_config(self):
        """获取配置对象 - IWindowProvider和INotificationProvider接口实现"""
        return self.config
    
    def get_task_manager(self):
        """获取任务管理器 - INotificationProvider接口实现"""
        return self.task_manager
    
    def get_window_state_manager(self):
        """获取窗口状态管理器 - ILayoutProvider接口实现"""
        return self.window_state_manager
    
    def get_data_provider(self):
        """获取数据提供器 - IActionProvider接口实现"""
        return self.data_provider
    
    def get_event_controller(self):
        """获取事件控制器 - IActionProvider接口实现"""
        return self.event_controller
    
    def is_running(self) -> bool:
        """检查是否正在运行 - IActionProvider接口实现"""
        return self.running
    
    def run(self):
        """运行主事件循环"""
        if not self.window:
            self.show()
        
        print("开始GUI事件循环...")
        
        while self.running:
            try:
                # 检查拖拽状态
                was_dragged = self.window_state_manager.detect_drag()
                
                # 读取事件
                event, values = self.window.read(timeout=50)  # 更短的超时以便及时检测拖拽
                
                # 处理事件
                if event == sg.WIN_CLOSED:
                    break
                elif event == "-CLOSE-":
                    if not was_dragged:
                        break
                    else:
                        self.window_state_manager.reset_drag_state()  # 重置拖拽状态
                else:
                    # 通过事件控制器处理所有其他事件
                    if self.event_controller:
                        # 同步拖拽状态到事件控制器
                        self.event_controller.set_drag_state(was_dragged)
                        
                        # 处理事件
                        handled = self.event_controller.handle_event(event, values)
                        
                        # 如果事件被处理，重置拖拽状态
                        if handled and was_dragged:
                            self.window_state_manager.reset_drag_state()
                
                # 定期刷新显示
                current_time = time.time()
                if current_time - self.last_refresh > self.refresh_interval:
                    self.action_dispatcher.update_display()
                    self.last_refresh = current_time
                
                # 定期监控待机时间
                if self.notification_controller.should_check_idle_tasks(current_time):
                    self.notification_controller.check_idle_tasks()
                
                # 检查状态消息是否需要清除
                self.action_dispatcher.check_status_clear(current_time)
                
            except Exception as e:
                print(f"GUI事件处理错误: {e}")
                continue
        
        print("GUI事件循环结束")
        self.close()
    
    
