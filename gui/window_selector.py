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
            size=(800, 600)
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
        
        # 过滤和控制区域
        filter_row = [
            sg.Text("过滤:", size=(6, 1)),
            sg.Input(key="-FILTER_TEXT-", size=(30, 1), 
                    enable_events=True, tooltip="输入文本过滤窗口"),
            sg.Push(),
            sg.Button("刷新", key="-REFRESH-", size=(8, 1))
        ]
        
        if multiple:
            filter_row.extend([
                sg.Button("全选", key="-SELECT_ALL-", size=(8, 1)),
                sg.Button("全不选", key="-SELECT_NONE-", size=(8, 1))
            ])
        
        # 窗口列表
        window_list_headings = ["选择", "窗口标题", "进程名", "状态", "窗口句柄"]
        
        window_list = [
            sg.Table(
                values=[],
                headings=window_list_headings,
                key="-WINDOW_LIST-",
                enable_events=True,
                select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                auto_size_columns=False,
                col_widths=[6, 35, 15, 8, 12],
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
            
            # 应用过滤
            filtered_windows = self._filter_windows(all_windows)
            
            # 创建表格数据
            table_data = []
            for window in filtered_windows:
                is_selected = window.hwnd in self.selected_windows
                
                # 窗口状态
                if window.is_enabled:
                    status = "正常"
                else:
                    status = "禁用"
                
                table_data.append([
                    "✓" if is_selected else "",
                    window.title,
                    window.process_name,
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
            else:
                stats = f"已选择: {selected_count} | 共 {total_count} 个窗口"
            
            dialog["-STATS-"].update(stats)
            
            # 更新刷新时间
            refresh_time = time.strftime("%H:%M:%S")
            dialog["-REFRESH_TIME-"].update(f"最后刷新: {refresh_time}")
            
            self.last_refresh = time.time()
            
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")
            dialog["-STATS-"].update("刷新失败")
    
    def _filter_windows(self, windows: List[WindowInfo]) -> List[WindowInfo]:
        """过滤窗口列表"""
        if not self.filter_text:
            return windows
        
        filter_lower = self.filter_text.lower()
        filtered = []
        
        for window in windows:
            # 检查标题或进程名是否包含过滤文本
            if (filter_lower in window.title.lower() or 
                filter_lower in window.process_name.lower()):
                filtered.append(window)
        
        return filtered
    
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
            
            # 获取窗口句柄
            hwnd_str = table_data[row_index][4]
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
            filtered_windows = self._filter_windows(all_windows)
            
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