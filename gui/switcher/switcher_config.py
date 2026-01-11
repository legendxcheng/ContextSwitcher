"""
任务切换器配置管理模块

负责加载和管理任务切换器的配置：
- 窗口配置（尺寸、自动关闭延迟）
- 字体配置
- 颜色配置
"""

from typing import Tuple, Dict, Any
from gui.modern_config import ModernUIConfig


class SwitcherConfig:
    """任务切换器配置管理类"""

    # 默认字体配置
    DEFAULT_FONTS = {
        'task_title': ('Segoe UI', 12, 'bold'),    # 任务名称
        'task_info': ('Segoe UI', 10),             # 任务详情
        'hotkey': ('Segoe UI', 11, 'bold'),        # 快捷键编号
        'status': ('Segoe UI', 9, 'bold'),         # 状态信息
        'timestamp': ('Segoe UI', 8),              # 时间戳
        'instruction': ('Segoe UI', 9),            # 操作说明
    }

    def __init__(self):
        """初始化配置"""
        self._config = None
        self._switcher_config = None
        self._fonts = None
        self._colors = None

        self._load_config()

    def _load_config(self):
        """加载配置"""
        from utils.config import get_config
        self._config = get_config()
        self._switcher_config = self._config.get_task_switcher_config()

    @property
    def window_size(self) -> Tuple[int, int]:
        """窗口配置尺寸"""
        return tuple(self._switcher_config.get("window_size", [500, 200]))

    @property
    def auto_close_delay(self) -> float:
        """自动关闭延迟（秒）"""
        return self._switcher_config.get("auto_close_delay", 2.0)

    @property
    def show_empty_slots(self) -> bool:
        """是否显示空槽位"""
        return self._switcher_config.get("show_empty_slots", True)

    @property
    def enabled(self) -> bool:
        """是否启用任务切换器"""
        return self._switcher_config.get("enabled", True)

    @property
    def fonts(self) -> Dict[str, Any]:
        """字体配置"""
        if self._fonts is None:
            self._fonts = self.DEFAULT_FONTS.copy()
        return self._fonts

    @property
    def colors(self) -> Dict[str, str]:
        """颜色配置"""
        if self._colors is None:
            self._colors = ModernUIConfig.COLORS.copy()
        return self._colors

    def calculate_window_size(self, task_count: int) -> Tuple[int, int]:
        """根据任务数量计算窗口尺寸

        Args:
            task_count: 任务数量

        Returns:
            (width, height) 窗口尺寸
        """
        width = 500
        # 根据任务数量动态计算高度，每行约35像素
        base_height = 100  # 标题、分隔线、底部说明
        task_height = task_count * 35
        height = min(500, max(200, base_height + task_height))

        print(f"📏 窗口尺寸: {width}x{height}")
        return (width, height)

    def get_status_color(self, status) -> str:
        """获取状态对应的颜色

        Args:
            status: 任务状态对象

        Returns:
            颜色十六进制字符串
        """
        status_colors = {
            "todo": self.colors['text_secondary'],
            "in_progress": self.colors['primary'],
            "blocked": self.colors['warning'],
            "review": self.colors['warning'],
            "completed": self.colors['success'],
            "paused": self.colors['text_disabled']
        }
        return status_colors.get(status.value, self.colors['text'])

    def get_time_display(self, timestamp: str) -> str:
        """获取时间显示文本

        Args:
            timestamp: ISO格式时间戳

        Returns:
            格式化的时间显示文本
        """
        try:
            from datetime import datetime
            last_time = datetime.fromisoformat(timestamp)
            now = datetime.now()
            diff = now - last_time

            if diff.days > 0:
                return f"{diff.days}天前"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours}小时前"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes}分钟前"
            else:
                return "刚刚"
        except:
            return "未知"
