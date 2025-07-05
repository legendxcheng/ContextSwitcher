"""
任务对话框模块

负责任务的添加和编辑界面:
- 任务信息输入
- 窗口选择器集成
- 数据验证
- 用户交互
"""

from typing import List, Dict, Any, Optional, Tuple

try:
    import FreeSimpleGUI as sg
    # 设置现代化主题
    sg.theme('DarkGrey13')
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise

from core.task_manager import TaskManager, Task, TaskStatus
from core.window_manager import WindowInfo
from gui.window_selector import WindowSelector


class TaskDialog:
    """任务对话框类"""
    
    def __init__(self, parent_window: sg.Window, task_manager: TaskManager):
        """初始化任务对话框
        
        Args:
            parent_window: 父窗口
            task_manager: 任务管理器
        """
        self.parent_window = parent_window
        self.task_manager = task_manager
        self.window_selector = WindowSelector(task_manager.window_manager)
        
        # 对话框窗口
        self.dialog_window: Optional[sg.Window] = None
        
        # 表单数据
        self.task_name = ""
        self.task_description = ""
        self.task_status = TaskStatus.PENDING
        self.selected_windows: List[WindowInfo] = []
    
    def show_add_dialog(self) -> bool:
        """显示添加任务对话框
        
        Returns:
            是否成功添加任务
        """
        # 重置表单数据
        self.task_name = ""
        self.task_description = ""
        self.task_status = TaskStatus.PENDING
        self.selected_windows = []
        
        # 创建对话框
        layout = self._create_add_layout()
        self.dialog_window = sg.Window(
            "添加任务",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=True,
            size=(620, 580),  # 适配现代化界面
            location=(200, 150),
            no_titlebar=False,  # 对话框保留标题栏
            alpha_channel=0.98,  # 轻微透明
            background_color="#202020",
            margins=(12, 10),
            element_padding=(4, 3)
        )
        
        # 初始化窗口列表数据
        self._refresh_window_list()
        
        # 运行对话框
        result = self._run_dialog()
        
        if result:
            # 创建任务
            window_hwnds = [w.hwnd for w in self.selected_windows]
            task = self.task_manager.add_task(
                name=self.task_name,
                description=self.task_description,
                window_hwnds=window_hwnds
            )
            
            if task:
                # 设置状态
                self.task_manager.edit_task(task.id, status=self.task_status)
                return True
        
        return False
    
    def show_edit_dialog(self, task: Task) -> bool:
        """显示编辑任务对话框
        
        Args:
            task: 要编辑的任务
            
        Returns:
            是否成功编辑任务
        """
        # 加载现有数据
        self.task_name = task.name
        self.task_description = task.description
        self.task_status = task.status
        
        # 加载绑定的窗口
        self.selected_windows = []
        for bound_window in task.bound_windows:
            if bound_window.is_valid:
                window_info = self.task_manager.window_manager.get_window_info(bound_window.hwnd)
                if window_info:
                    self.selected_windows.append(window_info)
        
        # 创建对话框
        layout = self._create_edit_layout()
        self.dialog_window = sg.Window(
            f"编辑任务 - {task.name}",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=True,
            size=(620, 580),  # 适配现代化界面
            location=(200, 150),
            no_titlebar=False,  # 对话框保留标题栏
            alpha_channel=0.98,  # 轻微透明
            background_color="#202020",
            margins=(12, 10),
            element_padding=(4, 3)
        )
        
        # 初始化窗口列表数据
        self._refresh_window_list()
        
        # 运行对话框
        result = self._run_dialog()
        
        if result:
            # 更新任务
            window_hwnds = [w.hwnd for w in self.selected_windows]
            success = self.task_manager.edit_task(
                task.id,
                name=self.task_name,
                description=self.task_description,
                status=self.task_status,
                window_hwnds=window_hwnds
            )
            return success
        
        return False
    
    def _create_add_layout(self) -> List[List[Any]]:
        """创建添加任务的布局"""
        return self._create_base_layout("添加任务")
    
    def _create_edit_layout(self) -> List[List[Any]]:
        """创建编辑任务的布局"""
        return self._create_base_layout("编辑任务")
    
    def _create_base_layout(self, title: str) -> List[List[Any]]:
        """创建基础布局"""
        # 任务信息区域
        info_frame = [
            [sg.Text("任务名称:", size=(10, 1)), 
             sg.Input(self.task_name, key="-TASK_NAME-", size=(40, 1))],
            [sg.Text("任务描述:", size=(10, 1)), 
             sg.Multiline(self.task_description, key="-TASK_DESC-", 
                         size=(40, 3), enable_events=True)],
            [sg.Text("任务状态:", size=(10, 1)),
             sg.Combo(["待处理", "活跃", "被阻塞", "已完成"], 
                     default_value=self._status_to_text(self.task_status),
                     key="-TASK_STATUS-", readonly=True, size=(15, 1))]
        ]
        
        # 窗口选择区域
        window_frame = self._create_window_selection_frame()
        
        # 现代化按钮区域
        button_row = [
            sg.Push(),
            sg.Button("确定", key="-OK-", size=(10, 1), 
                     button_color=("#FFFFFF", "#107C10"), 
                     font=("Segoe UI", 10), border_width=0),
            sg.Button("取消", key="-CANCEL-", size=(10, 1),
                     button_color=("#FFFFFF", "#404040"), 
                     font=("Segoe UI", 10), border_width=0),
            sg.Push()
        ]
        
        # 完整布局
        layout = [
            [sg.Text(title, font=("Arial", 12, "bold"))],  # 更小的标题字体
            [sg.Frame("任务信息", info_frame, expand_x=True, 
                     element_justification="left")],
            [sg.Frame("绑定窗口", window_frame, expand_x=True, expand_y=False)],  # 不允许垂直扩展
            [sg.Text("")],  # 添加一行空白分隔
            button_row  # 确保按钮在最后
        ]
        
        return layout
    
    def _create_window_selection_frame(self) -> List[List[Any]]:
        """创建窗口选择框架"""
        # 初始化空的窗口列表数据，稍后通过_refresh_window_list填充
        window_data = []
        
        # 窗口选择表格
        table_headings = ["选择", "窗口标题", "进程", "句柄"]
        
        window_frame = [
            [sg.Text("选择要绑定到此任务的窗口:")],
            [sg.Text("操作: 1.点击选中窗口行  2.点击'添加选择'按钮将其加入任务", font=("Arial", 9), text_color="#666666")],
            [sg.Button("刷新窗口列表", key="-REFRESH_WINDOWS-", size=(12, 1),
                      button_color=("#FFFFFF", "#0078D4"), font=("Segoe UI", 9), border_width=0),
             sg.Button("添加选择", key="-ADD_WINDOW-", size=(10, 1), 
                      button_color=("#FFFFFF", "#107C10"), font=("Segoe UI", 9), border_width=0)],
            [sg.Table(
                values=window_data,
                headings=table_headings,
                key="-WINDOW_TABLE-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[6, 30, 15, 12],
                justification="left",
                alternating_row_color="#F8F9FA",
                selected_row_colors="#FFFFFF on #007BFF",
                header_background_color="#007BFF",
                header_text_color="#FFFFFF",
                font=("Arial", 9),
                num_rows=4,  # 进一步减少行数
                expand_x=True,
                expand_y=False  # 不允许垂直扩展
            )],
            [sg.Text("已选择窗口:", font=("Arial", 10, "bold"))],
            [sg.Listbox(
                values=[f"{w.title} ({w.process_name})" for w in self.selected_windows],
                key="-SELECTED_WINDOWS-",
                size=(50, 2),  # 进一步减少高度
                enable_events=True,
                expand_x=True
            )],
            [sg.Button("移除选择", key="-REMOVE_WINDOW-", size=(10, 1),
                      button_color=("#FFFFFF", "#D13438"), font=("Segoe UI", 9), border_width=0)]
        ]
        
        return window_frame
    
    def _run_dialog(self) -> bool:
        """运行对话框事件循环
        
        Returns:
            用户是否确认操作
        """
        if not self.dialog_window:
            return False
        
        try:
            while True:
                event, values = self.dialog_window.read()
                
                if event in (sg.WIN_CLOSED, "-CANCEL-"):
                    return False
                
                elif event == "-OK-":
                    if self._validate_form(values):
                        self._save_form_data(values)
                        return True
                
                elif event == "-REFRESH_WINDOWS-":
                    self._refresh_window_list()
                
                elif event == "-WINDOW_TABLE-":
                    # 只响应表格选择，不自动添加/移除窗口
                    self._handle_table_click(values)
                
                elif event == "-ADD_WINDOW-":
                    # 新增的添加按钮
                    self._handle_add_window(values)
                
                elif event == "-REMOVE_WINDOW-":
                    self._handle_remove_window(values)
        
        finally:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None
    
    def _validate_form(self, values: Dict[str, Any]) -> bool:
        """验证表单数据"""
        # 检查任务名称
        task_name = values["-TASK_NAME-"].strip()
        if not task_name:
            sg.popup("请输入任务名称", title="验证错误")
            return False
        
        # 检查名称重复（编辑时跳过当前任务）
        existing_tasks = self.task_manager.get_all_tasks()
        for task in existing_tasks:
            if task.name == task_name:
                # 如果是编辑模式且是同一个任务，则允许
                if hasattr(self, '_editing_task_id') and task.id == self._editing_task_id:
                    continue
                sg.popup(f"任务名称 '{task_name}' 已存在", title="验证错误")
                return False
        
        # 检查是否选择了窗口
        if not self.selected_windows:
            result = sg.popup_yes_no(
                "没有选择任何窗口，确定要创建此任务吗？",
                title="确认"
            )
            if result != "Yes":
                return False
        
        return True
    
    def _save_form_data(self, values: Dict[str, Any]):
        """保存表单数据"""
        self.task_name = values["-TASK_NAME-"].strip()
        self.task_description = values["-TASK_DESC-"].strip()
        
        # 转换状态
        status_text = values["-TASK_STATUS-"]
        self.task_status = self._text_to_status(status_text)
    
    def _refresh_window_list(self):
        """刷新窗口列表"""
        if not self.dialog_window:
            return
        
        try:
            # 强制刷新窗口缓存
            self.task_manager.window_manager.invalidate_cache()
            
            # 获取最新窗口列表
            available_windows = self.task_manager.window_manager.enumerate_windows()
            
            # 更新表格数据
            window_data = []
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            
            for window in available_windows:
                is_selected = window.hwnd in selected_hwnds
                window_data.append([
                    "✓" if is_selected else "",
                    window.title,
                    window.process_name,
                    str(window.hwnd)
                ])
            
            self.dialog_window["-WINDOW_TABLE-"].update(values=window_data)
            
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")
            sg.popup(f"刷新失败: {e}", title="错误")
    
    def _handle_table_click(self, values: Dict[str, Any]):
        """处理表格点击事件（仅选择，不添加/移除）"""
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                return
            
            row_index = selected_rows[0]
            # 使用Values属性获取完整的表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values
            
            print(f"调试信息 - row_index: {row_index}, table_data类型: {type(table_data)}, len(table_data): {len(table_data) if table_data else 0}")
            
            if not table_data or row_index >= len(table_data):
                print(f"表格数据异常: row_index={row_index}, len(table_data)={len(table_data) if table_data else 0}")
                return
            
            # 显示选中窗口的信息
            if isinstance(table_data[row_index], list) and len(table_data[row_index]) > 1:
                window_title = table_data[row_index][1]
                print(f"选中窗口: {window_title}")
            else:
                print(f"表格行数据格式异常: {table_data[row_index]}")
            
        except Exception as e:
            print(f"处理表格点击失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_window_selection(self, values: Dict[str, Any]):
        """处理窗口选择（已弃用，保留兼容性）"""
        # 这个方法已经不再使用，保留是为了兼容性
        self._handle_table_click(values)
    
    def _handle_add_window(self, values: Dict[str, Any]):
        """处理添加窗口按钮"""
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                sg.popup("请先选择一个窗口", title="提示")
                return
            
            row_index = selected_rows[0]
            # 使用Values属性获取完整的表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values
            
            print(f"添加窗口调试 - row_index: {row_index}, table_data类型: {type(table_data)}, len(table_data): {len(table_data) if table_data else 0}")
            
            if not table_data or row_index >= len(table_data):
                print(f"表格数据异常: row_index={row_index}, len(table_data)={len(table_data) if table_data else 0}")
                sg.popup("表格数据异常", title="错误")
                return
            
            # 检查行数据格式
            if not isinstance(table_data[row_index], list) or len(table_data[row_index]) < 4:
                print(f"表格行数据格式异常: {table_data[row_index]}")
                sg.popup("表格行数据格式异常", title="错误")
                return
            
            # 获取窗口句柄
            hwnd_str = table_data[row_index][3]
            hwnd = int(hwnd_str)
            
            # 检查是否已经选择
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            if hwnd in selected_hwnds:
                sg.popup("此窗口已经选择", title="提示")
                return
            
            # 获取窗口信息并添加
            window_info = self.task_manager.window_manager.get_window_info(hwnd)
            if window_info:
                self.selected_windows.append(window_info)
                self._update_selected_windows_display()
                self._refresh_window_list()
                print(f"已添加窗口: {window_info.title}")
                # 显示成功提示
                sg.popup_timed(f"已添加窗口: {window_info.title}", auto_close_duration=2, title="成功")
            else:
                sg.popup("窗口信息获取失败", title="错误")
                
        except Exception as e:
            print(f"添加窗口失败: {e}")
            sg.popup(f"添加失败: {e}", title="错误")
    
    def _handle_remove_window(self, values: Dict[str, Any]):
        """处理移除窗口"""
        try:
            selected_items = values.get("-SELECTED_WINDOWS-", [])
            if not selected_items:
                sg.popup("请先选择要移除的窗口", title="提示")
                return
            
            selected_text = selected_items[0]
            
            # 根据显示文本找到对应的窗口
            removed_window = None
            for i, window in enumerate(self.selected_windows):
                display_text = f"{window.title} ({window.process_name})"
                if display_text == selected_text:
                    removed_window = self.selected_windows.pop(i)
                    break
            
            if removed_window:
                # 更新显示
                self._update_selected_windows_display()
                self._refresh_window_list()
                print(f"已移除窗口: {removed_window.title}")
                sg.popup_timed(f"已移除窗口: {removed_window.title}", auto_close_duration=2, title="成功")
            else:
                sg.popup("未找到要移除的窗口", title="错误")
            
        except Exception as e:
            print(f"移除窗口失败: {e}")
    
    def _update_selected_windows_display(self):
        """更新已选择窗口的显示"""
        if not self.dialog_window:
            return
        
        try:
            display_list = [
                f"{w.title} ({w.process_name})" 
                for w in self.selected_windows
            ]
            self.dialog_window["-SELECTED_WINDOWS-"].update(values=display_list)
            
        except Exception as e:
            print(f"更新选择窗口显示失败: {e}")
    
    def _status_to_text(self, status: TaskStatus) -> str:
        """状态枚举转换为文本"""
        status_map = {
            TaskStatus.PENDING: "待处理",
            TaskStatus.ACTIVE: "活跃", 
            TaskStatus.BLOCKED: "被阻塞",
            TaskStatus.COMPLETED: "已完成"
        }
        return status_map.get(status, "待处理")
    
    def _text_to_status(self, text: str) -> TaskStatus:
        """文本转换为状态枚举"""
        text_map = {
            "待处理": TaskStatus.PENDING,
            "活跃": TaskStatus.ACTIVE,
            "被阻塞": TaskStatus.BLOCKED,
            "已完成": TaskStatus.COMPLETED
        }
        return text_map.get(text, TaskStatus.PENDING)