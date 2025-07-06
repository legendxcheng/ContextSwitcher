"""
窗口选择器模块

提供窗口选择功能:
- 显示所有可用窗口
- 多选支持
- 实时刷新
- 窗口信息展示
"""

from typing import List, Dict, Any, Optional, Set
import time

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise

from core.window_manager import WindowManager, WindowInfo


class WindowSelector:
    """窗口选择器类"""
    
    def __init__(self, window_manager: WindowManager):
        """初始化窗口选择器
        
        Args:
            window_manager: 窗口管理器实例
        """
        self.window_manager = window_manager
        self.last_refresh = 0
        self.refresh_interval = 5.0  # 5秒自动刷新间隔
        
        # 选择状态
        self.selected_windows: Set[int] = set()  # 存储选中的窗口句柄
        
        # 过滤选项
        self.show_all_windows = True
        self.filter_text = ""
        
        # 搜索结果缓存
        self._current_search_results = {}
        
        # 优先级信息缓存
        self._current_priorities = {}
        
        # 优先级管理器
        from utils.window_priority import WindowPriorityManager
        self.priority_manager = WindowPriorityManager()
        
    def show_selector_dialog(self, 
                           parent_window: sg.Window = None,
                           title: str = "选择窗口",
                           multiple: bool = True,
                           pre_selected: List[int] = None) -> Optional[List[WindowInfo]]:
        """显示窗口选择对话框
        
        Args:
            parent_window: 父窗口
            title: 对话框标题
            multiple: 是否允许多选
            pre_selected: 预选中的窗口句柄列表
            
        Returns:
            选中的窗口信息列表，取消则返回None
        """
        # 初始化选择状态
        self.selected_windows = set(pre_selected or [])
        
        # 创建对话框布局
        layout = self._create_selector_layout(multiple)
        
        # 创建对话框窗口
        dialog = sg.Window(
            title,
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=True,
            size=(800, 600),
            return_keyboard_events=True  # 启用键盘事件
        )
        
        try:
            # 初始加载窗口列表
            self._refresh_window_list(dialog)
            
            # 运行对话框事件循环
            while True:
                event, values = dialog.read(timeout=1000)
                
                if event == sg.WIN_CLOSED or event == "-CANCEL-":
                    return None
                
                elif event == "-OK-":
                    # 返回选中的窗口信息
                    selected_windows = []
                    all_windows = self.window_manager.enumerate_windows()
                    
                    for window in all_windows:
                        if window.hwnd in self.selected_windows:
                            selected_windows.append(window)
                    
                    return selected_windows
                
                elif event == "-REFRESH-":
                    self._refresh_window_list(dialog)
                
                elif event == "-WINDOW_LIST-":
                    self._handle_window_selection(dialog, values, multiple)
                
                elif event == "-SELECT_ALL-":
                    self._select_all_windows(dialog)
                
                elif event == "-SELECT_NONE-":
                    self._select_no_windows(dialog)
                
                elif event == "-FILTER_TEXT-":
                    self.filter_text = values["-FILTER_TEXT-"].strip()
                    self._apply_filter(dialog)
                
                elif event == "-CLEAR_SEARCH-":
                    dialog["-FILTER_TEXT-"].update("")
                    self.filter_text = ""
                    self._apply_filter(dialog)
                
                # 处理键盘导航事件
                elif self._handle_keyboard_navigation(event, dialog, multiple):
                    continue  # 键盘事件已处理
                
                # 定期自动刷新
                current_time = time.time()
                if current_time - self.last_refresh > self.refresh_interval:
                    self._refresh_window_list(dialog)
        
        finally:
            dialog.close()
    
    def _create_selector_layout(self, multiple: bool) -> List[List[Any]]:
        """创建选择器布局"""
        # 标题和说明
        title_row = [
            sg.Text("选择要绑定的窗口:", font=("Arial", 12, "bold")),
            sg.Push(),
            sg.Text("双击选择/取消选择" if multiple else "单击选择")
        ]
        
        # 优化的搜索和控制区域
        filter_row = [
            sg.Text("🔍 搜索:", font=("Arial", 10), text_color="#0078D4"),
            sg.Input(key="-FILTER_TEXT-", size=(30, 1), 
                    enable_events=True, 
                    tooltip="输入窗口名称或进程名进行搜索，支持多个关键词用空格分隔"),
            sg.Button("×", key="-CLEAR_SEARCH-", size=(2, 1), 
                     button_color=("#666666", "#F0F0F0"),
                     tooltip="清空搜索"),
            sg.Text("", key="-SEARCH_COUNT-", size=(15, 1), 
                   text_color="#666666", font=("Arial", 9)),
            sg.Push(),
            sg.Button("刷新", key="-REFRESH-", size=(8, 1),
                     button_color=("#FFFFFF", "#0078D4"))
        ]
        
        if multiple:
            filter_row.extend([
                sg.Button("全选", key="-SELECT_ALL-", size=(8, 1)),
                sg.Button("全不选", key="-SELECT_NONE-", size=(8, 1))
            ])
        
        # 窗口列表（添加优先级列）
        window_list_headings = ["选择", "优先级", "窗口标题", "进程名", "状态", "窗口句柄"]
        
        window_list = [
            sg.Table(
                values=[],
                headings=window_list_headings,
                key="-WINDOW_LIST-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[6, 8, 30, 15, 8, 12],
                justification="left",
                alternating_row_color="#F8F9FA",
                selected_row_colors="#FFFFFF on #28A745",
                header_background_color="#007BFF",
                header_text_color="#FFFFFF",
                header_font=("Arial", 10, "bold"),
                font=("Arial", 9),
                num_rows=15,
                expand_x=True,
                expand_y=True,
                tooltip="双击行来选择/取消选择窗口"
            )
        ]
        
        # 选中窗口统计
        stats_row = [
            sg.Text("", key="-STATS-", font=("Arial", 9), text_color="#666666"),
            sg.Push(),
            sg.Text("", key="-REFRESH_TIME-", font=("Arial", 8), text_color="#999999")
        ]
        
        # 键盘快捷键提示
        keyboard_hints_row = [
            sg.Text("键盘快捷键: ↑↓方向键=导航 | 回车/空格=选择 | F5=刷新 | Ctrl+A=全选 | Ctrl+D=全不选 | ESC=关闭", 
                   font=("Arial", 8), text_color="#888888"),
            sg.Push()
        ]
        
        # 按钮区域
        button_row = [
            sg.Push(),
            sg.Button("确定", key="-OK-", size=(10, 1), 
                     button_color=("#FFFFFF", "#28A745")),
            sg.Button("取消", key="-CANCEL-", size=(10, 1)),
            sg.Push()
        ]
        
        # 完整布局
        layout = [
            title_row,
            [sg.HorizontalSeparator()],
            filter_row,
            [sg.HorizontalSeparator()],
            window_list,
            [sg.HorizontalSeparator()],
            stats_row,
            keyboard_hints_row,
            [sg.HorizontalSeparator()],
            button_row
        ]
        
        return layout
    
    def _refresh_window_list(self, dialog: sg.Window):
        """刷新窗口列表"""
        try:
            # 强制刷新窗口缓存
            self.window_manager.invalidate_cache()
            
            # 获取所有窗口
            all_windows = self.window_manager.enumerate_windows()
            
            # 应用过滤和智能排序
            filtered_windows = self._filter_and_sort_windows(all_windows)
            
            # 创建表格数据
            table_data = []
            for window in filtered_windows:
                is_selected = window.hwnd in self.selected_windows
                
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
                
                # 窗口状态
                if window.is_enabled:
                    status = "正常"
                else:
                    status = "禁用"
                
                # 使用高亮显示的文本（如果有搜索结果）
                display_title = window.title
                display_process = window.process_name
                
                if self.filter_text and window.hwnd in self._current_search_results:
                    search_result = self._current_search_results[window.hwnd]
                    # 移除高亮标记用于表格显示，但可以考虑其他高亮方式
                    from utils.search_helper import SearchHelper
                    display_title = SearchHelper.format_highlighted_text_for_table(search_result.highlighted_title)
                    display_process = SearchHelper.format_highlighted_text_for_table(search_result.highlighted_process)
                
                table_data.append([
                    "✓" if is_selected else "",
                    priority_indicator,
                    display_title,
                    display_process,
                    status,
                    str(window.hwnd)
                ])
            
            # 更新表格
            dialog["-WINDOW_LIST-"].update(values=table_data)
            
            # 更新统计信息
            selected_count = len(self.selected_windows)
            total_count = len(all_windows)
            filtered_count = len(filtered_windows)
            
            if self.filter_text:
                stats = f"已选择: {selected_count} | 显示: {filtered_count}/{total_count} 个窗口"
                search_info = f"搜索到 {filtered_count} 个结果"
            else:
                stats = f"已选择: {selected_count} | 共 {total_count} 个窗口"
                search_info = ""
            
            dialog["-STATS-"].update(stats)
            
            # 更新搜索计数显示
            if "-SEARCH_COUNT-" in dialog.AllKeysDict:
                dialog["-SEARCH_COUNT-"].update(search_info)
            
            # 更新刷新时间
            refresh_time = time.strftime("%H:%M:%S")
            dialog["-REFRESH_TIME-"].update(f"最后刷新: {refresh_time}")
            
            self.last_refresh = time.time()
            
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")
            dialog["-STATS-"].update("刷新失败")
    
    def _filter_and_sort_windows(self, windows: List[WindowInfo]) -> List[WindowInfo]:
        """使用智能排序和搜索过滤窗口列表"""
        # 获取活跃窗口信息
        active_windows_info = self.window_manager.get_active_windows_info()
        
        # 搜索过滤
        search_results_dict = {}
        filtered_windows = windows
        
        if self.filter_text:
            # 使用搜索功能
            from utils.search_helper import SearchHelper
            search_results = SearchHelper.search_windows(windows, self.filter_text)
            
            # 存储搜索结果
            search_results_dict = {
                result.item.hwnd: result for result in search_results
            }
            
            # 过滤出有匹配的窗口
            filtered_windows = [result.item for result in search_results]
        
        # 存储搜索结果用于显示
        self._current_search_results = search_results_dict
        
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
    
    def _apply_filter(self, dialog: sg.Window):
        """应用过滤器"""
        self._refresh_window_list(dialog)
    
    def _handle_window_selection(self, dialog: sg.Window, values: Dict[str, Any], multiple: bool):
        """处理窗口选择"""
        try:
            selected_rows = values.get("-WINDOW_LIST-", [])
            if not selected_rows:
                return
            
            row_index = selected_rows[0]
            table_data = dialog["-WINDOW_LIST-"].get()
            
            if row_index >= len(table_data):
                return
            
            # 获取窗口句柄 (优先级列插入后，句柄现在在第5列)
            hwnd_str = table_data[row_index][5]
            hwnd = int(hwnd_str)
            
            # 切换选择状态
            if multiple:
                if hwnd in self.selected_windows:
                    self.selected_windows.remove(hwnd)
                else:
                    self.selected_windows.add(hwnd)
            else:
                # 单选模式：清除其他选择
                self.selected_windows.clear()
                self.selected_windows.add(hwnd)
            
            # 刷新显示
            self._refresh_window_list(dialog)
            
        except Exception as e:
            print(f"处理窗口选择失败: {e}")
    
    def _select_all_windows(self, dialog: sg.Window):
        """选择所有窗口"""
        try:
            # 获取当前显示的窗口
            all_windows = self.window_manager.enumerate_windows()
            filtered_windows = self._filter_and_sort_windows(all_windows)
            
            # 添加所有过滤后的窗口到选择集合
            for window in filtered_windows:
                self.selected_windows.add(window.hwnd)
            
            # 刷新显示
            self._refresh_window_list(dialog)
            
        except Exception as e:
            print(f"全选失败: {e}")
    
    def _select_no_windows(self, dialog: sg.Window):
        """取消选择所有窗口"""
        try:
            self.selected_windows.clear()
            self._refresh_window_list(dialog)
            
        except Exception as e:
            print(f"取消全选失败: {e}")
    
    def _handle_keyboard_navigation(self, event: str, dialog: sg.Window, multiple: bool) -> bool:
        """处理键盘导航事件
        
        Args:
            event: 键盘事件
            dialog: 对话框窗口
            multiple: 是否多选模式
            
        Returns:
            是否处理了该事件
        """
        try:
            table_widget = dialog["-WINDOW_LIST-"]
            
            # 获取当前选中行
            current_selection = table_widget.SelectedRows
            if not current_selection:
                current_row = -1
            else:
                current_row = current_selection[0]
            
            table_data = table_widget.Values
            if not table_data:
                return False
            
            max_row = len(table_data) - 1
            new_row = current_row
            
            # 处理不同的键盘事件
            if event == "Up:38" or event == "Up":
                # 上箭头键
                new_row = max(0, current_row - 1)
            
            elif event == "Down:40" or event == "Down":
                # 下箭头键
                new_row = min(max_row, current_row + 1)
            
            elif event == "Prior:33" or event == "Page_Up":
                # Page Up - 向上翻页
                new_row = max(0, current_row - 5)
            
            elif event == "Next:34" or event == "Page_Down":
                # Page Down - 向下翻页
                new_row = min(max_row, current_row + 5)
            
            elif event == "Home:36" or event == "Home":
                # Home键 - 跳到第一行
                new_row = 0
            
            elif event == "End:35" or event == "End":
                # End键 - 跳到最后一行
                new_row = max_row
            
            elif event == "Return:13" or event == "space:32" or event == "Return" or event == "space":
                # 回车键或空格键 - 切换选择状态
                if current_row >= 0:
                    self._toggle_window_selection(current_row, dialog, multiple)
                return True
            
            elif event == "F5:116" or event == "F5":
                # F5键 - 刷新
                self._refresh_window_list(dialog)
                return True
            
            elif event == "Escape:27" or event == "Escape":
                # ESC键 - 关闭对话框
                dialog.close()
                return True
            
            elif event.startswith("Control_L") and event.endswith("a"):
                # Ctrl+A - 全选（仅多选模式）
                if multiple:
                    self._select_all_windows(dialog)
                return True
            
            elif event.startswith("Control_L") and event.endswith("d"):
                # Ctrl+D - 全不选
                self._select_no_windows(dialog)
                return True
            
            else:
                # 未处理的事件
                return False
            
            # 更新选中行
            if new_row != current_row and 0 <= new_row <= max_row:
                table_widget.update(select_rows=[new_row])
                # 确保选中行可见
                table_widget.Widget.see(new_row)
            
            return True
            
        except Exception as e:
            print(f"键盘导航处理失败: {e}")
            return False
    
    def _toggle_window_selection(self, row_index: int, dialog: sg.Window, multiple: bool):
        """切换窗口选择状态
        
        Args:
            row_index: 表格行索引
            dialog: 对话框窗口
            multiple: 是否多选模式
        """
        try:
            table_data = dialog["-WINDOW_LIST-"].Values
            if not table_data or row_index >= len(table_data):
                return
            
            # 获取窗口句柄 (优先级列插入后，句柄现在在第5列)
            hwnd_str = table_data[row_index][5]
            hwnd = int(hwnd_str)
            
            # 切换选择状态
            if multiple:
                if hwnd in self.selected_windows:
                    self.selected_windows.remove(hwnd)
                else:
                    self.selected_windows.add(hwnd)
            else:
                # 单选模式：清除其他选择
                self.selected_windows.clear()
                self.selected_windows.add(hwnd)
            
            # 刷新显示
            self._refresh_window_list(dialog)
            
        except Exception as e:
            print(f"切换窗口选择失败: {e}")

    def get_window_summary(self, windows: List[WindowInfo]) -> Dict[str, Any]:
        """获取窗口摘要信息"""
        if not windows:
            return {"total": 0}
        
        # 按进程分组统计
        process_count = {}
        enabled_count = 0
        
        for window in windows:
            # 进程统计
            process = window.process_name
            process_count[process] = process_count.get(process, 0) + 1
            
            # 状态统计
            if window.is_enabled:
                enabled_count += 1
        
        return {
            "total": len(windows),
            "enabled": enabled_count,
            "disabled": len(windows) - enabled_count,
            "top_processes": dict(sorted(process_count.items(), 
                                       key=lambda x: x[1], reverse=True)[:5])
        }