"""
Visual Studio Code 窗口辅助模块

功能:
- 从窗口句柄获取进程实际工作目录
- 从窗口标题解析项目路径
- 恢复 VS Code 窗口到指定项目
"""

import os
import re
import time
import subprocess
from typing import Optional, Dict, List, Tuple, Any
from ctypes import windll, c_void_p, c_ulong, byref, c_size_t, c_wchar_p, Structure, POINTER, c_char
from ctypes.wintypes import DWORD, HANDLE, ULONG, PCHAR, WCHAR

import win32process
import win32api
import win32con

from .base_app_helper import BaseAppHelper

# 尝试导入 psutil，如果可用则使用它获取进程工作目录
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# Windows API 结构体定义
class PROCESS_BASIC_INFORMATION(Structure):
    # 对于 64 位系统:
    # - ExitStatus: 4 bytes (DWORD/ULONG)
    # - PebBaseAddress: 8 bytes (pointer)
    # - AffinityMask: 8 bytes (SIZE_T)
    # - BasePriority: 4 bytes (ULONG)
    # - UniqueProcessId: 8 bytes (ULONG_PTR)
    # - InheritedFromUniqueProcessId: 8 bytes (ULONG_PTR)
    _fields_ = [
        ('ExitStatus', c_ulong),
        ('PebBaseAddress', c_void_p),
        ('AffinityMask', c_size_t),
        ('BasePriority', c_ulong),
        ('UniqueProcessId', c_size_t),
        ('InheritedFromUniqueProcessId', c_size_t),
    ]


class UNICODE_STRING(Structure):
    _fields_ = [
        ('Length', c_ulong),
        ('MaximumLength', c_ulong),
        ('Buffer', c_void_p),
    ]


class PEB(Structure):
    _fields_ = [
        ('InheritedAddressSpace', c_ulong),
        ('ReadImageFileExecOptions', c_ulong),
        ('BeingDebugged', c_ulong),
        ('BitField', c_ulong),
        ('Padding0', c_ulong * 4),
        ('Mutant', c_void_p),
        ('ImageBaseAddress', c_void_p),
        ('Ldr', c_void_p),
        ('ProcessParameters', c_void_p),
        ('SubSystemData', c_void_p),
        ('ProcessHeap', c_void_p),
        ('RuntimeData', c_void_p),
        ('Pads0', c_ulong * 4),
        ('PreCommitData', c_void_p),
        ('Padding1', c_ulong * 44),
    ]


class RTL_USER_PROCESS_PARAMETERS(Structure):
    _fields_ = [
        ('MaximumLength', c_ulong),
        ('Length', c_ulong),
        ('Flags', c_ulong),
        ('DebugFlags', c_ulong),
        ('ConsoleHandle', c_void_p),
        ('ConsoleFlags', c_ulong),
        ('StandardInput', c_void_p),
        ('StandardOutput', c_void_p),
        ('StandardError', c_void_p),
        ('CurrentDirectoryPath', UNICODE_STRING),
        ('CurrentDirectoryHandle', c_void_p),
    ]


# 加载 ntdll
ntdll = windll.ntdll


