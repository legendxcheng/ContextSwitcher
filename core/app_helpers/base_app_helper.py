"""
应用窗口辅助抽象基类

定义所有应用辅助类的接口规范，包括：
- 窗口识别
- 上下文提取
- 窗口恢复
- 窗口匹配
"""

import time
import win32gui
import win32con
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, Any

from utils.screen_helper import ScreenHelper


class BaseAppHelper(ABC):
    """应用窗口辅助抽象基类

    所有特定应用的辅助类都应继承此类，实现以下核心方法：
    - app_type: 返回应用类型标识符
    - process_names: 返回支持的进程名列表
    - is_supported_window: 检查窗口是否由此辅助类处理
    - extract_context: 从窗口提取上下文信息
    - restore_window: 恢复窗口到指定上下文
    """

    def __init__(self):
        """初始化辅助类"""
        self.screen_helper = ScreenHelper()

    @property
    @abstractmethod
    def app_type(self) -> str:
        """返回应用类型标识符

        Returns:
            应用类型: 'explorer', 'terminal', 'vscode', 'generic'
        """
        pass

    @property
    @abstractmethod
    def process_names(self) -> List[str]:
        """返回此辅助类处理的进程名列表

        Returns:
            进程名列表（小写），如 ['windowsterminal.exe', 'powershell.exe']
        """
        pass

    @abstractmethod
    def is_supported_window(self, hwnd: int, process_name: str) -> bool:
        """检查窗口是否由此辅助类支持

        Args:
            hwnd: 窗口句柄
            process_name: 进程名

        Returns:
            是否支持此窗口
        """
        pass

    @abstractmethod
    def extract_context(self, hwnd: int, title: str) -> Dict[str, Any]:
        """从窗口提取上下文信息

        Args:
            hwnd: 窗口句柄
            title: 窗口标题

        Returns:
            上下文字典，包含:
            - working_directory: 工作目录
            - terminal_profile: Terminal配置名（如适用）
            - 其他应用特定信息
        """
        pass

    @abstractmethod
    def restore_window(
        self,
        context: Dict[str, Any],
        target_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[int]:
        """恢复窗口到指定上下文

        Args:
            context: 上下文信息字典
            target_rect: 目标窗口位置 (left, top, right, bottom)

        Returns:
            新窗口句柄，如果恢复失败返回None
        """
        pass

    def find_matching_window(
        self,
        context: Dict[str, Any],
        timeout: float = 2.0
    ) -> Optional[int]:
        """查找与上下文匹配的新创建窗口

        默认实现：在超时时间内轮询查找匹配的窗口

        Args:
            context: 上下文信息
            timeout: 超时时间（秒）

        Returns:
            匹配的窗口句柄，未找到返回None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 获取此应用类型的所有窗口
            windows = self._get_all_windows_by_process()

            for hwnd in windows:
                try:
                    title = win32gui.GetWindowText(hwnd)
                    score = self._calculate_context_match(hwnd, title, context)

                    if score >= 0.7:  # 匹配度阈值
                        return hwnd
                except Exception:
                    continue

            time.sleep(0.1)  # 短暂等待后重试

        # 备用：返回最新的窗口
        windows = self._get_all_windows_by_process()
        if windows:
            return windows[-1]

        return None

    def _get_all_windows_by_process(self) -> List[int]:
        """获取所有属于此应用类型的窗口句柄

        Returns:
            窗口句柄列表
        """
        result = []
        process_names_lower = [p.lower() for p in self.process_names]

        def enum_callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True

            try:
                import win32process
                import win32api

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False, pid
                )
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                win32api.CloseHandle(handle)

                exe_name = exe_path.split('\\')[-1].lower()
                if exe_name in process_names_lower:
                    result.append(hwnd)
            except Exception:
                pass

            return True

        win32gui.EnumWindows(enum_callback, None)
        return result

    def _calculate_context_match(
        self,
        hwnd: int,
        title: str,
        context: Dict[str, Any]
    ) -> float:
        """计算窗口与上下文的匹配度

        Args:
            hwnd: 窗口句柄
            title: 窗口标题
            context: 期望的上下文

        Returns:
            匹配度 0.0-1.0
        """
        score = 0.0
        factors = 0

        # 检查工作目录
        working_dir = context.get('working_directory')
        if working_dir:
            factors += 1
            title_lower = title.lower()
            working_dir_lower = working_dir.lower()

            if working_dir_lower in title_lower:
                score += 1.0
            elif working_dir.split('\\')[-1].lower() in title_lower:
                # 目录名匹配
                score += 0.7

        return score / max(factors, 1)

    def _position_window(
        self,
        hwnd: int,
        target_rect: Tuple[int, int, int, int]
    ) -> bool:
        """将窗口定位到指定位置

        Args:
            hwnd: 窗口句柄
            target_rect: 目标位置 (left, top, right, bottom)

        Returns:
            是否成功
        """
        try:
            if not target_rect:
                # 无位置信息，仅最大化
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return True

            # 获取目标位置所在的显示器
            target_point = (target_rect[0], target_rect[1])
            target_monitor = self.screen_helper.get_monitor_from_point(target_point)

            if target_monitor:
                work_area = target_monitor.get('work_rect')
                if work_area:
                    # 移动窗口到目标显示器的工作区域
                    win32gui.SetWindowPos(
                        hwnd, 0,
                        work_area[0], work_area[1],
                        work_area[2] - work_area[0],
                        work_area[3] - work_area[1],
                        win32con.SWP_NOZORDER
                    )

            # 最大化窗口
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

            # 确保窗口在前台
            win32gui.SetForegroundWindow(hwnd)

            return True

        except Exception as e:
            print(f"窗口定位失败: {e}")
            return False

    def get_window_rect(self, hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """获取窗口位置和大小

        Args:
            hwnd: 窗口句柄

        Returns:
            窗口矩形 (left, top, right, bottom)，失败返回None
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return rect
        except Exception:
            return None
