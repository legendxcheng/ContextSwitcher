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


class MainWindow:
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
        
        # 状态
        self.running = False
        self.refresh_timer = None
        self.last_refresh = 0
        self.refresh_interval = 2.0  # 秒
        
        # 表格选中状态保存
        self.preserved_selection = None
        
        # 状态消息清除时间
        self.status_clear_time = 0
        
        # 待机时间监控
        self.monitoring_timer = None
        self.last_monitoring = 0
        self.monitoring_interval = 60.0  # 监控间隔：60秒
        self.toast_manager = None  # 将在启动时初始化
        
        # 事件回调
        self.on_window_closed: Optional[Callable] = None
        
        # 拖拽状态跟踪
        self.window_was_dragged = False
        self.last_mouse_pos = None
        self.mouse_press_time = None
        
        # 设置现代化主题
        ModernUIConfig.setup_theme()
        
        # 创建窗口布局
        self.layout = self._create_layout()
        
        # 设置数据提供器的状态管理器引用（延迟设置）
        if hasattr(self.data_provider, 'set_task_status_manager'):
            self.data_provider.set_task_status_manager(self.task_status_manager)
        
        print("✓ 主窗口初始化完成")
    
    def _create_layout(self) -> List[List[Any]]:
        """创建现代化Widget布局"""
        colors = ModernUIConfig.COLORS
        fonts = ModernUIConfig.FONTS
        
        # 状态行 - 保持全局拖拽功能
        status_row = [
            sg.Text("", key="-STATUS-", font=fonts['body'], 
                   text_color=colors['text_secondary']),
            sg.Push(),
            sg.Text("●", key="-INDICATOR-", font=("Segoe UI", 12), 
                   text_color=colors['success'], tooltip="就绪"),
            sg.Button("✕", key="-CLOSE-", size=(1, 1), 
                     button_color=(colors['text'], colors['error']),
                     font=("Segoe UI", 10), border_width=0, tooltip="关闭")
        ]
        
        # 现代化任务表格 - 增加待机时间列
        table_headings = ["#", "任务", "窗口", "状态", "待机时间"]
        table_data = []
        
        # 创建精确控制宽度的表格，增加待机时间列
        compact_table = ModernUIConfig.create_modern_table(
            values=table_data,
            headings=table_headings,
            key="-TASK_TABLE-",
            num_rows=5,  # 从4行增加到5行
            col_widths=[2, 12, 3, 3, 6]  # 调整列宽：[编号, 任务名, 窗口数, 状态, 待机时间]
        )
        # 确保表格不会扩展
        compact_table.expand_x = False
        compact_table.expand_y = False
        
        table_row = [compact_table]
        
        # 正方形按钮行
        button_row = [
            ModernUIConfig.create_modern_button("＋", "-ADD_TASK-", "success", (2, 1), "添加任务"),
            ModernUIConfig.create_modern_button("✎", "-EDIT_TASK-", "primary", (2, 1), "编辑任务"),
            ModernUIConfig.create_modern_button("✕", "-DELETE_TASK-", "error", (2, 1), "删除任务"),
            sg.Text("", size=(1, 1)),  # 小分隔符
            ModernUIConfig.create_modern_button("↻", "-REFRESH-", "secondary", (2, 1), "刷新"),
            ModernUIConfig.create_modern_button("⚙", "-SETTINGS-", "warning", (2, 1), "设置")
        ]
        
        # 极简状态行
        bottom_row = [
            sg.Text("", key="-MAIN_STATUS-", font=fonts['small'], 
                   text_color=colors['text_secondary'], size=(8, 1)),
            sg.Text("C+A+空格", font=fonts['small'], 
                   text_color=colors['text_disabled'], size=(8, 1))
        ]
        
        # 现代化Widget布局 - 极简设计，使用Column控制整体宽度
        layout = [
            [sg.Column([
                status_row,
                table_row,
                button_row,
                bottom_row
            ], element_justification='left', 
               expand_x=False, expand_y=False,
               pad=(0, 0),  # 无额外padding
               background_color=colors['background'])]
        ]
        
        return layout
    
    def create_window(self) -> sg.Window:
        """创建现代化Widget窗口"""
        # 获取现代化Widget配置
        window_config = ModernUIConfig.get_widget_window_config()
        window_config['layout'] = self.layout
        
        # 窗口位置设置，不设置大小让其自适应
        if self.window_config.get("remember_position", True):
            window_config["location"] = (
                self.window_config.get("x", 200),
                self.window_config.get("y", 100)
            )
        # 不设置size参数，让窗口完全自适应内容大小
        
        # 创建窗口
        window = sg.Window(**window_config)
        
        # 保存表格组件引用
        self.table_widget = window["-TASK_TABLE-"]
        
        # 绑定双击事件
        self.table_widget.bind('<Double-Button-1>', ' Double')
        
        return window
    
    def show(self):
        """显示窗口"""
        if not self.window:
            self.window = self.create_window()
        
        self.running = True
        self._update_display()
        
        # 初始化Toast管理器
        self._initialize_toast_manager()
        
        # 更新数据提供器的状态管理器引用
        if hasattr(self.data_provider, 'set_task_status_manager'):
            self.data_provider.set_task_status_manager(self.task_status_manager)
        
        # 设置任务管理器回调
        self.task_manager.on_task_added = self._on_task_changed
        self.task_manager.on_task_removed = self._on_task_changed
        self.task_manager.on_task_updated = self._on_task_changed
        self.task_manager.on_task_switched = self._on_task_switched
        
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
        if self.window and self.window_config.get("remember_position", True):
            try:
                location = self.window.current_location()
                size = self.window.size
                
                if location and size:
                    self.config.update_window_position(
                        location[0], location[1], size[0], size[1]
                    )
            except Exception as e:
                print(f"保存窗口位置失败: {e}")
        
        if self.window:
            self.window.close()
            self.window = None
        
        # 触发关闭回调
        if self.on_window_closed:
            self.on_window_closed()
        
        print("✓ 主窗口已关闭")
    
    def run(self):
        """运行主事件循环"""
        if not self.window:
            self.show()
        
        print("开始GUI事件循环...")
        
        while self.running:
            try:
                # 检查拖拽状态
                self._check_drag_state()
                
                # 读取事件
                event, values = self.window.read(timeout=50)  # 更短的超时以便及时检测拖拽
                
                # 处理事件
                if event == sg.WIN_CLOSED:
                    break
                elif event == "-CLOSE-":
                    if not self.window_was_dragged:
                        break
                    else:
                        self.window_was_dragged = False  # 重置拖拽状态
                elif event == "-ADD_TASK-":
                    if not self.window_was_dragged:
                        self._handle_add_task()
                    else:
                        self.window_was_dragged = False  # 重置拖拽状态
                elif event == "-EDIT_TASK-":
                    if not self.window_was_dragged:
                        self._handle_edit_task(values)
                    else:
                        self.window_was_dragged = False  # 重置拖拽状态
                elif event == "-DELETE_TASK-":
                    if not self.window_was_dragged:
                        self._handle_delete_task(values)
                    else:
                        self.window_was_dragged = False  # 重置拖拽状态
                elif event == "-REFRESH-":
                    self._handle_refresh()
                elif event == "-SETTINGS-":
                    if not self.window_was_dragged:
                        self._handle_settings()
                    else:
                        self.window_was_dragged = False  # 重置拖拽状态
                elif event == "-TASK_TABLE-":
                    self._handle_table_selection(values)
                
                elif event == "-TASK_TABLE- Double":
                    self._handle_table_double_click(values)
                
                elif event == "-HOTKEY_TRIGGERED-":
                    # 处理来自热键线程的切换器触发事件
                    self._handle_hotkey_switcher_triggered()
                
                elif event == "-HOTKEY_ERROR-":
                    # 处理来自热键线程的错误事件
                    error_msg = values.get("-HOTKEY_ERROR-", "未知热键错误")
                    self._handle_hotkey_error(error_msg)
                
                # 定期刷新显示
                current_time = time.time()
                if current_time - self.last_refresh > self.refresh_interval:
                    self._update_display()
                    self.last_refresh = current_time
                
                # 定期监控待机时间
                if current_time - self.last_monitoring > self.monitoring_interval:
                    self._check_idle_tasks()
                    self.last_monitoring = current_time
                
                # 检查状态消息是否需要清除
                if self.status_clear_time > 0 and current_time >= self.status_clear_time:
                    try:
                        self.window["-MAIN_STATUS-"].update("就绪")
                        self.status_clear_time = 0  # 重置清除时间
                    except Exception as e:
                        print(f"清除状态失败: {e}")
                        self.status_clear_time = 0
                
            except Exception as e:
                print(f"GUI事件处理错误: {e}")
                continue
        
        print("GUI事件循环结束")
        self.close()
    
    def _update_display(self):
        """更新显示内容"""
        if not self.window or not self.running:
            return
        
        try:
            # 确定要使用的选中状态（优先使用保存的状态）
            selection_to_restore = self.preserved_selection
            
            # 如果没有保存的状态，尝试获取当前选中状态
            if selection_to_restore is None:
                try:
                    table_widget = self.window["-TASK_TABLE-"]
                    if hasattr(table_widget, 'SelectedRows') and table_widget.SelectedRows:
                        selection_to_restore = table_widget.SelectedRows[0]
                except Exception as e:
                    print(f"⚠️ 获取选中状态失败: {e}")
            
            # 更新任务表格和行颜色
            table_data = self.data_provider.get_table_data()
            row_colors = self.data_provider.get_row_colors()
            
            # 应用行颜色配置
            
            # 更新表格数据和行颜色
            self.window["-TASK_TABLE-"].update(values=table_data, row_colors=row_colors)
            
            # 恢复选中状态
            if selection_to_restore is not None and selection_to_restore < len(table_data):
                try:
                    self.window["-TASK_TABLE-"].update(select_rows=[selection_to_restore])
                except Exception as e:
                    print(f"⚠️ 恢复选中状态失败: {e}")
            
            # 更新状态
            task_count = len(self.task_manager.get_all_tasks())
            current_task = self.task_manager.get_current_task()
            
            if current_task:
                status = f"当前: {current_task.name}"
            else:
                status = f"{task_count} 个任务"
            
            self.window["-STATUS-"].update(status)
            self.window["-MAIN_STATUS-"].update("就绪")
            
        except Exception as e:
            print(f"更新显示失败: {e}")
    
    
    def _check_drag_state(self):
        """检查窗口是否被拖拽"""
        try:
            import win32api
            import win32gui
            import time
            
            # 获取当前鼠标位置
            current_mouse_pos = win32api.GetCursorPos()
            
            # 检查鼠标左键状态
            left_button_pressed = win32api.GetKeyState(0x01) < 0
            
            if left_button_pressed:
                # 鼠标按下，记录起始位置和时间
                if self.last_mouse_pos is None:
                    self.last_mouse_pos = current_mouse_pos
                    self.mouse_press_time = time.time()
                    self.window_was_dragged = False
                else:
                    # 检查鼠标是否移动了
                    dx = abs(current_mouse_pos[0] - self.last_mouse_pos[0])
                    dy = abs(current_mouse_pos[1] - self.last_mouse_pos[1])
                    
                    # 如果移动距离超过阈值，认为是拖拽
                    if dx > 3 or dy > 3:
                        self.window_was_dragged = True
            else:
                # 鼠标释放，重置状态（但保留拖拽标记一小段时间）
                if self.last_mouse_pos is not None:
                    self.last_mouse_pos = None
                    self.mouse_press_time = None
                    # 不立即重置 window_was_dragged，让事件处理器有时间检查
                    
        except Exception as e:
            print(f"检查拖拽状态失败: {e}")
    
    def _handle_add_task(self):
        """处理添加任务"""
        try:
            print("点击了添加任务按钮")  # 调试信息
            from gui.task_dialog import TaskDialog
            
            dialog = TaskDialog(self.window, self.task_manager)
            result = dialog.show_add_dialog()
            
            if result:
                self._update_display()
                self._set_status("任务添加成功", 3000)
                print("任务添加成功")
            else:
                print("任务添加取消")
            
        except Exception as e:
            print(f"添加任务失败: {e}")
            import traceback
            traceback.print_exc()
            self._set_status("添加任务失败", 3000)
    
    def _handle_edit_task(self, values: Dict[str, Any]):
        """处理编辑任务"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                sg.popup("请先选择要编辑的任务", title="提示")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                sg.popup("任务不存在", title="错误")
                return
            
            from gui.task_dialog import TaskDialog
            
            dialog = TaskDialog(self.window, self.task_manager)
            result = dialog.show_edit_dialog(task)
            
            if result:
                self._update_display()
                self._set_status("任务编辑成功", 3000)
            
        except Exception as e:
            print(f"编辑任务失败: {e}")
            self._set_status("编辑任务失败", 3000)
    
    def _handle_delete_task(self, values: Dict[str, Any]):
        """处理删除任务"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                sg.popup("请先选择要删除的任务", title="提示")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                sg.popup("任务不存在", title="错误")
                return
            
            # 确认删除
            result = sg.popup_yes_no(
                f"确定要删除任务 '{task.name}' 吗？\\n\\n此操作无法撤销。",
                title="确认删除"
            )
            
            if result == "Yes":
                if self.task_manager.remove_task(task.id):
                    self._update_display()
                    self._set_status("任务删除成功", 3000)
                else:
                    sg.popup("删除任务失败", title="错误")
            
        except Exception as e:
            print(f"删除任务失败: {e}")
            self._set_status("删除任务失败", 3000)
    
    def _handle_refresh(self):
        """处理刷新"""
        try:
            # 验证所有任务的窗口绑定
            invalid_windows = self.task_manager.validate_all_tasks()
            
            if invalid_windows:
                total_invalid = sum(len(windows) for windows in invalid_windows.values())
                self._set_status(f"发现 {total_invalid} 个失效窗口", 3000)
            
            self._update_display()
            self._set_status("刷新完成", 2000)
            
        except Exception as e:
            print(f"刷新失败: {e}")
            self._set_status("刷新失败", 3000)
    
    
    def _handle_settings(self):
        """处理设置"""
        try:
            from gui.settings_dialog import SettingsDialog
            
            dialog = SettingsDialog(self.window, self.task_manager)
            result = dialog.show_settings_dialog()
            
            if result:
                self._update_display()
                self._set_status("设置已保存", 3000)
                print("✓ 设置已保存并应用")
            
        except ImportError:
            sg.popup("设置功能开发中...", title="设置")
        except Exception as e:
            print(f"打开设置失败: {e}")
            sg.popup(f"打开设置失败: {e}", title="错误")
    
    def _handle_table_selection(self, values: Dict[str, Any]):
        """处理表格选择事件"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if selected_rows:
                task_index = selected_rows[0]
                # 保存选中状态
                self.preserved_selection = task_index
                
                task = self.task_manager.get_task_by_index(task_index)
                if task:
                    self._set_status(f"已选择: {task.name}", 2000)
            else:
                # 清除选中状态
                self.preserved_selection = None
            
        except Exception as e:
            print(f"处理表格选择失败: {e}")
    
    def _handle_table_double_click(self, values: Dict[str, Any]):
        """处理表格双击事件 - 切换到任务窗口"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if not selected_rows:
                print("⚠️ 双击事件：没有选中的任务")
                return
            
            task_index = selected_rows[0]
            task = self.task_manager.get_task_by_index(task_index)
            
            if not task:
                print(f"⚠️ 找不到索引为 {task_index} 的任务")
                return
            
            print(f"🖱️ 双击任务: {task.name}")
            self._set_status(f"正在切换到: {task.name}", 1000)
            
            # 使用任务管理器切换到该任务
            success = self.task_manager.switch_to_task(task_index)
            
            if success:
                print(f"✅ 成功切换到任务: {task.name}")
                self._set_status(f"已切换到: {task.name}", 3000)
            else:
                print(f"❌ 切换任务失败: {task.name}")
                self._set_status(f"切换失败: {task.name}", 3000)
            
        except Exception as e:
            print(f"处理表格双击失败: {e}")
            self._set_status("切换任务失败", 2000)
    
    def _set_status(self, message: str, duration_ms: int = 0):
        """设置状态消息
        
        Args:
            message: 状态消息
            duration_ms: 显示时长（毫秒），0表示永久显示
        """
        if not self.window:
            return
        
        try:
            self.window["-MAIN_STATUS-"].update(message)
            
            if duration_ms > 0:
                # 记录状态清除时间，让主事件循环处理
                self.status_clear_time = time.time() + (duration_ms / 1000.0)
                
        except Exception as e:
            print(f"设置状态失败: {e}")
    
    def _on_task_changed(self, task: Task):
        """任务变化回调"""
        if self.running:
            # 任务发生变化时，清除保存的选中状态以避免索引错位
            self.preserved_selection = None
            self._update_display()
    
    def _on_task_switched(self, task: Task, index: int):
        """任务切换回调"""
        if self.running:
            self._update_display()
            self._set_status(f"已切换到: {task.name}", 3000)
    
    def _initialize_toast_manager(self):
        """初始化Toast管理器"""
        try:
            from utils.toast_manager import get_toast_manager
            
            self.toast_manager = get_toast_manager()
            
            # 从配置读取设置
            monitoring_config = self.config.get_monitoring_config()
            cooldown_minutes = monitoring_config.get('toast_cooldown_minutes', 30)
            self.toast_manager.set_cooldown_minutes(cooldown_minutes)
            
            # 设置点击回调
            self.toast_manager.on_toast_clicked = self._on_toast_clicked
            
            print("✓ Toast管理器初始化完成")
            
        except Exception as e:
            print(f"初始化Toast管理器失败: {e}")
            self.toast_manager = None
    
    def _check_idle_tasks(self):
        """检查并处理待机时间超时的任务"""
        try:
            monitoring_config = self.config.get_monitoring_config()
            
            # 检查是否启用通知
            if not monitoring_config.get('toast_notifications_enabled', True):
                return
            
            if not self.toast_manager:
                return
            
            # 获取超时任务
            from utils.time_helper import get_overdue_tasks
            current_task_index = self.task_manager.current_task_index
            overdue_tasks = get_overdue_tasks(self.task_manager.get_all_tasks(), current_task_index)
            
            if not overdue_tasks:
                return
            
            # 发送通知
            if len(overdue_tasks) == 1:
                # 单个任务通知
                task_info = overdue_tasks[0]
                self.toast_manager.send_idle_task_notification(
                    task_info['task'].name,
                    task_info['task'].id,
                    task_info['display_time']
                )
            else:
                # 多个任务汇总通知
                self.toast_manager.send_multiple_tasks_notification(overdue_tasks)
            
        except Exception as e:
            print(f"检查待机任务失败: {e}")
    
    def _on_toast_clicked(self, task_id: str):
        """Toast通知点击回调"""
        try:
            # 查找对应的任务
            task = self.task_manager.get_task_by_id(task_id)
            if not task:
                print(f"找不到任务: {task_id}")
                return
            
            # 获取任务索引
            all_tasks = self.task_manager.get_all_tasks()
            for i, t in enumerate(all_tasks):
                if t.id == task_id:
                    # 切换到该任务
                    success = self.task_manager.switch_to_task(i)
                    if success:
                        self._set_status(f"通过通知切换到: {task.name}", 3000)
                        print(f"✓ 通过Toast通知切换到任务: {task.name}")
                    else:
                        print(f"✗ 切换到任务失败: {task.name}")
                    break
            
        except Exception as e:
            print(f"处理Toast点击失败: {e}")
    
    def _handle_hotkey_switcher_triggered(self):
        """处理热键线程发送的切换器触发事件（线程安全）"""
        try:
            # 获取主程序实例，通过回调来显示任务切换器
            # 这样避免直接在主窗口中操作任务切换器
            if hasattr(self, '_app_instance') and self._app_instance:
                # 如果有应用实例的引用，调用其方法
                self._app_instance.show_task_switcher()
            else:
                # 备用方案：直接调用全局回调（如果设置了）
                if hasattr(self, 'on_hotkey_switcher_triggered') and self.on_hotkey_switcher_triggered:
                    self.on_hotkey_switcher_triggered()
                else:
                    print("⚠️ 未找到任务切换器回调方法")
            
        except Exception as e:
            print(f"处理热键切换器触发失败: {e}")
    
    def _handle_hotkey_error(self, error_msg: str):
        """处理热键线程发送的错误事件（线程安全）"""
        try:
            print(f"⚠️ 热键错误: {error_msg}")
            # 在主线程中安全地显示错误状态
            self._set_status(f"热键错误: {error_msg}", 5000)
            
        except Exception as e:
            print(f"处理热键错误失败: {e}")