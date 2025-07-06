"""
智能重新绑定对话框

为失效窗口提供重新绑定界面:
- 显示失效窗口列表
- 提供智能匹配建议
- 支持手动选择新窗口
- 批量重新绑定功能
"""

from typing import List, Dict, Optional, Tuple, Any
import FreeSimpleGUI as sg

from core.task_manager import Task, BoundWindow
from core.smart_rebind_manager import SmartRebindManager, RebindSuggestion
from gui.modern_config import ModernUIConfig


class RebindDialog:
    """智能重新绑定对话框"""
    
    def __init__(self, parent_window, smart_rebind_manager: SmartRebindManager):
        """初始化重新绑定对话框
        
        Args:
            parent_window: 父窗口
            smart_rebind_manager: 智能重新绑定管理器
        """
        self.parent_window = parent_window
        self.smart_rebind_manager = smart_rebind_manager
        self.window: Optional[sg.Window] = None
        
        # 设置主题
        ModernUIConfig.setup_theme()
    
    def show_rebind_dialog(self, task: Task) -> bool:
        """显示重新绑定对话框
        
        Args:
            task: 需要重新绑定的任务
            
        Returns:
            是否进行了重新绑定操作
        """
        # 检查任务并获取建议
        validation_result = self.smart_rebind_manager.validate_and_suggest_rebinds(task)
        
        if validation_result['valid']:
            sg.popup("任务的所有窗口都是有效的，无需重新绑定。", title="提示")
            return False
        
        invalid_windows = validation_result['invalid_windows']
        suggestions = validation_result['suggestions']
        auto_rebind_available = validation_result['auto_rebind_available']
        
        # 创建对话框
        layout = self._create_rebind_layout(task, invalid_windows, suggestions, auto_rebind_available)
        
        self.window = sg.Window(
            f"重新绑定窗口 - {task.name}",
            layout,
            modal=True,
            finalize=True,
            size=(800, 600),
            element_justification='left'
        )
        
        rebind_made = False
        
        try:
            while True:
                event, values = self.window.read()
                
                if event in (sg.WIN_CLOSED, "-CANCEL-"):
                    break
                elif event == "-AUTO_REBIND-":
                    if self._handle_auto_rebind(task):
                        rebind_made = True
                        break
                elif event == "-MANUAL_REBIND-":
                    if self._handle_manual_rebind(task, invalid_windows, values):
                        rebind_made = True
                        break
                elif event.startswith("-SUGGEST_"):
                    self._handle_suggestion_click(event, values)
        
        finally:
            if self.window:
                self.window.close()
                self.window = None
        
        return rebind_made
    
    def _create_rebind_layout(self, task: Task, invalid_windows: List[BoundWindow], 
                            suggestions: Dict[int, List[RebindSuggestion]], 
                            auto_rebind_available: bool) -> List[List[Any]]:
        """创建重新绑定布局"""
        colors = ModernUIConfig.COLORS
        fonts = ModernUIConfig.FONTS
        
        layout = []
        
        # 标题
        layout.append([
            sg.Text(f"任务 '{task.name}' 有 {len(invalid_windows)} 个失效窗口需要重新绑定",
                   font=fonts['heading'], text_color=colors['text'])
        ])
        
        layout.append([sg.HSeparator()])
        
        # 自动重新绑定按钮
        if auto_rebind_available:
            layout.append([
                sg.Text("🤖 智能匹配", font=fonts['body'], text_color=colors['success']),
                sg.Text("系统检测到高相似度匹配，可以自动重新绑定", font=fonts['body']),
                sg.Push(),
                ModernUIConfig.create_modern_button("自动重新绑定", "-AUTO_REBIND-", "success")
            ])
            layout.append([sg.HSeparator()])
        
        # 失效窗口列表和建议
        for i, invalid_window in enumerate(invalid_windows):
            window_suggestions = suggestions.get(invalid_window.hwnd, [])
            
            # 失效窗口信息
            layout.append([
                sg.Text(f"失效窗口 {i+1}:", font=fonts['subheading'], text_color=colors['error'])
            ])
            layout.append([
                sg.Text(f"标题: {invalid_window.title}", font=fonts['body']),
                sg.Text(f"进程: {invalid_window.process_name}", font=fonts['body'])
            ])
            
            # 建议列表
            if window_suggestions:
                layout.append([
                    sg.Text("建议的替代窗口:", font=fonts['body'], text_color=colors['primary'])
                ])
                
                suggestion_data = []
                for j, suggestion in enumerate(window_suggestions[:5]):  # 最多显示5个建议
                    score_text = f"{suggestion.similarity_score:.1%}"
                    suggestion_data.append([
                        j + 1,
                        suggestion.window_title[:40] + "..." if len(suggestion.window_title) > 40 else suggestion.window_title,
                        suggestion.window_process,
                        score_text,
                        suggestion.match_reason
                    ])
                
                suggestion_table = sg.Table(
                    values=suggestion_data,
                    headings=["#", "窗口标题", "进程", "相似度", "匹配原因"],
                    key=f"-SUGGESTIONS_{invalid_window.hwnd}-",
                    justification='left',
                    alternating_row_color='lightgray',
                    selected_row_colors='red on yellow',
                    enable_events=True,
                    num_rows=min(5, len(window_suggestions)),
                    col_widths=[3, 25, 10, 8, 15]
                )
                layout.append([suggestion_table])
            else:
                layout.append([
                    sg.Text("未找到合适的替代窗口建议", font=fonts['body'], text_color=colors['text_secondary'])
                ])
            
            layout.append([sg.HSeparator()])
        
        # 手动选择区域
        layout.append([
            sg.Text("手动重新绑定:", font=fonts['subheading'], text_color=colors['primary'])
        ])
        layout.append([
            sg.Text("选择失效窗口:"),
            sg.Combo([f"{i+1}. {w.title}" for i, w in enumerate(invalid_windows)],
                    key="-SELECTED_INVALID-", size=(30, 1)),
            sg.Text("选择新窗口:"),
            sg.Combo([], key="-SELECTED_NEW-", size=(30, 1)),
            ModernUIConfig.create_modern_button("刷新窗口", "-REFRESH_WINDOWS-", "secondary")
        ])
        
        # 按钮行
        layout.append([sg.HSeparator()])
        layout.append([
            ModernUIConfig.create_modern_button("手动重新绑定", "-MANUAL_REBIND-", "primary"),
            ModernUIConfig.create_modern_button("取消", "-CANCEL-", "secondary"),
            sg.Push(),
            sg.Text("提示: 选择建议表格中的行，然后点击手动重新绑定", 
                   font=fonts['small'], text_color=colors['text_secondary'])
        ])
        
        return layout
    
    def _handle_auto_rebind(self, task: Task) -> bool:
        """处理自动重新绑定"""
        try:
            results = self.smart_rebind_manager.auto_rebind_windows(task)
            
            success_count = sum(1 for _, _, status in results if status == 'auto_success')
            total_count = len(results)
            
            if success_count > 0:
                sg.popup(f"自动重新绑定完成！\n\n成功: {success_count}/{total_count}", title="成功")
                return True
            else:
                sg.popup("自动重新绑定失败，请尝试手动重新绑定。", title="失败")
                return False
        
        except Exception as e:
            sg.popup(f"自动重新绑定出错: {e}", title="错误")
            return False
    
    def _handle_manual_rebind(self, task: Task, invalid_windows: List[BoundWindow], values: Dict) -> bool:
        """处理手动重新绑定"""
        try:
            # 获取选择的失效窗口
            selected_invalid = values.get("-SELECTED_INVALID-")
            if not selected_invalid:
                sg.popup("请选择要替换的失效窗口", title="提示")
                return False
            
            invalid_index = int(selected_invalid.split('.')[0]) - 1
            if invalid_index < 0 or invalid_index >= len(invalid_windows):
                sg.popup("选择的失效窗口无效", title="错误")
                return False
            
            invalid_window = invalid_windows[invalid_index]
            
            # 检查是否从建议表格中选择了窗口
            suggestion_selected = False
            new_hwnd = None
            
            for key, value in values.items():
                if key.startswith("-SUGGESTIONS_") and value:
                    # 从建议表格获取选择
                    hwnd_str = key.replace("-SUGGESTIONS_", "").replace("-", "")
                    suggestions = self.smart_rebind_manager.suggest_replacements(invalid_window)
                    if value and value[0] < len(suggestions):
                        new_hwnd = suggestions[value[0]].window_hwnd
                        suggestion_selected = True
                        break
            
            if not suggestion_selected:
                # 从手动选择下拉框获取
                selected_new = values.get("-SELECTED_NEW-")
                if not selected_new:
                    sg.popup("请选择新窗口或在建议表格中选择一行", title="提示")
                    return False
                
                # 解析窗口句柄
                try:
                    new_hwnd = int(selected_new.split('(')[1].split(')')[0])
                except:
                    sg.popup("新窗口选择格式错误", title="错误")
                    return False
            
            # 执行手动重新绑定
            success = self.smart_rebind_manager.manual_rebind_window(
                task, invalid_window.hwnd, new_hwnd
            )
            
            if success:
                sg.popup("手动重新绑定成功！", title="成功")
                return True
            else:
                sg.popup("手动重新绑定失败", title="失败")
                return False
        
        except Exception as e:
            sg.popup(f"手动重新绑定出错: {e}", title="错误")
            return False
    
    def _handle_suggestion_click(self, event: str, values: Dict):
        """处理建议点击"""
        # 这里可以添加额外的建议点击处理逻辑
        pass
    
    def _refresh_available_windows(self):
        """刷新可用窗口列表"""
        if not self.window:
            return
        
        try:
            windows = self.smart_rebind_manager.window_manager.enumerate_windows()
            window_options = [
                f"{w.title} ({w.hwnd})" for w in windows
            ]
            
            self.window["-SELECTED_NEW-"].update(values=window_options)
        
        except Exception as e:
            print(f"刷新窗口列表失败: {e}")