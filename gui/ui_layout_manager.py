"""
UI布局管理器模块

负责主窗口的布局创建和窗口配置逻辑
从MainWindow中提取，遵循单一职责原则
"""

from typing import List, Any, Dict, Optional
from abc import ABC, abstractmethod

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    print("运行: pip install FreeSimpleGUI")
    raise

from gui.modern_config import ModernUIConfig


class ILayoutManager(ABC):
    """布局管理器接口"""
    
    @abstractmethod
    def create_layout(self) -> List[List[Any]]:
        """创建窗口布局"""
        pass
    
    @abstractmethod
    def create_window(self, layout: List[List[Any]]) -> sg.Window:
        """创建窗口"""
        pass
    
    @abstractmethod
    def setup_window_events(self, window: sg.Window) -> sg.Window:
        """设置窗口事件绑定"""
        pass


class ILayoutProvider(ABC):
    """布局提供器接口 - 定义UILayoutManager需要的回调方法"""
    
    @abstractmethod
    def get_window_state_manager(self):
        """获取窗口状态管理器"""
        pass


class UILayoutManager(ILayoutManager):
    """UI布局管理器实现"""
    
    def __init__(self, layout_provider: ILayoutProvider = None):
        """初始化UI布局管理器
        
        Args:
            layout_provider: 布局提供器接口实现（可选）
        """
        self.layout_provider = layout_provider
        
        # 布局配置
        self.table_headings = ["#", "任务", "窗口", "状态", "待机时间"]
        self.table_col_widths = [2, 12, 3, 3, 6]  # [编号, 任务名, 窗口数, 状态, 待机时间]
        self.table_rows = 5
        
        print("✓ UI布局管理器初始化完成")
    
    def create_layout(self) -> List[List[Any]]:
        """创建现代化Widget布局"""
        colors = ModernUIConfig.COLORS
        fonts = ModernUIConfig.FONTS
        
        # 状态行 - 保持全局拖拽功能
        status_row = self._create_status_row(colors, fonts)
        
        # 任务表格行
        table_row = self._create_table_row()
        
        # 按钮行
        button_row = self._create_button_row()
        
        # 底部状态行
        bottom_row = self._create_bottom_row(colors, fonts)
        
        # 组装完整布局
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
    
    def _create_status_row(self, colors: Dict[str, str], fonts: Dict[str, tuple]) -> List[Any]:
        """创建状态行"""
        return [
            sg.Text("", key="-STATUS-", font=fonts['body'], 
                   text_color=colors['text_secondary']),
            sg.Push(),
            sg.Text("●", key="-INDICATOR-", font=("Segoe UI", 12), 
                   text_color=colors['success'], tooltip="就绪"),
            sg.Button("✕", key="-CLOSE-", size=(1, 1), 
                     button_color=(colors['text'], colors['error']),
                     font=("Segoe UI", 10), border_width=0, tooltip="关闭")
        ]
    
    def _create_table_row(self) -> List[Any]:
        """创建任务表格行"""
        table_data = []
        
        # 创建精确控制宽度的表格
        compact_table = ModernUIConfig.create_modern_table(
            values=table_data,
            headings=self.table_headings,
            key="-TASK_TABLE-",
            num_rows=self.table_rows,
            col_widths=self.table_col_widths
        )
        
        # 确保表格不会扩展
        compact_table.expand_x = False
        compact_table.expand_y = False
        
        return [compact_table]
    
    def _create_button_row(self) -> List[Any]:
        """创建按钮行"""
        return [
            ModernUIConfig.create_modern_button("＋", "-ADD_TASK-", "success", (2, 1), "添加任务"),
            ModernUIConfig.create_modern_button("✎", "-EDIT_TASK-", "primary", (2, 1), "编辑任务"),
            ModernUIConfig.create_modern_button("✕", "-DELETE_TASK-", "error", (2, 1), "删除任务"),
            sg.Text("", size=(1, 1)),  # 小分隔符
            ModernUIConfig.create_modern_button("↻", "-REFRESH-", "secondary", (2, 1), "刷新"),
            ModernUIConfig.create_modern_button("⚙", "-SETTINGS-", "warning", (2, 1), "设置")
        ]
    
    def _create_bottom_row(self, colors: Dict[str, str], fonts: Dict[str, tuple]) -> List[Any]:
        """创建底部状态行"""
        return [
            sg.Text("", key="-MAIN_STATUS-", font=fonts['small'], 
                   text_color=colors['text_secondary'], size=(8, 1)),
            sg.Text("C+A+空格", font=fonts['small'], 
                   text_color=colors['text_disabled'], size=(8, 1))
        ]
    
    def create_window(self, layout: List[List[Any]]) -> sg.Window:
        """创建现代化Widget窗口"""
        # 获取现代化Widget配置
        window_config = ModernUIConfig.get_widget_window_config()
        window_config['layout'] = layout
        
        # 窗口位置设置
        if self.layout_provider:
            window_state_manager = self.layout_provider.get_window_state_manager()
            if window_state_manager:
                restored_position = window_state_manager.restore_position()
                if restored_position:
                    window_config["location"] = restored_position
        
        # 创建窗口
        window = sg.Window(**window_config)
        
        return window
    
    def setup_window_events(self, window: sg.Window) -> sg.Window:
        """设置窗口事件绑定"""
        try:
            # 保存表格组件引用并绑定双击事件
            table_widget = window["-TASK_TABLE-"]
            table_widget.bind('<Double-Button-1>', ' Double')
            
            print("✓ 窗口事件绑定完成")
            return window
            
        except Exception as e:
            print(f"设置窗口事件失败: {e}")
            return window
    
    def get_table_widget(self, window: sg.Window) -> Optional[Any]:
        """获取表格组件"""
        try:
            return window["-TASK_TABLE-"]
        except Exception as e:
            print(f"获取表格组件失败: {e}")
            return None
    
    def update_table_config(self, headings: List[str] = None, 
                           col_widths: List[int] = None, 
                           num_rows: int = None) -> None:
        """更新表格配置
        
        Args:
            headings: 表格标题列表
            col_widths: 列宽列表
            num_rows: 行数
        """
        if headings:
            self.table_headings = headings
            print(f"✓ 表格标题更新为: {headings}")
        
        if col_widths:
            self.table_col_widths = col_widths
            print(f"✓ 表格列宽更新为: {col_widths}")
        
        if num_rows and num_rows > 0:
            self.table_rows = num_rows
            print(f"✓ 表格行数更新为: {num_rows}")
    
    def get_layout_config(self) -> Dict[str, Any]:
        """获取布局配置信息（用于调试）"""
        return {
            "table_headings": self.table_headings,
            "table_col_widths": self.table_col_widths,
            "table_rows": self.table_rows,
            "has_layout_provider": self.layout_provider is not None
        }
    
    def validate_layout(self, layout: List[List[Any]]) -> bool:
        """验证布局结构"""
        try:
            if not layout or not isinstance(layout, list):
                return False
            
            # 检查是否包含必要的组件
            has_column = False
            for row in layout:
                if isinstance(row, list):
                    for element in row:
                        if hasattr(element, '__class__') and 'Column' in str(element.__class__):
                            has_column = True
                            break
                if has_column:
                    break
            
            return has_column
            
        except Exception as e:
            print(f"验证布局失败: {e}")
            return False