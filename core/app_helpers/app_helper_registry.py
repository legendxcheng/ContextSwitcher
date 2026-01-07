"""
应用辅助类注册表

提供统一的接口来管理和访问各应用辅助类:
- 自动注册所有辅助类
- 根据进程名或应用类型获取对应的辅助类
- 统一的上下文提取和窗口恢复接口
"""

from typing import Optional, Dict, List, Any, Tuple

from .base_app_helper import BaseAppHelper
from .terminal_helper import TerminalHelper
from .vscode_helper import VSCodeHelper


class AppHelperRegistry:
    """应用辅助类注册表

    管理所有应用辅助类的注册和查找。
    提供统一的接口来提取窗口上下文和恢复窗口。
    """

    def __init__(self):
        """初始化注册表并注册所有辅助类"""
        self._helpers: Dict[str, BaseAppHelper] = {}
        self._process_map: Dict[str, str] = {}  # 进程名 -> 应用类型

        # 注册内置辅助类
        self._register_builtin_helpers()

    def _register_builtin_helpers(self):
        """注册内置的应用辅助类"""
        # Terminal 辅助类
        self.register(TerminalHelper())

        # VS Code 辅助类
        self.register(VSCodeHelper())

    def register(self, helper: BaseAppHelper):
        """注册应用辅助类

        Args:
            helper: 应用辅助类实例
        """
        app_type = helper.app_type
        self._helpers[app_type] = helper

        # 建立进程名到应用类型的映射
        for process_name in helper.process_names:
            self._process_map[process_name.lower()] = app_type

    def get_helper_by_type(self, app_type: str) -> Optional[BaseAppHelper]:
        """根据应用类型获取辅助类

        Args:
            app_type: 应用类型 ('terminal', 'vscode' 等)

        Returns:
            辅助类实例，未找到返回 None
        """
        return self._helpers.get(app_type)

    def get_helper_by_process(self, process_name: str) -> Optional[BaseAppHelper]:
        """根据进程名获取辅助类

        Args:
            process_name: 进程名 (如 'Code.exe')

        Returns:
            辅助类实例，未找到返回 None
        """
        process_lower = process_name.lower()
        app_type = self._process_map.get(process_lower)

        if app_type:
            return self._helpers.get(app_type)

        return None

    def detect_app_type(self, process_name: str) -> str:
        """检测应用类型

        Args:
            process_name: 进程名

        Returns:
            应用类型 ('terminal', 'vscode', 'explorer', 'generic')
        """
        process_lower = process_name.lower()

        # 检查已注册的辅助类
        app_type = self._process_map.get(process_lower)
        if app_type:
            return app_type

        # Explorer 特殊处理（由 ExplorerHelper 处理，这里只做类型检测）
        if process_lower == 'explorer.exe':
            return 'explorer'

        return 'generic'

    def extract_context(
        self,
        hwnd: int,
        title: str,
        process_name: str
    ) -> Dict[str, Any]:
        """提取窗口上下文

        根据进程名自动选择合适的辅助类来提取上下文

        Args:
            hwnd: 窗口句柄
            title: 窗口标题
            process_name: 进程名

        Returns:
            上下文字典，包含 app_type 和应用特定信息
        """
        # 检测应用类型
        app_type = self.detect_app_type(process_name)

        # 基础上下文
        context = {
            'app_type': app_type,
            'working_directory': None,
            'terminal_profile': None,
        }

        # 获取对应的辅助类
        helper = self.get_helper_by_process(process_name)

        if helper:
            # 使用辅助类提取详细上下文
            extracted = helper.extract_context(hwnd, title)
            context.update(extracted)

        return context

    def restore_window(
        self,
        app_type: str,
        context: Dict[str, Any],
        target_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[int]:
        """恢复窗口

        Args:
            app_type: 应用类型
            context: 上下文信息
            target_rect: 目标窗口位置

        Returns:
            新窗口句柄，失败返回 None
        """
        helper = self.get_helper_by_type(app_type)

        if not helper:
            print(f"未找到应用类型 '{app_type}' 的辅助类")
            return None

        return helper.restore_window(context, target_rect)

    def can_restore(self, app_type: str, context: Dict[str, Any]) -> bool:
        """检查是否可以恢复窗口

        Args:
            app_type: 应用类型
            context: 上下文信息

        Returns:
            是否可以恢复
        """
        # 检查是否有对应的辅助类
        if app_type not in self._helpers:
            return False

        # 检查是否有足够的上下文信息
        working_dir = context.get('working_directory')

        if app_type == 'terminal':
            # Terminal 可以在没有工作目录的情况下恢复（使用默认目录）
            return True

        if app_type == 'vscode':
            # VS Code 需要项目路径
            return working_dir is not None

        return False

    def get_supported_app_types(self) -> List[str]:
        """获取所有支持的应用类型

        Returns:
            应用类型列表
        """
        return list(self._helpers.keys())

    def get_all_process_names(self) -> List[str]:
        """获取所有支持的进程名

        Returns:
            进程名列表
        """
        return list(self._process_map.keys())


# 全局单例
_registry_instance: Optional[AppHelperRegistry] = None


def get_app_helper_registry() -> AppHelperRegistry:
    """获取全局应用辅助类注册表实例

    Returns:
        AppHelperRegistry 单例实例
    """
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = AppHelperRegistry()

    return _registry_instance
