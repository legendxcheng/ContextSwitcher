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
from gui.modern_config import ModernUIConfig
from utils.dialog_position_manager import get_dialog_position_manager
from utils.popup_helper import PopupManager


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
        
        # 对话框位置管理器
        self.position_manager = get_dialog_position_manager()
        
        # 弹窗管理器
        self.popup_manager = PopupManager(parent_window)
        
        # 对话框窗口
        self.dialog_window: Optional[sg.Window] = None
        
        # 表单数据
        self.task_name = ""
        self.task_description = ""
        self.task_status = TaskStatus.TODO
        self.task_priority = 0  # 优先级: 0=普通, 1=低, 2=中, 3=高
        self.task_notes = ""    # 快速笔记
        self.task_tags: List[str] = []  # 标签列表
        self.selected_windows: List[WindowInfo] = []
        
        # 搜索和过滤相关
        self.window_filter_text = ""
        self._filtered_windows = []
        self._current_priorities = {}
        
        # 导入增强功能模块
        from utils.search_helper import SearchHelper
        from utils.window_priority import WindowPriorityManager
        self.search_helper = SearchHelper()
        self.priority_manager = WindowPriorityManager()
        
        # 编辑模式标识
        self._editing_task_id = None
    
    def _get_main_window_position(self) -> Optional[tuple]:
        """获取主窗口位置
        
        Returns:
            主窗口位置 (x, y) 或 None
        """
        try:
            if self.parent_window and hasattr(self.parent_window, 'current_location'):
                location = self.parent_window.current_location()
                if location and len(location) == 2:
                    return location
        except Exception as e:
            print(f"获取主窗口位置失败: {e}")
        return None
    
    def show_add_dialog(self) -> bool:
        """显示添加任务对话框
        
        Returns:
            是否成功添加任务
        """
        # 清除编辑模式标识
        self._editing_task_id = None
        
        # 重置表单数据
        self.task_name = ""
        self.task_description = ""
        self.task_status = TaskStatus.TODO
        self.task_priority = 0
        self.task_notes = ""
        self.task_tags = []
        self.selected_windows = []
        
        # 重置搜索状态
        self.window_filter_text = ""
        self._filtered_windows = []
        self._current_priorities = {}
        
        # 创建对话框
        layout = self._create_add_layout()
        # 获取图标路径
        icon_path = ModernUIConfig._get_icon_path()
        
        # 动态计算对话框位置
        dialog_size = (620, 650)
        main_window_position = self._get_main_window_position()
        dialog_position = self.position_manager.get_task_dialog_position(
            dialog_size, main_window_position
        )
        
        self.dialog_window = sg.Window(
            "添加任务",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=True,
            size=dialog_size,
            location=dialog_position,  # 使用动态计算的位置
            no_titlebar=False,  # 对话框保留标题栏
            alpha_channel=0.98,  # 轻微透明
            background_color="#202020",
            margins=(10, 8),  # 减少边距
            element_padding=(3, 2),  # 减少元素间距
            icon=icon_path if icon_path else None
        )
        
        # 初始化窗口列表数据
        self._refresh_window_list()
        
        # 绑定双击事件（在窗口finalize后）
        self.dialog_window['-WINDOW_TABLE-'].bind('<Double-Button-1>', ' Double')
        
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
                # 设置状态、优先级、笔记和标签
                self.task_manager.edit_task(
                    task.id,
                    status=self.task_status,
                    priority=self.task_priority,
                    notes=self.task_notes,
                    tags=self.task_tags
                )
                return True

        return False
    
    def show_edit_dialog(self, task: Task) -> bool:
        """显示编辑任务对话框
        
        Args:
            task: 要编辑的任务
            
        Returns:
            是否成功编辑任务
        """
        # 设置编辑模式标识
        self._editing_task_id = task.id
        
        # 加载现有数据
        self.task_name = task.name
        self.task_description = task.description
        self.task_status = task.status
        self.task_priority = getattr(task, 'priority', 0)
        self.task_notes = getattr(task, 'notes', "")
        self.task_tags = getattr(task, 'tags', []) or []
        
        # 加载绑定的窗口
        self.selected_windows = []
        for bound_window in task.bound_windows:
            if bound_window.is_valid:
                window_info = self.task_manager.window_manager.get_window_info(bound_window.hwnd)
                if window_info:
                    self.selected_windows.append(window_info)
        
        # 重置搜索状态
        self.window_filter_text = ""
        self._filtered_windows = []
        self._current_priorities = {}
        
        # 创建对话框
        layout = self._create_edit_layout()
        # 获取图标路径
        icon_path = ModernUIConfig._get_icon_path()
        
        # 动态计算对话框位置
        dialog_size = (620, 650)
        main_window_position = self._get_main_window_position()
        dialog_position = self.position_manager.get_task_dialog_position(
            dialog_size, main_window_position
        )
        
        self.dialog_window = sg.Window(
            f"编辑任务 - {task.name}",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=True,
            size=dialog_size,
            location=dialog_position,  # 使用动态计算的位置
            no_titlebar=False,  # 对话框保留标题栏
            alpha_channel=0.98,  # 轻微透明
            background_color="#202020",
            margins=(10, 8),  # 减少边距
            element_padding=(3, 2),  # 减少元素间距
            icon=icon_path if icon_path else None
        )
        
        # 初始化窗口列表数据
        self._refresh_window_list()
        
        # 绑定双击事件（在窗口finalize后）
        self.dialog_window['-WINDOW_TABLE-'].bind('<Double-Button-1>', ' Double')
        
        # 运行对话框
        result = self._run_dialog()
        
        if result:
            # 更新任务（包括优先级、笔记和标签）
            window_hwnds = [w.hwnd for w in self.selected_windows]
            success = self.task_manager.edit_task(
                task.id,
                name=self.task_name,
                description=self.task_description,
                status=self.task_status,
                window_hwnds=window_hwnds,
                priority=self.task_priority,
                notes=self.task_notes,
                tags=self.task_tags
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
        # 优先级选项
        priority_options = ["普通", "低", "中", "高"]
        priority_default = priority_options[self.task_priority] if 0 <= self.task_priority < len(priority_options) else "普通"

        # 标签显示文本（用逗号分隔）
        tags_display = ", ".join(self.task_tags) if self.task_tags else ""

        # 任务信息区域
        info_frame = [
            [sg.Text("任务名称:", size=(10, 1)),
             sg.Input(self.task_name, key="-TASK_NAME-", size=(40, 1))],
            [sg.Text("任务描述:", size=(10, 1)),
             sg.Multiline(self.task_description, key="-TASK_DESC-",
                         size=(40, 2), enable_events=True)],
            [sg.Text("任务状态:", size=(10, 1)),
             sg.Combo(["待办", "进行中", "已阻塞", "待审查", "已完成", "已暂停"],
                     default_value=self._status_to_text(self.task_status),
                     key="-TASK_STATUS-", readonly=True, size=(12, 1)),
             sg.Text("优先级:", size=(6, 1)),
             sg.Combo(priority_options,
                     default_value=priority_default,
                     key="-TASK_PRIORITY-", readonly=True, size=(8, 1))],
            [sg.Text("标签:", size=(10, 1)),
             sg.Input(tags_display, key="-TASK_TAGS-", size=(40, 1),
                     tooltip="用逗号分隔多个标签，例如: 前端, bug修复, 紧急")],
            [sg.Text("快速笔记:", size=(10, 1)),
             sg.Multiline(self.task_notes, key="-TASK_NOTES-",
                         size=(40, 2), enable_events=True,
                         tooltip="记录任务相关的快速笔记、链接或要点")]
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
        
        print("🔍 调试: 按钮区域已创建")
        
        # 使用Column来更好地控制布局
        main_column = [
            [sg.Frame("任务信息", info_frame, expand_x=True, 
                     element_justification="left")],
            [sg.Frame("绑定窗口", window_frame, expand_x=True, expand_y=True)],  # 允许垂直扩展以填充空间
        ]
        
        # 完整布局
        layout = [
            [sg.Column(main_column, expand_x=True, expand_y=True, 
                      scrollable=False, vertical_scroll_only=False,
                      size=(None, None))],  # 让Column自动调整大小
            [sg.HorizontalSeparator()],
            button_row  # 按钮单独一行，确保始终可见
        ]
        
        return layout
    
    def _create_window_selection_frame(self) -> List[List[Any]]:
        """创建窗口选择框架"""
        # 初始化空的窗口列表数据，稍后通过_refresh_window_list填充
        window_data = []
        
        # 窗口选择表格（添加优先级列）
        table_headings = ["选择", "优先级", "窗口标题", "进程", "句柄"]
        
        window_frame = [
            [sg.Text("选择要绑定到此任务的窗口:")],
            [sg.Text("操作: 1.双击窗口行直接添加  2.或点击选中后点击'添加选择'按钮", font=("Arial", 9), text_color="#666666")],
            # 搜索行
            [sg.Text("🔍 搜索:", font=("Arial", 10), text_color="#0078D4"),
             sg.Input("", key="-WINDOW_FILTER-", size=(20, 1), 
                     enable_events=True, 
                     tooltip="输入关键词搜索窗口标题或进程名"),
             sg.Button("×", key="-CLEAR_FILTER-", size=(2, 1), 
                      button_color=("#666666", "#F0F0F0"),
                      tooltip="清空搜索"),
             sg.Text("输入关键词过滤窗口", font=("Arial", 8), text_color="#888888")],
            [sg.Button("刷新窗口列表", key="-REFRESH_WINDOWS-", size=(12, 1),
                      button_color=("#FFFFFF", "#0078D4"), font=("Segoe UI", 9), border_width=0),
             sg.Button("添加选择", key="-ADD_WINDOW-", size=(10, 1), 
                      button_color=("#FFFFFF", "#107C10"), font=("Segoe UI", 9), border_width=0),
             sg.Text("", key="-FILTER_COUNT-", size=(15, 1), 
                    text_color="#666666", font=("Arial", 9))],
            [sg.Table(
                values=window_data,
                headings=table_headings,
                key="-WINDOW_TABLE-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[6, 8, 25, 12, 10],  # 调整列宽以适应优先级列
                justification="left",
                alternating_row_color="#404040",
                selected_row_colors="#CCCCCC on #0078D4",
                header_background_color="#2D2D2D",
                header_text_color="#FFFFFF",
                font=("Arial", 9),
                num_rows=8,  # 增加行数以更好利用空间
                expand_x=True,
                expand_y=True  # 允许垂直扩展
            )],
            [sg.Text("已选择窗口:", font=("Arial", 10, "bold"))],
            [sg.Listbox(
                values=[f"{w.title} ({w.process_name})" for w in self.selected_windows],
                key="-SELECTED_WINDOWS-",
                size=(50, 6),  # 基础高度
                enable_events=True,
                expand_x=True,
                expand_y=True  # 允许垂直扩展以填充剩余空间
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
                
                elif event == "-WINDOW_TABLE- Double":
                    # 处理双击事件：直接添加窗口
                    self._handle_table_double_click(values)
                
                elif event == "-ADD_WINDOW-":
                    # 新增的添加按钮
                    self._handle_add_window(values)
                
                elif event == "-REMOVE_WINDOW-":
                    self._handle_remove_window(values)
                
                elif event == "-WINDOW_FILTER-":
                    # 处理搜索过滤
                    self.window_filter_text = values["-WINDOW_FILTER-"].strip()
                    self._refresh_window_list()
                
                elif event == "-CLEAR_FILTER-":
                    # 清空搜索
                    self.dialog_window["-WINDOW_FILTER-"].update("")
                    self.window_filter_text = ""
                    self._refresh_window_list()
        
        finally:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None
            # 清理编辑模式标识
            self._editing_task_id = None
    
    def _validate_form(self, values: Dict[str, Any]) -> bool:
        """验证表单数据"""
        # 检查任务名称
        task_name = values["-TASK_NAME-"].strip()
        if not task_name:
            self.popup_manager.show_error("请输入任务名称", "验证错误")
            return False
        
        # 检查名称重复（编辑时跳过当前任务）
        existing_tasks = self.task_manager.get_all_tasks()
        for task in existing_tasks:
            if task.name == task_name:
                # 如果是编辑模式且是同一个任务，则允许
                if hasattr(self, '_editing_task_id') and self._editing_task_id is not None and task.id == self._editing_task_id:
                    print(f"🔍 编辑模式：跳过当前任务 {task.id} 的名称验证")
                    continue
                self.popup_manager.show_error(f"任务名称 '{task_name}' 已存在", "验证错误")
                return False
        
        # 检查是否选择了窗口
        if not self.selected_windows:
            result = self.popup_manager.show_question(
                "没有选择任何窗口，确定要创建此任务吗？",
                "确认"
            )
            if not result:
                return False
        
        return True
    
    def _save_form_data(self, values: Dict[str, Any]):
        """保存表单数据"""
        self.task_name = values["-TASK_NAME-"].strip()
        self.task_description = values["-TASK_DESC-"].strip()
        self.task_notes = values.get("-TASK_NOTES-", "").strip()

        # 转换状态
        status_text = values["-TASK_STATUS-"]
        self.task_status = self._text_to_status(status_text)

        # 转换优先级
        priority_text = values.get("-TASK_PRIORITY-", "普通")
        priority_map = {"普通": 0, "低": 1, "中": 2, "高": 3}
        self.task_priority = priority_map.get(priority_text, 0)

        # 解析标签（逗号分隔）
        tags_text = values.get("-TASK_TAGS-", "").strip()
        if tags_text:
            self.task_tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        else:
            self.task_tags = []
    
    def _refresh_window_list(self):
        """刷新窗口列表（增强版，支持搜索和优先级）"""
        if not self.dialog_window:
            return
        
        try:
            # 强制刷新窗口缓存
            self.task_manager.window_manager.invalidate_cache()
            
            # 获取最新窗口列表
            all_windows = self.task_manager.window_manager.enumerate_windows()
            
            # 应用搜索过滤和智能排序
            filtered_windows = self._filter_and_sort_windows(all_windows)
            self._filtered_windows = filtered_windows
            
            # 更新表格数据
            window_data = []
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            
            for window in filtered_windows:
                is_selected = window.hwnd in selected_hwnds
                
                # 获取优先级信息
                priority_info = self._current_priorities.get(window.hwnd)
                priority_indicator = ""
                
                if priority_info:
                    # 根据窗口类型显示不同的优先级图标
                    if priority_info.is_foreground:
                        priority_indicator = "🔥"  # 前台窗口
                    elif priority_info.is_active:
                        priority_indicator = "⭐"  # 活跃窗口
                    elif priority_info.is_recent:
                        priority_indicator = "📌"  # 最近使用
                    elif priority_info.search_score > 0:
                        priority_indicator = "🔍"  # 搜索匹配
                    elif priority_info.total_score > 50:
                        priority_indicator = "💻"  # 高优先级应用
                
                # 显示文本处理（如果有搜索关键词）
                display_title = window.title
                display_process = window.process_name
                
                if self.window_filter_text:
                    # 移除高亮标记用于表格显示
                    from utils.search_helper import SearchHelper
                    # 这里可以添加高亮处理，暂时保持原文本
                    pass
                
                window_data.append([
                    "✓" if is_selected else "",
                    priority_indicator,
                    display_title,
                    display_process,
                    str(window.hwnd)
                ])
            
            # 更新表格
            self.dialog_window["-WINDOW_TABLE-"].update(values=window_data)
            
            # 更新搜索统计信息
            total_count = len(all_windows)
            filtered_count = len(filtered_windows)
            
            if self.window_filter_text:
                filter_info = f"显示 {filtered_count}/{total_count}"
            else:
                filter_info = f"共 {total_count} 个窗口"
            
            if "-FILTER_COUNT-" in self.dialog_window.AllKeysDict:
                self.dialog_window["-FILTER_COUNT-"].update(filter_info)
            
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")
            self.popup_manager.show_error(f"刷新失败: {e}", "错误")
    
    def _filter_and_sort_windows(self, windows: List[WindowInfo]) -> List[WindowInfo]:
        """使用智能排序和搜索过滤窗口列表"""
        try:
            # 获取活跃窗口信息
            active_windows_info = self.task_manager.window_manager.get_active_windows_info()
            
            # 搜索过滤
            search_results_dict = {}
            filtered_windows = windows
            
            if self.window_filter_text:
                # 使用搜索功能
                search_results = self.search_helper.search_windows(windows, self.window_filter_text)
                
                # 存储搜索结果
                search_results_dict = {
                    result.item.hwnd: result for result in search_results
                }
                
                # 过滤出有匹配的窗口
                filtered_windows = [result.item for result in search_results]
            
            # 使用优先级管理器进行智能排序
            priorities = self.priority_manager.calculate_window_priorities(
                filtered_windows, active_windows_info, search_results_dict
            )
            
            # 存储优先级信息用于显示
            self._current_priorities = {
                priority.window.hwnd: priority for priority in priorities
            }
            
            # 返回按优先级排序的窗口列表
            return [priority.window for priority in priorities]
            
        except Exception as e:
            print(f"过滤和排序窗口失败: {e}")
            return windows  # 出错时返回原始列表
    
    def _handle_table_click(self, values: Dict[str, Any]):
        """处理表格单击事件"""
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                print("⚠️ 表格点击：没有选中行")
                return
            
            row_index = selected_rows[0]
            print(f"📌 单击事件：行索引: {row_index}")
            
            # 使用Values属性获取完整的表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values
            
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
    
    def _handle_table_double_click(self, values: Dict[str, Any]):
        """处理表格双击事件，直接添加窗口"""
        try:
            selected_rows = values.get("-WINDOW_TABLE-", [])
            if not selected_rows:
                print("⚠️ 表格双击：没有选中行")
                return
            
            row_index = selected_rows[0]
            print(f"✅ 检测到双击事件！行索引: {row_index}, 开始添加窗口")
            
            # 直接添加窗口
            self._add_window_by_row_index(row_index)
            
        except Exception as e:
            print(f"处理表格双击失败: {e}")
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
                self.popup_manager.show_message("请先选择一个窗口", "提示")
                return
            
            row_index = selected_rows[0]
            # 使用Values属性获取完整的表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values
            
            print(f"添加窗口调试 - row_index: {row_index}, table_data类型: {type(table_data)}, len(table_data): {len(table_data) if table_data else 0}")
            
            if not table_data or row_index >= len(table_data):
                print(f"表格数据异常: row_index={row_index}, len(table_data)={len(table_data) if table_data else 0}")
                self.popup_manager.show_error("表格数据异常", "错误")
                return
            
            # 检查行数据格式
            if not isinstance(table_data[row_index], list) or len(table_data[row_index]) < 5:
                print(f"表格行数据格式异常: {table_data[row_index]}")
                self.popup_manager.show_error("表格行数据格式异常", "错误")
                return
            
            # 获取窗口句柄 (新表格结构中句柄在第4列，索引为4)
            hwnd_str = table_data[row_index][4]
            hwnd = int(hwnd_str)
            
            # 检查是否已经选择
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            if hwnd in selected_hwnds:
                self.popup_manager.show_message("此窗口已经选择", "提示")
                return
            
            # 获取窗口信息并添加
            window_info = self.task_manager.window_manager.get_window_info(hwnd)
            if window_info:
                self.selected_windows.append(window_info)
                self._update_selected_windows_display()
                self._refresh_window_list()
                print(f"已添加窗口: {window_info.title}")
                # 不再显示弹窗提示，保持界面简洁
            else:
                self.popup_manager.show_error("窗口信息获取失败", "错误")
                
        except Exception as e:
            print(f"添加窗口失败: {e}")
            self.popup_manager.show_error(f"添加失败: {e}", "错误")
    
    def _add_window_by_row_index(self, row_index: int):
        """通过行索引直接添加窗口（双击触发，无弹窗提示）"""
        try:
            print(f"🔄 开始双击添加窗口，行索引: {row_index}")
            
            # 使用Values属性获取完整的表格数据
            table_widget = self.dialog_window["-WINDOW_TABLE-"]
            table_data = table_widget.Values
            
            print(f"📊 表格数据检查: table_data存在={table_data is not None}, 长度={len(table_data) if table_data else 0}")
            
            if not table_data or row_index >= len(table_data):
                print(f"❌ 表格数据异常: row_index={row_index}, len(table_data)={len(table_data) if table_data else 0}")
                return
            
            # 检查行数据格式
            row_data = table_data[row_index]
            print(f"📋 行数据: {row_data}")
            
            if not isinstance(row_data, list) or len(row_data) < 5:
                print(f"❌ 表格行数据格式异常: {row_data}")
                return
            
            # 获取窗口句柄 (新表格结构中句柄在第4列，索引为4)
            hwnd_str = row_data[4]
            print(f"🎯 窗口句柄字符串: {hwnd_str}")
            hwnd = int(hwnd_str)
            print(f"🎯 窗口句柄: {hwnd}")
            
            # 检查是否已经选择
            selected_hwnds = [w.hwnd for w in self.selected_windows]
            if hwnd in selected_hwnds:
                print(f"⚠️ 窗口已经选择: {hwnd}")
                return
            
            # 获取窗口信息并添加
            print(f"🔍 获取窗口信息: {hwnd}")
            window_info = self.task_manager.window_manager.get_window_info(hwnd)
            if window_info:
                print(f"✅ 窗口信息获取成功: {window_info.title}")
                self.selected_windows.append(window_info)
                self._update_selected_windows_display()
                self._refresh_window_list()
                print(f"🎉 双击添加窗口成功: {window_info.title}")
                # 不显示弹窗提示，只在控制台输出
            else:
                print("❌ 窗口信息获取失败")
                
        except Exception as e:
            print(f"❌ 双击添加窗口失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_remove_window(self, values: Dict[str, Any]):
        """处理移除窗口"""
        try:
            selected_items = values.get("-SELECTED_WINDOWS-", [])
            if not selected_items:
                self.popup_manager.show_message("请先选择要移除的窗口", "提示")
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
                self.popup_manager.show_timed_message(f"已移除窗口: {removed_window.title}", 2, "成功")
            else:
                self.popup_manager.show_error("未找到要移除的窗口", "错误")
            
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
            TaskStatus.TODO: "待办",
            TaskStatus.IN_PROGRESS: "进行中",
            TaskStatus.BLOCKED: "已阻塞",
            TaskStatus.REVIEW: "待审查",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.PAUSED: "已暂停"
        }
        return status_map.get(status, "待办")
    
    def _text_to_status(self, text: str) -> TaskStatus:
        """文本转换为状态枚举"""
        text_map = {
            "待办": TaskStatus.TODO,
            "进行中": TaskStatus.IN_PROGRESS,
            "已阻塞": TaskStatus.BLOCKED,
            "待审查": TaskStatus.REVIEW,
            "已完成": TaskStatus.COMPLETED,
            "已暂停": TaskStatus.PAUSED
        }
        return text_map.get(text, TaskStatus.TODO)