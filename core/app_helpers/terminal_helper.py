"""
Windows Terminal 窗口辅助模块

支持的应用:
- Windows Terminal (WindowsTerminal.exe)
- PowerShell (powershell.exe, pwsh.exe)
- 命令提示符 (cmd.exe)

功能:
- 从窗口标题解析工作目录和配置文件
- 恢复 Terminal 窗口到指定工作目录
"""

import os
import re
import time
import subprocess
from typing import Optional, Dict, List, Tuple, Any

from .base_app_helper import BaseAppHelper


class TerminalHelper(BaseAppHelper):
    """Windows Terminal 窗口辅助类

    支持 Windows Terminal、PowerShell、CMD 窗口的上下文提取和恢复。
    通过解析窗口标题获取工作目录和配置文件信息。
    """

    # 标题解析正则表达式模式
    TITLE_PATTERNS = [
        # Windows Terminal: "管理员: Windows PowerShell" 或 "C:\Users\Dev - PowerShell"
        (r'^(?:管理员:\s*)?(.+?)\s*-\s*(Windows PowerShell|PowerShell|pwsh|cmd)$', 'working_dir', 'profile'),
        # PowerShell: "管理员: C:\Windows\System32"
        (r'^(?:管理员:\s*)?([A-Za-z]:\\[^<>:"|?*]+)$', 'working_dir', None),
        # MINGW/Git Bash: "MINGW64:/c/Users/Dev"
        (r'^MINGW\d*:(.+)$', 'mingw_path', None),
        # 简单路径格式: "C:\Users\Dev"
        (r'^([A-Za-z]:\\[^<>:"|?*]*)$', 'working_dir', None),
        # VS Code Terminal: "Terminal - ProjectName"
        (r'^Terminal\s*-\s*(.+)$', 'project_name', None),
    ]

    # 配置文件名映射
    PROFILE_MAPPING = {
        'windows powershell': 'Windows PowerShell',
        'powershell': 'PowerShell',
        'pwsh': 'PowerShell',
        'cmd': 'Command Prompt',
        'command prompt': 'Command Prompt',
        'git bash': 'Git Bash',
        'bash': 'Git Bash',
        'ubuntu': 'Ubuntu',
        'wsl': 'Ubuntu',
    }

    @property
    def app_type(self) -> str:
        return 'terminal'

    @property
    def process_names(self) -> List[str]:
        return [
            'windowsterminal.exe',
            'powershell.exe',
            'pwsh.exe',
            'cmd.exe',
            'bash.exe',
            'wsl.exe',
        ]

    def is_supported_window(self, hwnd: int, process_name: str) -> bool:
        """检查是否为 Terminal 窗口"""
        return process_name.lower() in self.process_names

    def extract_context(self, hwnd: int, title: str) -> Dict[str, Any]:
        """从 Terminal 窗口提取上下文

        解析窗口标题以获取:
        - working_directory: 当前工作目录
        - terminal_profile: Terminal 配置文件名

        Args:
            hwnd: 窗口句柄
            title: 窗口标题

        Returns:
            上下文字典
        """
        context = {
            'app_type': self.app_type,
            'working_directory': None,
            'terminal_profile': None,
        }

        if not title:
            return context

        # 尝试匹配各种标题模式
        for pattern, dir_group, profile_group in self.TITLE_PATTERNS:
            match = re.match(pattern, title, re.IGNORECASE)
            if match:
                groups = match.groups()

                if dir_group == 'working_dir' and groups:
                    path = groups[0].strip()
                    # 验证路径是否存在
                    if os.path.isdir(path):
                        context['working_directory'] = path

                elif dir_group == 'mingw_path' and groups:
                    # 转换 MINGW 路径: /c/Users -> C:\Users
                    mingw_path = groups[0].strip()
                    windows_path = self._convert_mingw_path(mingw_path)
                    if windows_path and os.path.isdir(windows_path):
                        context['working_directory'] = windows_path

                elif dir_group == 'project_name' and groups:
                    # 尝试从项目名推断路径（有限支持）
                    project_name = groups[0].strip()
                    context['working_directory'] = project_name  # 保存名称，后续可能用于匹配

                # 提取配置文件名
                if profile_group and len(groups) > 1 and groups[1]:
                    profile = groups[1].strip().lower()
                    context['terminal_profile'] = self.PROFILE_MAPPING.get(
                        profile, profile.title()
                    )

                break

        # 如果标题中没有找到配置文件，尝试从进程名推断
        if not context['terminal_profile']:
            context['terminal_profile'] = self._infer_profile_from_title(title)

        return context

    def restore_window(
        self,
        context: Dict[str, Any],
        target_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[int]:
        """恢复 Terminal 窗口

        优先使用 Windows Terminal (wt.exe)，如果不可用则回退到直接启动 PowerShell/CMD

        Args:
            context: 上下文信息
            target_rect: 目标窗口位置

        Returns:
            新窗口句柄，失败返回 None
        """
        working_dir = context.get('working_directory')
        profile = context.get('terminal_profile', 'PowerShell')

        # 验证工作目录
        if working_dir and not os.path.isdir(working_dir):
            print(f"警告: 工作目录不存在: {working_dir}")
            working_dir = None

        try:
            # 方法1: 使用 Windows Terminal
            if self._try_restore_with_wt(working_dir, profile):
                time.sleep(0.5)
                new_hwnd = self.find_matching_window(context, timeout=2.0)
                if new_hwnd and target_rect:
                    self._position_window(new_hwnd, target_rect)
                return new_hwnd

        except Exception as e:
            print(f"使用 wt.exe 恢复失败: {e}")

        try:
            # 方法2: 直接启动 PowerShell/CMD（备用）
            if self._try_restore_direct(working_dir, profile):
                time.sleep(0.5)
                new_hwnd = self.find_matching_window(context, timeout=2.0)
                if new_hwnd and target_rect:
                    self._position_window(new_hwnd, target_rect)
                return new_hwnd

        except Exception as e:
            print(f"直接启动 Terminal 失败: {e}")

        return None

    def _try_restore_with_wt(self, working_dir: Optional[str], profile: str) -> bool:
        """使用 Windows Terminal 恢复窗口

        Args:
            working_dir: 工作目录
            profile: 配置文件名

        Returns:
            是否成功启动
        """
        # 构建命令
        cmd_parts = ['wt.exe']

        # 添加配置文件参数
        if profile:
            cmd_parts.extend(['-p', f'"{profile}"'])

        # 添加工作目录参数
        if working_dir:
            cmd_parts.extend(['-d', f'"{working_dir}"'])

        cmd = ' '.join(cmd_parts)

        # 执行命令
        result = subprocess.Popen(cmd, shell=True)
        return result.pid > 0

    def _try_restore_direct(self, working_dir: Optional[str], profile: str) -> bool:
        """直接启动 PowerShell 或 CMD（备用方法）

        Args:
            working_dir: 工作目录
            profile: 配置文件名

        Returns:
            是否成功启动
        """
        # 根据配置文件选择启动程序
        profile_lower = (profile or '').lower()

        if 'cmd' in profile_lower or 'command' in profile_lower:
            # 启动 CMD
            if working_dir:
                cmd = f'start cmd /K cd /d "{working_dir}"'
            else:
                cmd = 'start cmd'
        else:
            # 默认启动 PowerShell
            if working_dir:
                cmd = f'start powershell -NoExit -Command "Set-Location -Path \'{working_dir}\'"'
            else:
                cmd = 'start powershell'

        result = subprocess.Popen(cmd, shell=True)
        return result.pid > 0

    def _convert_mingw_path(self, mingw_path: str) -> Optional[str]:
        r"""将 MINGW 路径转换为 Windows 路径

        例如: /c/Users/Dev -> C:\Users\Dev

        Args:
            mingw_path: MINGW 格式路径

        Returns:
            Windows 格式路径，转换失败返回 None
        """
        try:
            # /c/Users/Dev -> C:\Users\Dev
            if mingw_path.startswith('/'):
                parts = mingw_path.split('/')
                if len(parts) >= 2 and len(parts[1]) == 1:
                    drive = parts[1].upper()
                    path = '\\'.join(parts[2:])
                    return f"{drive}:\\{path}"
            return None
        except Exception:
            return None

    def _infer_profile_from_title(self, title: str) -> Optional[str]:
        """从标题推断 Terminal 配置文件

        Args:
            title: 窗口标题

        Returns:
            配置文件名
        """
        title_lower = title.lower()

        if 'powershell' in title_lower:
            return 'Windows PowerShell'
        elif 'pwsh' in title_lower:
            return 'PowerShell'
        elif 'cmd' in title_lower or 'command' in title_lower:
            return 'Command Prompt'
        elif 'bash' in title_lower or 'mingw' in title_lower:
            return 'Git Bash'
        elif 'ubuntu' in title_lower or 'wsl' in title_lower:
            return 'Ubuntu'

        # 默认
        return 'Windows PowerShell'

    def _calculate_context_match(
        self,
        hwnd: int,
        title: str,
        context: Dict[str, Any]
    ) -> float:
        """计算 Terminal 窗口与上下文的匹配度

        重写基类方法，增加 Terminal 特定的匹配逻辑
        """
        score = 0.0
        factors = 0

        working_dir = context.get('working_directory')
        profile = context.get('terminal_profile')

        # 检查工作目录
        if working_dir:
            factors += 1
            title_lower = title.lower()
            dir_lower = working_dir.lower()

            if dir_lower in title_lower:
                score += 1.0
            elif working_dir.split('\\')[-1].lower() in title_lower:
                score += 0.7

        # 检查配置文件
        if profile:
            factors += 1
            if profile.lower() in title.lower():
                score += 1.0

        return score / max(factors, 1)
