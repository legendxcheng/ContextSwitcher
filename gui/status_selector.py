"""
任务状态选择器UI组件

提供任务状态选择和管理界面:
- 状态下拉选择
- 状态可视化显示
- 状态转换验证
- 状态变更历史
"""

from typing import List, Optional, Dict, Any, Callable
import FreeSimpleGUI as sg
from datetime import datetime

from core.task_manager import Task, TaskStatus
from core.task_status_manager import TaskStatusManager
from gui.modern_config import ModernUIConfig


class StatusSelector:
    """任务状态选择器"""
    
    def __init__(self, task_status_manager: TaskStatusManager):
        """初始化状态选择器
        
        Args:
            task_status_manager: 状态管理器实例
        """
        self.status_manager = task_status_manager
        self.on_status_changed: Optional[Callable[[str, TaskStatus], None]] = None
        
        # 设置主题
        ModernUIConfig.setup_theme()
    
    def create_status_dropdown(self, current_status: TaskStatus, 
                             key_suffix: str = "", enabled: bool = True) -> sg.Combo:
        """创建状态下拉选择器
        
        Args:
            current_status: 当前状态
            key_suffix: 键名后缀
            enabled: 是否启用
            
        Returns:
            状态下拉组件
        """
        # 获取允许转换到的状态
        allowed_statuses = [current_status]  # 包含当前状态
        allowed_statuses.extend(self.status_manager.get_allowed_next_statuses(current_status))
        
        # 创建选项列表
        status_options = []
        for status in allowed_statuses:
            icon = self.status_manager.get_status_icon(status)
            name = self.status_manager.get_status_name(status)
            status_options.append(f"{icon} {name}")
        
        # 创建下拉组件
        current_display = f"{self.status_manager.get_status_icon(current_status)} {self.status_manager.get_status_name(current_status)}"
        
        return sg.Combo(
            values=status_options,
            default_value=current_display,
            key=f"-STATUS_COMBO{key_suffix}-",
            size=(12, 1),
            readonly=True,
            font=ModernUIConfig.FONTS['body'],
            enable_events=True,
            disabled=not enabled
        )
    
    def create_status_display(self, status: TaskStatus, size: tuple = (8, 1)) -> sg.Text:
        """创建状态显示文本
        
        Args:
            status: 任务状态
            size: 组件大小
            
        Returns:
            状态显示组件
        """
        icon = self.status_manager.get_status_icon(status)
        name = self.status_manager.get_status_name(status)
        color = self.status_manager.get_status_color(status)
        
        return sg.Text(
            f"{icon} {name}",
            size=size,
            font=ModernUIConfig.FONTS['body'],
            text_color=color,
            justification='center'
        )
    
    def show_status_change_dialog(self, task: Task) -> bool:
        """显示状态变更对话框
        
        Args:
            task: 要变更状态的任务
            
        Returns:
            是否进行了状态变更
        """
        current_status = task.status
        allowed_statuses = self.status_manager.get_allowed_next_statuses(current_status)
        
        if not allowed_statuses:
            sg.popup(f"当前状态 '{self.status_manager.get_status_name(current_status)}' 无法转换到其他状态", 
                    title="状态变更")
            return False
        
        # 创建对话框布局
        layout = self._create_status_change_layout(task, current_status, allowed_statuses)
        
        window = sg.Window(
            f"变更任务状态 - {task.name}",
            layout,
            modal=True,
            finalize=True,
            size=(500, 400)
        )
        
        status_changed = False
        
        try:
            while True:
                event, values = window.read()
                
                if event in (sg.WIN_CLOSED, "-CANCEL-"):
                    break
                elif event == "-OK-":
                    if self._handle_status_change(task, values):
                        status_changed = True
                        break
                elif event == "-SHOW_HISTORY-":
                    self._show_status_history(task)
        
        finally:
            window.close()
        
        return status_changed
    
    def _create_status_change_layout(self, task: Task, current_status: TaskStatus, 
                                   allowed_statuses: List[TaskStatus]) -> List[List[Any]]:
        """创建状态变更对话框布局"""
        colors = ModernUIConfig.COLORS
        fonts = ModernUIConfig.FONTS
        
        # 当前状态显示
        current_display = self.create_status_display(current_status, (15, 1))
        
        # 新状态选项
        status_options = []
        for status in allowed_statuses:
            icon = self.status_manager.get_status_icon(status)
            name = self.status_manager.get_status_name(status)
            status_options.append(f"{icon} {name}")
        
        layout = [
            # 标题
            [sg.Text(f"变更任务状态", font=fonts['heading'], text_color=colors['text'])],
            [sg.HSeparator()],
            
            # 任务信息
            [sg.Text("任务:", font=fonts['body']), 
             sg.Text(task.name, font=fonts['body'], text_color=colors['primary'])],
            [sg.Text("当前状态:", font=fonts['body']), current_display],
            
            [sg.HSeparator()],
            
            # 新状态选择
            [sg.Text("新状态:", font=fonts['body'])],
            [sg.Combo(status_options, key="-NEW_STATUS-", size=(20, 1), 
                     readonly=True, font=fonts['body'])],
            
            # 变更原因
            [sg.Text("变更原因:", font=fonts['body'])],
            [sg.Multiline("", key="-REASON-", size=(40, 3), font=fonts['body'])],
            
            # 用户备注
            [sg.Text("备注（可选）:", font=fonts['body'])],
            [sg.Multiline("", key="-COMMENT-", size=(40, 2), font=fonts['body'])],
            
            [sg.HSeparator()],
            
            # 按钮
            [sg.Button("变更状态", key="-OK-", font=fonts['button']),
             sg.Button("取消", key="-CANCEL-", font=fonts['button']),
             sg.Push(),
             sg.Button("查看历史", key="-SHOW_HISTORY-", font=fonts['button'])]
        ]
        
        return layout
    
    def _handle_status_change(self, task: Task, values: Dict[str, Any]) -> bool:
        """处理状态变更"""
        try:
            new_status_text = values.get("-NEW_STATUS-")
            if not new_status_text:
                sg.popup("请选择新状态", title="错误")
                return False
            
            # 解析选择的状态
            new_status = None
            for status in TaskStatus:
                icon = self.status_manager.get_status_icon(status)
                name = self.status_manager.get_status_name(status)
                if new_status_text == f"{icon} {name}":
                    new_status = status
                    break
            
            if not new_status:
                sg.popup("无效的状态选择", title="错误")
                return False
            
            reason = values.get("-REASON-", "").strip()
            comment = values.get("-COMMENT-", "").strip()
            
            # 执行状态变更
            success = self.status_manager.change_task_status(
                task.id, new_status, reason, comment
            )
            
            if success:
                sg.popup(f"状态已成功变更为: {self.status_manager.get_status_name(new_status)}", 
                        title="成功")
                
                # 触发回调
                if self.on_status_changed:
                    self.on_status_changed(task.id, new_status)
                
                return True
            else:
                sg.popup("状态变更失败", title="错误")
                return False
        
        except Exception as e:
            sg.popup(f"状态变更出错: {e}", title="错误")
            return False
    
    def _show_status_history(self, task: Task):
        """显示任务状态历史"""
        history = self.status_manager.get_task_status_history(task.id)
        
        if not history:
            sg.popup("该任务暂无状态变更历史", title="状态历史")
            return
        
        # 创建历史数据表格
        table_data = []
        for record in reversed(history):  # 最新的在前
            old_status_name = self.status_manager.get_status_name(record.old_status)
            new_status_name = self.status_manager.get_status_name(record.new_status)
            
            # 格式化时间
            try:
                dt = datetime.fromisoformat(record.timestamp)
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = record.timestamp[:16]
            
            table_data.append([
                time_str,
                f"{old_status_name} → {new_status_name}",
                record.reason[:30] + "..." if len(record.reason) > 30 else record.reason,
                record.user_comment[:20] + "..." if len(record.user_comment) > 20 else record.user_comment
            ])
        
        # 创建历史窗口
        layout = [
            [sg.Text(f"任务状态历史 - {task.name}", font=ModernUIConfig.FONTS['heading'])],
            [sg.HSeparator()],
            [sg.Table(
                values=table_data,
                headings=["时间", "状态变更", "原因", "备注"],
                key="-HISTORY_TABLE-",
                justification='left',
                alternating_row_color='lightgray',
                num_rows=min(10, len(table_data)),
                col_widths=[10, 15, 20, 15],
                auto_size_columns=False
            )],
            [sg.Button("关闭", key="-CLOSE-")]
        ]
        
        history_window = sg.Window(
            "状态历史",
            layout,
            modal=True,
            finalize=True,
            size=(600, 400)
        )
        
        try:
            while True:
                event, values = history_window.read()
                if event in (sg.WIN_CLOSED, "-CLOSE-"):
                    break
        finally:
            history_window.close()
    
    def parse_status_from_display(self, display_text: str) -> Optional[TaskStatus]:
        """从显示文本解析状态
        
        Args:
            display_text: 状态显示文本（如 "○ 待办"）
            
        Returns:
            解析出的状态，如果无法解析则返回None
        """
        for status in TaskStatus:
            icon = self.status_manager.get_status_icon(status)
            name = self.status_manager.get_status_name(status)
            if display_text == f"{icon} {name}":
                return status
        return None