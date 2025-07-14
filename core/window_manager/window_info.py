"""
窗口信息数据类和常量定义

这个模块包含了窗口管理器中使用的核心数据结构和常量配置。
从原始的 window_manager.py 中提取，以实现数据与逻辑的分离。
"""

from dataclasses import dataclass
from typing import Tuple, Set


@dataclass
class WindowInfo:
    """窗口信息数据类
    
    包含窗口的所有基本属性和状态信息。
    """
    hwnd: int          # 窗口句柄
    title: str         # 窗口标题
    class_name: str    # 窗口类名
    process_id: int    # 进程ID
    process_name: str  # 进程名称
    is_visible: bool   # 是否可见
    is_enabled: bool   # 是否启用
    rect: Tuple[int, int, int, int]  # 窗口位置和大小 (left, top, right, bottom)


# 需要过滤的窗口类名（系统窗口等）
FILTERED_CLASSES: Set[str] = {
    'Shell_TrayWnd',        # 任务栏
    'DV2ControlHost',       # Windows 10开始菜单
    'Windows.UI.Core.CoreWindow',  # UWP应用容器
    'ApplicationFrameWindow',      # UWP应用框架
    'WorkerW',              # 桌面工作窗口
    'Progman',              # 程序管理器
    'Button',               # 按钮控件
    'Edit',                 # 编辑控件
    ''                      # 空类名
}

# 需要过滤的窗口标题
FILTERED_TITLES: Set[str] = {
    '',                     # 空标题
    'Program Manager',      # 程序管理器
    'Desktop',              # 桌面
}

# 缓存配置常量
DEFAULT_CACHE_DURATION = 2.0  # 默认缓存2秒

# 常见应用程序进程名（用于窗口分析）
COMMON_APPS: Set[str] = {
    'chrome.exe', 'firefox.exe', 'edge.exe',           # 浏览器
    'code.exe', 'devenv.exe', 'notepad++.exe',          # 编辑器
    'explorer.exe', 'cmd.exe', 'powershell.exe',       # 系统工具
    'wechat.exe', 'qq.exe', 'dingding.exe',             # 通讯工具
    'winword.exe', 'excel.exe', 'powerpnt.exe',        # Office
    'photoshop.exe', 'illustrator.exe',                # 设计工具
}