class VSCodeHelper(BaseAppHelper):
    """Visual Studio Code 窗口辅助类

    支持 VS Code 窗口的上下文提取和恢复。
    通过解析窗口标题获取项目文件夹信息。
    """

    # 标题解析正则表达式模式
    TITLE_PATTERNS = [
        # 标准格式: "filename.py - ProjectFolder - Visual Studio Code"
        (r'^.+?\s+-\s+(.+?)\s+-\s+Visual Studio Code$', 'project_from_middle'),
        # 仅项目格式: "ProjectFolder - Visual Studio Code"
        (r'^(.+?)\s+-\s+Visual Studio Code$', 'project_name'),
        # 完整路径格式: "C:\path\to\file.py - Visual Studio Code"
        (r'^([A-Za-z]:\\[^<>:"|?*]+)\s+-\s+Visual Studio Code$', 'full_path'),
        # 无标题格式: "Visual Studio Code"
        (r'^Visual Studio Code$', 'no_project'),
    ]

    # 常见的项目根目录标记文件
    PROJECT_MARKERS = [
        '.git',
        'package.json',
        'setup.py',
        'pyproject.toml',
        'Cargo.toml',
        '.vscode',
        'pom.xml',
        'build.gradle',
    ]

    @property
    def app_type(self) -> str:
        return 'vscode'

    @property
    def process_names(self) -> List[str]:
        return ['code.exe']

    def is_supported_window(self, hwnd: int, process_name: str) -> bool:
        """检查是否为 VS Code 窗口"""
        return process_name.lower() in self.process_names

    def _get_process_working_directory(self, hwnd: int) -> Optional[str]:
        """获取 VSCode 进程的实际工作目录

        通过多种方法尝试获取 VSCode 的工作目录：
        1. 使用 psutil 获取进程工作目录（排除 VSCode 安装目录）
        2. 读取进程 PEB 获取当前目录（备选）
        3. 回退到标题解析

        Args:
            hwnd: 窗口句柄

        Returns:
            工作目录完整路径，失败返回 None
        """
        try:
            # 获取进程 ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # 方法1: 使用 psutil 获取进程工作目录（如果可用）
            if HAS_PSUTIL:
                try:
                    process = psutil.Process(pid)
                    cwd = process.cwd()
                    if cwd and os.path.isdir(cwd):
                        # 检查是否是 VSCode 安装目录（不是项目目录）
                        # VSCode 安装目录的特征：包含 Code.exe
                        if self._is_vscode_install_dir(cwd):
                            # 这是 VSCode 安装目录，不是项目目录，返回 None
                            # 让标题解析方法来处理
                            pass
                        else:
                            print(f"  ✓ 通过 psutil 获取工作目录: {cwd}")
                            return cwd
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    pass
                except Exception as e:
                    pass

            # 方法2: 尝试读取 PEB 中的当前工作目录
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, pid
            )

            if not process_handle:
                return None

            try:
                process_handle_int = int(process_handle)
                wd = self._read_working_directory_from_peb(process_handle_int)
                if wd:
                    if not self._is_vscode_install_dir(wd):
                        print(f"  ✓ 通过 PEB 获取工作目录: {wd}")
                        return wd
                return None

            finally:
                win32api.CloseHandle(process_handle)

        except Exception:
            # 静默失败，回退到标题解析
            return None

    def _is_vscode_install_dir(self, path: str) -> bool:
        """检查路径是否是 VSCode 安装目录

        VSCode 安装目录的特征：
        - 包含 Code.exe
        - 或者路径中包含 "Microsoft VS Code" 或 "Visual Studio Code"

        Args:
            path: 要检查的路径

        Returns:
            是否是 VSCode 安装目录
        """
        if not path:
            return False

        path_lower = path.lower()

        # 检查路径特征
        if 'microsoft vs code' in path_lower or 'visual studio code' in path_lower:
            return True

        # 检查是否包含 Code.exe
        code_exe_path = os.path.join(path, 'Code.exe')
        if os.path.exists(code_exe_path):
            return True

        return False

    def _read_working_directory_from_peb(self, process_handle: int) -> Optional[str]:
        """从进程 PEB 读取当前工作目录"""
        try:
            # 定义 ProcessBasicInformation (0)
            ProcessBasicInformation = 0

            # 初始化 PROCESS_BASIC_INFORMATION 结构
            pbi = PROCESS_BASIC_INFORMATION()
            return_length = c_ulong()

            status = ntdll.NtQueryInformationProcess(
                process_handle,
                ProcessBasicInformation,
                byref(pbi),
                c_size_t(sizeof(pbi)),
                byref(return_length)
            )

            if status != 0:
                return None

            # 读取 PEB 内容
            peb_buffer = (c_ulong * 16)()  # 64 字节
            bytes_read = c_size_t()

            if not windll.kernel32.ReadProcessMemory(
                process_handle,
                c_void_p(pbi.PebBaseAddress),
                peb_buffer,
                64,  # 直接使用整数
                byref(bytes_read)
            ):
                return None

            # ProcessParameters 指针在偏移 0x20 = 8 个 ULONG (每个 4 字节)
            # 在 64 位系统上，需要组合两个 ULONG 来获取完整地址
            process_params_addr = peb_buffer[8] | (peb_buffer[9] << 32)
            if process_params_addr == 0:
                return None

            # 读取 RTL_USER_PROCESS_PARAMETERS 结构
            params_buffer = (c_ulong * 32)()  # 128 字节

            if not windll.kernel32.ReadProcessMemory(
                process_handle,
                c_void_p(process_params_addr),
                params_buffer,
                128,
                byref(bytes_read)
            ):
                return None

            # CurrentDirectoryPath 在偏移 0x38 = 14 个 ULONG
            # UNICODE_STRING: Length(4), MaximumLength(4), Buffer(8)
            str_length = params_buffer[14]
            str_buffer_low = params_buffer[16]
            str_buffer_high = params_buffer[17]

            # 组合 64 位地址
            str_buffer = str_buffer_low | (str_buffer_high << 32)

            # 验证值是否合理
            if str_buffer == 0 or str_length == 0 or str_length > 0x2000:
                return None

            # 读取路径字符串
            char_count = (str_length // 2) + 1
            path_buffer = (WCHAR * char_count)()

            if not windll.kernel32.ReadProcessMemory(
                process_handle,
                c_void_p(str_buffer),
                byref(path_buffer),
                str_length + 2,
                byref(bytes_read)
            ):
                return None

            working_dir = path_buffer[:char_count - 1]

            if working_dir and os.path.isdir(working_dir):
                return working_dir

            return None

        except Exception:
            return None

    def _read_working_directory_from_cmdline(self, process_handle: int, pid: int) -> Optional[str]:
        """从进程命令行解析工作目录（暂未实现）"""
        return None

    def extract_context(self, hwnd: int, title: str) -> Dict[str, Any]:
        """从 VS Code 窗口提取上下文

        优先从进程 PEB 获取实际工作目录，失败时则从窗口标题解析项目路径。

        Args:
            hwnd: 窗口句柄
            title: 窗口标题

        Returns:
            上下文字典
        """
        context = {
            'app_type': self.app_type,
            'working_directory': None,
            'terminal_profile': None,  # VS Code 不使用此字段
        }

        if not title:
            return context

        # 优先：尝试通过进程 PEB 获取实际工作目录（最可靠）
        process_wd = self._get_process_working_directory(hwnd)
        if process_wd:
            context['working_directory'] = process_wd
            return context

        # 备选：从窗口标题解析（当进程方法失败时）
        # 尝试匹配各种标题模式
        for pattern, match_type in self.TITLE_PATTERNS:
            match = re.match(pattern, title, re.IGNORECASE)
            if match:
                if match_type == 'no_project':
                    # 无项目打开
                    break

                extracted = match.group(1).strip() if match.groups() else None

                if match_type == 'full_path' and extracted:
                    # 完整路径，提取目录部分
                    if os.path.isfile(extracted):
                        context['working_directory'] = os.path.dirname(extracted)
                    elif os.path.isdir(extracted):
                        context['working_directory'] = extracted

                elif match_type == 'project_from_middle' and extracted:
                    # 从中间部分提取项目名
                    # 可能是项目名或完整路径
                    resolved = self._resolve_project_path(extracted)
                    if resolved:
                        context['working_directory'] = resolved

                elif match_type == 'project_name' and extracted:
                    # 项目名或路径
                    resolved = self._resolve_project_path(extracted)
                    if resolved:
                        context['working_directory'] = resolved

                break

        return context

    def restore_window(
        self,
        context: Dict[str, Any],
        target_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> Optional[int]:
        """恢复 VS Code 窗口

        使用 code 命令行工具打开项目

        Args:
            context: 上下文信息
            target_rect: 目标窗口位置

        Returns:
            新窗口句柄，失败返回 None
        """
        project_path = context.get('working_directory')

        # 验证项目路径
        if not project_path:
            print("警告: 无法恢复 VS Code 窗口，缺少项目路径")
            return None

        if not os.path.exists(project_path):
            print(f"警告: 项目路径不存在: {project_path}")
            return None

        try:
            # 使用 code 命令打开项目
            # -n 表示打开新窗口（避免复用现有窗口）
            cmd = f'code -n "{project_path}"'

            subprocess.Popen(cmd, shell=True)

            # VS Code 启动较慢，增加等待时间
            time.sleep(1.0)

            # 查找新创建的窗口
            new_hwnd = self.find_matching_window(context, timeout=3.0)

            if new_hwnd and target_rect:
                self._position_window(new_hwnd, target_rect)

            return new_hwnd

        except Exception as e:
            print(f"恢复 VS Code 窗口失败: {e}")
            return None

    def _resolve_project_path(self, name_or_path: str) -> Optional[str]:
        """解析项目名称或路径到完整路径

        Args:
            name_or_path: 项目名称或路径

        Returns:
            完整路径，无法解析返回 None
        """
        # 如果已经是完整路径
        if os.path.isabs(name_or_path) and os.path.isdir(name_or_path):
            return name_or_path

        # 如果是文件路径，返回目录
        if os.path.isabs(name_or_path) and os.path.isfile(name_or_path):
            return os.path.dirname(name_or_path)

        # 尝试在常见位置查找项目
        search_paths = self._get_common_project_locations()

        # 收集所有匹配的候选路径
        candidates = []

        for base_path in search_paths:
            # 首先检查基础路径本身是否就是目标目录
            # 例如：base_path = 'E:\ContextSwitcher', name_or_path = 'ContextSwitcher'
            base_name = os.path.basename(base_path.rstrip(os.sep))
            if base_name == name_or_path:
                if os.path.isdir(base_path) and self._looks_like_project(base_path):
                    candidates.append(base_path)
                    continue  # 已经找到精确匹配，不需要再检查子目录

            # 然后检查基础路径下的子目录
            candidate = os.path.join(base_path, name_or_path)
            if os.path.isdir(candidate):
                # 验证是否看起来像项目目录
                if self._looks_like_project(candidate):
                    candidates.append(candidate)

        if not candidates:
            # 如果是相对路径样式的名称（如 "folder [ssh: server]"），提取文件夹名
            folder_match = re.match(r'^([^\[\]]+?)(?:\s*\[.+\])?$', name_or_path)
            if folder_match:
                folder_name = folder_match.group(1).strip()
                for base_path in search_paths:
                    candidate = os.path.join(base_path, folder_name)
                    if os.path.isdir(candidate):
                        candidates.append(candidate)

        if not candidates:
            return None

        # 如果有多个候选，优先选择非系统目���
        # 系统目录特征：包含 AppData、Temp、Program Files 等
        system_path_keywords = ['AppData', 'Application Data', 'Temp', 'Program Files', 'Windows', 'System32']
        non_system_candidates = []
        system_candidates = []

        for candidate in candidates:
            is_system = any(keyword.lower() in candidate.lower() for keyword in system_path_keywords)
            if is_system:
                system_candidates.append(candidate)
            else:
                non_system_candidates.append(candidate)

        # 优先返回非系统目录
        if non_system_candidates:
            return non_system_candidates[0]
        return system_candidates[0]

    def _get_common_project_locations(self) -> List[str]:
        """获取常见的项目存放位置

        Returns:
            目录路径列表
        """
        locations = []

        # 用户目录
        user_home = os.path.expanduser('~')

        # 常见的项目目录
        common_dirs = [
            'Projects',
            'projects',
            'Code',
            'code',
            'Development',
            'dev',
            'workspace',
            'repos',
            'GitHub',
            'Documents',
        ]

        for dir_name in common_dirs:
            path = os.path.join(user_home, dir_name)
            if os.path.isdir(path):
                locations.append(path)

        # 添加用户目录本身
        locations.append(user_home)

        # 新增：扫描用户主目录下的所有子目录（深度2层）
        # 这样可以找到不在预设目录中的项目
        try:
            for item in os.listdir(user_home):
                item_path = os.path.join(user_home, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    # 避免重复添加
                    if item_path not in locations:
                        locations.append(item_path)

                    # 扫描第二层目录（常见开发目录）
                    try:
                        for sub_item in os.listdir(item_path):
                            sub_path = os.path.join(item_path, sub_item)
                            if os.path.isdir(sub_path) and not sub_item.startswith('.'):
                                if sub_path not in locations:
                                    locations.append(sub_path)
                    except Exception:
                        pass
        except Exception:
            pass

        # 新增：检查其他驱动器的根目录
        # 例如 E:\, D:\ 等驱动器可能包含项目
        try:
            import string
            # 只扫描前几个驱动器，避免扫描太多
            for letter in string.ascii_uppercase[:5]:  # A-E
                drive = f'{letter}:'
                if os.path.exists(drive):
                    # 检查驱动器根目录下的常见项目文件夹
                    for dir_name in ['Projects', 'Code', 'Development', 'workspace', 'repos']:
                        drive_path = os.path.join(drive + '\\', dir_name)
                        if os.path.isdir(drive_path) and drive_path not in locations:
                            locations.append(drive_path)
                    # 检查驱动器根目录下是否有直接的项目文件夹
                    # 注意：必须使用 drive + '\\' 来获取根目录，而不是 drive
                    try:
                        root_path = drive + '\\'
                        for item in os.listdir(root_path):
                            if item.startswith('.'):
                                continue
                            item_path = os.path.join(root_path, item)
                            if os.path.isdir(item_path):
                                # 检查是否看起来像项目目录
                                if self._looks_like_project(item_path):
                                    if item_path not in locations:
                                        locations.append(item_path)
                                # 限制避免扫描太多目录
                                if len(locations) > 200:
                                    break
                        if len(locations) > 200:
                            break
                    except Exception:
                        pass
                if len(locations) > 200:
                    break
        except Exception:
            pass

        return locations

    def _looks_like_project(self, path: str) -> bool:
        """检查目录是否看起来像项目目录

        Args:
            path: 目录路径

        Returns:
            是否像项目目录
        """
        if not os.path.isdir(path):
            return False

        # 检查项目标记文件
        for marker in self.PROJECT_MARKERS:
            if os.path.exists(os.path.join(path, marker)):
                return True

        # 检查是否包含代码文件
        try:
            for item in os.listdir(path):
                if item.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.cs', '.go', '.rs')):
                    return True
        except Exception:
            pass

        return False

    def _calculate_context_match(
        self,
        hwnd: int,
        title: str,
        context: Dict[str, Any]
    ) -> float:
        """计算 VS Code 窗口与上下文的匹配度

        重写基类方法，增加 VS Code 特定的匹配逻辑
        """
        score = 0.0
        factors = 0

        working_dir = context.get('working_directory')

        if working_dir:
            factors += 1
            title_lower = title.lower()

            # 检查完整路径
            if working_dir.lower() in title_lower:
                score += 1.0
            else:
                # 检查文件夹名
                folder_name = os.path.basename(working_dir).lower()
                if folder_name and folder_name in title_lower:
                    score += 0.8

        # 确保是 VS Code 窗口
        if 'visual studio code' in title.lower():
            factors += 1
            score += 1.0

        return score / max(factors, 1)
