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


class MainWindow:
    """主窗口类"""
    
    def __init__(self, task_manager: TaskManager):
        """初始化主窗口
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.config = get_config()
        
        # 窗口配置
        self.window_config = self.config.get_window_config()
        self.app_name = "ContextSwitcher"
        self.version = "v1.0.0"
        
        # GUI组件
        self.window: Optional[sg.Window] = None
        self.table_widget = None
        
        # 状态
        self.running = False
        self.refresh_timer = None
        self.last_refresh = 0
        self.refresh_interval = 2.0  # 秒
        
        # 事件回调
        self.on_window_closed: Optional[Callable] = None
        
        # 设置主题
        sg.theme(self.config.get('app.theme', 'DefaultNoMoreNagging'))
        
        # 创建窗口布局
        self.layout = self._create_layout()
        
        print("✓ 主窗口初始化完成")
    
    def _create_layout(self) -> List[List[Any]]:
        """创建紧凑的窗口布局"""
        # 精简标题行 - 更小的字体，紧凑布局
        title_row = [
            sg.Text(f"{self.app_name}", 
                   font=("Arial", 10, "bold"),
                   text_color="#2E86AB"),
            sg.Push(),
            sg.Text("", key="-STATUS-", font=("Arial", 8), 
                   text_color="#666666")
        ]
        
        # 紧凑的任务表格 - 减少列数，更小字体
        table_headings = ["#", "任务", "窗口", "时间"]
        table_data = []
        
        table_row = [
            sg.Table(
                values=table_data,
                headings=table_headings,
                key="-TASK_TABLE-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[3, 25, 20, 12],  # 减少列数和宽度
                justification="left",
                alternating_row_color="#F8F8F8",
                selected_row_colors="#FFFFFF on #2E86AB",
                header_text_color="#FFFFFF",
                header_background_color="#2E86AB",
                header_font=("Arial", 9, "bold"),
                font=("Arial", 8),  # 更小的字体
                num_rows=3,  # 只显示3行
                expand_x=True,
                expand_y=False,  # 不允许垂直扩展
                row_height=18,  # 设置固定行高
                max_col_width=25  # 限制列宽
            )
        ]
        
        # 紧凑的按钮行 - 更小的按钮，简化按钮
        button_row = [
            sg.Button("+ 添加", key="-ADD_TASK-", 
                     size=(8, 1), button_color=("#FFFFFF", "#28A745"),
                     font=("Arial", 8)),
            sg.Button("编辑", key="-EDIT_TASK-", 
                     size=(6, 1), button_color=("#FFFFFF", "#007BFF"),
                     font=("Arial", 8)),
            sg.Button("删除", key="-DELETE_TASK-", 
                     size=(6, 1), button_color=("#FFFFFF", "#DC3545"),
                     font=("Arial", 8)),
            sg.Push(),
            sg.Button("⟳", key="-REFRESH-", size=(3, 1), 
                     font=("Arial", 10), tooltip="刷新")
        ]
        
        # 极简状态行
        status_row = [
            sg.Text("", key="-MAIN_STATUS-", font=("Arial", 8), 
                   text_color="#888888"),
            sg.Push(),
            sg.Text("Ctrl+Alt+1-9", font=("Arial", 7), 
                   text_color="#AAAAAA")
        ]
        
        # 紧凑布局 - 减少分隔线和边距
        layout = [
            title_row,
            table_row,
            button_row,
            status_row
        ]
        
        return layout
    
    def create_window(self) -> sg.Window:
        """创建窗口"""
        # 窗口配置
        window_config = {
            "title": self.app_name,
            "layout": self.layout,
            "keep_on_top": self.window_config.get("always_on_top", True),
            "finalize": True,
            "resizable": False,  # 禁用调整大小
            "grab_anywhere": True,
            "icon": None,  # TODO: 添加应用图标
            "margins": (3, 3),  # 更小的边距
            "element_padding": (2, 1),  # 更小的元素间距
            "auto_size_text": False,
            "auto_size_buttons": False
        }
        
        # 窗口位置 - 让FreeSimpleGUI自动调整大小
        if self.window_config.get("remember_position", True):
            window_config.update({
                "location": (
                    self.window_config.get("x", 100),
                    self.window_config.get("y", 100)
                )
            })
        
        # 不设置固定size，让窗口自适应内容大小
        
        # 创建窗口
        window = sg.Window(**window_config)
        
        # 保存表格组件引用
        self.table_widget = window["-TASK_TABLE-"]
        
        return window
    
    def show(self):
        """显示窗口"""
        if not self.window:
            self.window = self.create_window()
        
        self.running = True
        self._update_display()
        
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
                # 读取事件
                event, values = self.window.read(timeout=1000)
                
                # 处理事件
                if event == sg.WIN_CLOSED:
                    break
                elif event == "-ADD_TASK-":
                    self._handle_add_task()
                elif event == "-EDIT_TASK-":
                    self._handle_edit_task(values)
                elif event == "-DELETE_TASK-":
                    self._handle_delete_task(values)
                elif event == "-REFRESH-":
                    self._handle_refresh()
                elif event == "-SETTINGS-":
                    self._handle_settings()
                elif event == "-TASK_TABLE-":
                    self._handle_table_selection(values)
                
                # 定期刷新显示
                current_time = time.time()
                if current_time - self.last_refresh > self.refresh_interval:
                    self._update_display()
                    self.last_refresh = current_time
                
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
            # 更新任务表格
            table_data = self._get_table_data()
            self.window["-TASK_TABLE-"].update(values=table_data)
            
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
    
    def _get_table_data(self) -> List[List[str]]:
        """获取表格数据"""
        table_data = []
        tasks = self.task_manager.get_all_tasks()
        current_index = self.task_manager.current_task_index
        
        for i, task in enumerate(tasks):
            # 任务编号（带当前任务标记）
            task_num = f"►{i+1}" if i == current_index else str(i+1)
            
            # 任务名称 - 限制长度
            task_name = task.name
            if len(task_name) > 20:
                task_name = task_name[:17] + "..."
            
            # 绑定窗口数量和状态 - 紧凑显示
            valid_windows = sum(1 for w in task.bound_windows if w.is_valid)
            total_windows = len(task.bound_windows)
            
            if total_windows == 0:
                windows_info = "无"
            elif valid_windows == total_windows:
                windows_info = f"{total_windows}个"
            else:
                windows_info = f"{valid_windows}/{total_windows}"
            
            # 最后访问时间 - 只显示时分
            try:
                last_time = datetime.fromisoformat(task.last_accessed)
                time_str = last_time.strftime("%H:%M")
            except:
                time_str = "--:--"
            
            # 新的4列格式：编号、任务名、窗口数、时间
            table_data.append([task_num, task_name, windows_info, time_str])
        
        return table_data
    
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
            # TODO: 实现设置对话框
            sg.popup("设置功能开发中...", title="设置")
            
        except Exception as e:
            print(f"打开设置失败: {e}")
    
    def _handle_table_selection(self, values: Dict[str, Any]):
        """处理表格选择事件"""
        try:
            selected_rows = values.get("-TASK_TABLE-", [])
            if selected_rows:
                task_index = selected_rows[0]
                task = self.task_manager.get_task_by_index(task_index)
                if task:
                    self._set_status(f"已选择: {task.name}", 2000)
            
        except Exception as e:
            print(f"处理表格选择失败: {e}")
    
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
                # 设置定时器清除状态
                def clear_status():
                    if self.window and self.running:
                        self.window["-MAIN_STATUS-"].update("就绪")
                
                timer = threading.Timer(duration_ms / 1000.0, clear_status)
                timer.start()
                
        except Exception as e:
            print(f"设置状态失败: {e}")
    
    def _on_task_changed(self, task: Task):
        """任务变化回调"""
        if self.running:
            self._update_display()
    
    def _on_task_switched(self, task: Task, index: int):
        """任务切换回调"""
        if self.running:
            self._update_display()
            self._set_status(f"已切换到: {task.name}", 3000)