"""
任务管理模块

负责管理开发任务和窗口绑定:
- 任务的创建、编辑、删除
- 多窗口绑定管理
- 任务切换逻辑
- 时间戳更新
- 任务状态管理
"""

import time
import uuid
import os
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from core.window_manager import WindowManager, WindowInfo
from core.explorer_helper import ExplorerHelper
from core.time_tracker import get_time_tracker, TimeTracker
from core.app_helpers import get_app_helper_registry, AppHelperRegistry


class TaskStatus(Enum):
    """任务状态枚举"""
    TODO = "todo"           # 待办
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"     # 已阻塞
    REVIEW = "review"       # 待审查
    COMPLETED = "completed" # 已完成
    PAUSED = "paused"       # 已暂停


@dataclass
class BoundWindow:
    """绑定的窗口信息"""
    hwnd: int              # 窗口句柄
    title: str             # 窗口标题
    process_name: str      # 进程名
    binding_time: str      # 绑定时间
    is_valid: bool = True  # 窗口是否仍然有效
    folder_path: Optional[str] = None  # Explorer窗口的文件夹路径
    window_rect: Optional[Tuple[int, int, int, int]] = None  # 窗口位置和大小 (left, top, right, bottom)

    # v1.2.0 新增字段：智能窗口恢复支持
    app_type: Optional[str] = None           # 应用类型: 'explorer', 'terminal', 'vscode', 'generic'
    working_directory: Optional[str] = None  # 工作目录 (Terminal/VS Code)
    terminal_profile: Optional[str] = None   # Terminal配置文件名 (PowerShell, cmd, bash等)

    def get_restore_context(self) -> Dict[str, Any]:
        """获取窗口恢复所需的上下文信息"""
        return {
            'app_type': self.app_type,
            'folder_path': self.folder_path,
            'working_directory': self.working_directory,
            'terminal_profile': self.terminal_profile,
            'window_rect': self.window_rect,
        }


@dataclass
class Task:
    """任务数据类"""
    id: str                           # 任务唯一ID
    name: str                         # 任务名称
    description: str = ""             # 任务描述
    status: TaskStatus = TaskStatus.TODO  # 任务状态
    bound_windows: List[BoundWindow] = field(default_factory=list)  # 绑定的窗口
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())  # 创建时间
    last_accessed: str = ""           # 最后访问时间
    access_count: int = 0             # 访问次数
    tags: List[str] = field(default_factory=list)  # 标签
    priority: int = 0                 # 优先级 (0=普通, 1=低, 2=中, 3=高)
    notes: str = ""                   # 快速笔记
    total_time_seconds: int = 0       # 总专注时间(秒)
    wave_workspace: Optional[str] = None  # 绑定的 Wave workspace 名称（可选）
    todo_items: List[Dict[str, Any]] = field(default_factory=list)  # 任务级 Todo 列表
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.last_accessed:
            self.last_accessed = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """从字典创建任务"""
        data = data.copy()

        # 处理状态枚举
        if 'status' in data and isinstance(data['status'], str):
            try:
                data['status'] = TaskStatus(data['status'])
            except ValueError:
                data['status'] = TaskStatus.TODO

        # 处理任务 Todo（向后兼容旧格式）
        data['todo_items'] = cls._normalize_todo_items(data.get('todo_items', []))
        
        # 处理绑定窗口
        if 'bound_windows' in data:
            windows = []
            for window_data in data['bound_windows']:
                if isinstance(window_data, dict):
                    # 确保新字段有默认值（向后兼容性）
                    # v1.1.0 字段
                    if 'folder_path' not in window_data:
                        window_data['folder_path'] = None
                    if 'window_rect' not in window_data:
                        window_data['window_rect'] = None
                    # v1.2.0 新增字段
                    if 'app_type' not in window_data:
                        # 从进程名自动推断 app_type
                        process_name = window_data.get('process_name', '').lower()
                        if process_name == 'explorer.exe':
                            window_data['app_type'] = 'explorer'
                        elif process_name in ('windowsterminal.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'):
                            window_data['app_type'] = 'terminal'
                        elif process_name == 'code.exe':
                            window_data['app_type'] = 'vscode'
                        else:
                            window_data['app_type'] = 'generic'
                    if 'working_directory' not in window_data:
                        window_data['working_directory'] = None
                    if 'terminal_profile' not in window_data:
                        window_data['terminal_profile'] = None
                    windows.append(BoundWindow(**window_data))
                else:
                    windows.append(window_data)
            data['bound_windows'] = windows
        
        return cls(**data)

    @staticmethod
    def _normalize_todo_items(raw_items: Any) -> List[Dict[str, Any]]:
        """标准化 todo_items，兼容历史数据格式。"""
        if not isinstance(raw_items, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in raw_items:
            text = ""
            completed = False

            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get('text', '')).strip()
                completed = bool(item.get('completed', item.get('done', False)))
            elif item is not None:
                text = str(item).strip()

            if not text:
                continue

            normalized.append({
                "text": text,
                "completed": completed
            })

        return normalized


class TaskManager:
    """任务管理器"""

    def __init__(self, window_manager: Optional[WindowManager] = None):
        """初始化任务管理器

        Args:
            window_manager: 窗口管理器实例
        """
        self.window_manager = window_manager or WindowManager()
        self.explorer_helper = ExplorerHelper()
        self.app_helper_registry = get_app_helper_registry()  # 智能窗口恢复辅助类注册表
        self.tasks: List[Task] = []
        self.current_task_index: int = -1
        self.max_tasks = 9  # 最多支持9个任务（对应数字键1-9）

        # 时间追踪器
        self.time_tracker: TimeTracker = get_time_tracker()

        # 事件回调
        self.on_task_added = None
        self.on_task_removed = None
        self.on_task_updated = None
        self.on_task_switched = None
    
    def generate_task_id(self) -> str:
        """生成唯一的任务ID"""
        timestamp = str(int(time.time() * 1000))
        return f"task_{timestamp}"
    
    def add_task(self, name: str, description: str = "", 
                 window_hwnds: List[int] = None) -> Optional[Task]:
        """添加新任务
        
        Args:
            name: 任务名称
            description: 任务描述
            window_hwnds: 要绑定的窗口句柄列表
            
        Returns:
            创建的任务对象，如果失败则返回None
        """
        if len(self.tasks) >= self.max_tasks:
            print(f"任务数量已达上限 {self.max_tasks}")
            return None
        
        if not name.strip():
            print("任务名称不能为空")
            return None
        
        # 检查名称是否重复
        if any(task.name == name for task in self.tasks):
            print(f"任务名称 '{name}' 已存在")
            return None
        
        # 创建任务
        task = Task(
            id=self.generate_task_id(),
            name=name.strip(),
            description=description.strip()
        )
        
        # 绑定窗口
        if window_hwnds:
            self._bind_windows_to_task(task, window_hwnds)
        
        self.tasks.append(task)
        
        # 触发事件回调
        if self.on_task_added:
            self.on_task_added(task)
        
        print(f"✓ 已添加任务: {name}")
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功删除
        """
        task_index = self._find_task_index(task_id)
        if task_index == -1:
            print(f"任务不存在: {task_id}")
            return False
        
        task = self.tasks[task_index]
        
        # 如果删除的是当前任务，重置当前任务索引
        if task_index == self.current_task_index:
            self.current_task_index = -1
        elif task_index < self.current_task_index:
            self.current_task_index -= 1
        
        # 删除任务
        removed_task = self.tasks.pop(task_index)
        
        # 触发事件回调
        if self.on_task_removed:
            self.on_task_removed(removed_task)
        
        print(f"✓ 已删除任务: {removed_task.name}")
        return True
    
    def edit_task(self, task_id: str, name: str = None, description: str = None,
                  status: TaskStatus = None, window_hwnds: List[int] = None,
                  priority: int = None, notes: str = None,
                  wave_workspace: Optional[str] = None,
                  tags: List[str] = None) -> bool:
        """编辑任务

        Args:
            task_id: 任务ID
            name: 新的任务名称
            description: 新的任务描述
            status: 新的任务状态
            window_hwnds: 新的窗口绑定列表
            priority: 新的优先级 (0=普通, 1=低, 2=中, 3=高)
            notes: 新的快速笔记
            tags: 新的标签列表

        Returns:
            是否成功编辑
        """
        task = self._find_task(task_id)
        if not task:
            print(f"任务不存在: {task_id}")
            return False

        changed = False

        # 更新名称
        if name is not None and name.strip() != task.name:
            # 检查新名称是否重复
            if any(t.name == name.strip() for t in self.tasks if t.id != task_id):
                print(f"任务名称 '{name}' 已存在")
                return False
            task.name = name.strip()
            changed = True

        # 更新描述
        if description is not None and description.strip() != task.description:
            task.description = description.strip()
            changed = True

        # 更新状态
        if status is not None and status != task.status:
            task.status = status
            changed = True

        # 更新优先级
        if priority is not None and priority != task.priority:
            task.priority = priority
            changed = True

        # 更新笔记
        if notes is not None and notes != task.notes:
            task.notes = notes
            changed = True

        # 更新 Wave workspace
        if wave_workspace is not None:
            normalized_workspace = wave_workspace.strip() if isinstance(wave_workspace, str) else None
            if normalized_workspace == "":
                normalized_workspace = None
            if normalized_workspace != task.wave_workspace:
                task.wave_workspace = normalized_workspace
                changed = True

        # 更新标签
        if tags is not None and tags != task.tags:
            task.tags = tags
            changed = True

        # 更新窗口绑定
        if window_hwnds is not None:
            task.bound_windows.clear()
            self._bind_windows_to_task(task, window_hwnds)
            changed = True

        if changed:
            # 触发事件回调
            if self.on_task_updated:
                self.on_task_updated(task)

            print(f"✓ 已更新任务: {task.name}")

        return True
    
    def switch_to_task(self, index: int) -> bool:
        """切换到指定任务（支持中止机制和时间追踪）

        Args:
            index: 任务索引 (0-8 对应热键 1-9)

        Returns:
            是否成功切换
        """
        if not (0 <= index < len(self.tasks)):
            print(f"任务索引无效: {index} (总共 {len(self.tasks)} 个任务)")
            return False

        task = self.tasks[index]

        # 生成独特的切换ID
        switch_id = str(uuid.uuid4())[:8]

        print(f"正在切换到任务: {task.name} (ID: {switch_id})")

        # 中止当前正在进行的切换
        aborted_previous = self.window_manager.abort_current_switch(switch_id)
        if aborted_previous:
            print(f"⚠️ 已中止上一个切换操作")

        # 记录上一个任务的时间
        if self.current_task_index >= 0 and self.current_task_index < len(self.tasks):
            prev_task = self.tasks[self.current_task_index]
            # 结束上一个任务的计时并更新累计时间
            if self.time_tracker.current_session:
                ended_session = self.time_tracker.end_session()
                if ended_session:
                    prev_task.total_time_seconds += ended_session.duration_seconds

        # 更新访问信息
        task.last_accessed = datetime.now().isoformat()
        task.access_count += 1
        self.current_task_index = index

        # 开始新任务的计时
        self.time_tracker.start_session(task.id, task.name)

        # 切换 Wave workspace（如果有配置）
        self._switch_wave_workspace_for_task(task)

        # 验证绑定的窗口
        valid_windows = self._validate_bound_windows(task)

        if not valid_windows:
            print(f"警告: 任务 '{task.name}' 没有有效的绑定窗口")
            return False

        # 激活所有有效窗口（带上切换ID）
        hwnds = [w.hwnd for w in valid_windows]
        results = self.window_manager.activate_multiple_windows(hwnds, switch_id=switch_id)

        success_count = sum(1 for success in results.values() if success)
        print(f"任务切换完成: {success_count}/{len(hwnds)} 个窗口成功激活 (ID: {switch_id})")

        # 触发事件回调
        if self.on_task_switched:
            self.on_task_switched(task, index)

        # 如果有任何窗口激活成功，就认为切换成功
        return success_count > 0

    def _switch_wave_workspace_for_task(self, task: Task) -> None:
        """根据任务配置切换 Wave workspace"""
        workspace_name = (task.wave_workspace or "").strip() if isinstance(task.wave_workspace, str) else ""
        if not workspace_name:
            return

        try:
            from utils.config import get_config
            config = get_config()
            wave_exe_path = config.get("integrations.wave.exe_path", "") or ""
        except Exception as e:
            print(f"⚠️ 读取 Wave 配置失败: {e}")
            return

        wave_exe_path = wave_exe_path.strip()
        if not wave_exe_path:
            print("⚠️ 未配置 Wave.exe 路径，跳过 Wave workspace 切换")
            return

        if not os.path.isfile(wave_exe_path):
            print(f"⚠️ Wave.exe 路径无效: {wave_exe_path}")
            return

        args = [wave_exe_path, f"--switch-workspace={workspace_name}"]
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )

        try:
            subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            print(f"✓ 已请求 Wave 切换 workspace: {workspace_name}")
        except Exception as e:
            print(f"⚠️ Wave workspace 切换失败: {e}")
    
    def get_task_by_index(self, index: int) -> Optional[Task]:
        """根据索引获取任务
        
        Args:
            index: 任务索引
            
        Returns:
            任务对象，如果不存在则返回None
        """
        if 0 <= index < len(self.tasks):
            return self.tasks[index]
        return None
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        return self._find_task(task_id)
    
    def get_task_by_name(self, name: str) -> Optional[Task]:
        """根据名称获取任务"""
        for task in self.tasks:
            if task.name == name:
                return task
        return None
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return self.tasks.copy()
    
    def get_current_task(self) -> Optional[Task]:
        """获取当前任务"""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def add_todo_item(self, task_id: str, text: str) -> bool:
        """为任务新增 Todo 项。"""
        task = self._find_task(task_id)
        if not task:
            return False

        todo_text = (text or "").strip()
        if not todo_text:
            return False

        task.todo_items.append({
            "text": todo_text,
            "completed": False
        })

        if self.on_task_updated:
            self.on_task_updated(task)

        return True

    def set_todo_item_completed(self, task_id: str, item_index: int, completed: bool) -> bool:
        """设置指定 Todo 项的完成状态。"""
        task = self._find_task(task_id)
        if not task:
            return False

        if not (0 <= item_index < len(task.todo_items)):
            return False

        item = task.todo_items[item_index]
        is_completed = bool(completed)
        if item.get("completed") == is_completed:
            return True

        item["completed"] = is_completed

        if self.on_task_updated:
            self.on_task_updated(task)

        return True

    def remove_completed_todo_items(self, task_id: str) -> int:
        """删除任务中所有已完成的 Todo 项，返回删除数量。"""
        task = self._find_task(task_id)
        if not task:
            return 0

        before_count = len(task.todo_items)
        if before_count == 0:
            return 0

        task.todo_items = [
            item for item in task.todo_items
            if not bool(item.get("completed", False))
        ]
        removed_count = before_count - len(task.todo_items)

        if removed_count > 0 and self.on_task_updated:
            self.on_task_updated(task)

        return removed_count
    
    def validate_all_tasks(self) -> Dict[str, List[str]]:
        """验证所有任务的窗口绑定
        
        Returns:
            验证结果 {task_id: [invalid_window_titles]}
        """
        results = {}
        
        for task in self.tasks:
            invalid_windows = []
            for window in task.bound_windows:
                if not self.window_manager.is_window_valid(window.hwnd):
                    window.is_valid = False
                    invalid_windows.append(window.title)
                else:
                    window.is_valid = True
            
            if invalid_windows:
                results[task.id] = invalid_windows
        
        return results
    
    def cleanup_invalid_windows(self) -> int:
        """清理所有任务中的无效窗口绑定
        
        Returns:
            清理的窗口数量
        """
        cleaned_count = 0
        
        for task in self.tasks:
            original_count = len(task.bound_windows)
            task.bound_windows = [
                w for w in task.bound_windows 
                if self.window_manager.is_window_valid(w.hwnd)
            ]
            cleaned_count += original_count - len(task.bound_windows)
        
        if cleaned_count > 0:
            print(f"✓ 已清理 {cleaned_count} 个无效窗口绑定")
        
        return cleaned_count
    
    def get_task_summary(self) -> Dict[str, Any]:
        """获取任务管理器状态摘要"""
        status_count = {}
        total_windows = 0
        valid_windows = 0
        
        for task in self.tasks:
            # 统计状态
            status = task.status.value
            status_count[status] = status_count.get(status, 0) + 1
            
            # 统计窗口
            total_windows += len(task.bound_windows)
            valid_windows += sum(1 for w in task.bound_windows if w.is_valid)
        
        return {
            "total_tasks": len(self.tasks),
            "current_task_index": self.current_task_index,
            "max_tasks": self.max_tasks,
            "status_distribution": status_count,
            "total_bound_windows": total_windows,
            "valid_bound_windows": valid_windows,
            "current_task": self.get_current_task().name if self.get_current_task() else None
        }
    
    def _find_task(self, task_id: str) -> Optional[Task]:
        """查找任务"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def _find_task_index(self, task_id: str) -> int:
        """查找任务索引"""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                return i
        return -1
    
    def _bind_windows_to_task(self, task: Task, window_hwnds: List[int]):
        """为任务绑定窗口（支持智能上下文提取）"""
        for hwnd in window_hwnds:
            window_info = self.window_manager.get_window_info(hwnd)
            if window_info:
                # 获取窗口位置信息
                window_rect = self.explorer_helper.get_window_rect(hwnd)

                # 检测应用类型并提取上下文
                app_type = self.app_helper_registry.detect_app_type(window_info.process_name)

                # 初始化上下文字段
                folder_path = None
                working_directory = None
                terminal_profile = None

                if app_type == 'explorer':
                    # Explorer窗口：使用专门的ExplorerHelper
                    if self.explorer_helper.is_explorer_window(hwnd):
                        folder_path = self.explorer_helper.get_explorer_folder_path(hwnd)
                        if folder_path:
                            print(f"  ✓ 检测到Explorer路径: {folder_path}")

                elif app_type in ('terminal', 'vscode'):
                    # Terminal/VS Code窗口：使用app_helper_registry提取上下文
                    context = self.app_helper_registry.extract_context(
                        hwnd, window_info.title, window_info.process_name
                    )
                    working_directory = context.get('working_directory')
                    terminal_profile = context.get('terminal_profile')

                    if working_directory:
                        print(f"  ✓ 检测到{app_type}工作目录: {working_directory}")
                    if terminal_profile:
                        print(f"  ✓ 检测到Terminal配置: {terminal_profile}")

                bound_window = BoundWindow(
                    hwnd=hwnd,
                    title=window_info.title,
                    process_name=window_info.process_name,
                    binding_time=datetime.now().isoformat(),
                    is_valid=True,
                    folder_path=folder_path,
                    window_rect=window_rect,
                    app_type=app_type,
                    working_directory=working_directory,
                    terminal_profile=terminal_profile,
                )
                task.bound_windows.append(bound_window)
                print(f"  ✓ 已绑定窗口: {window_info.title} (类型: {app_type})")
            else:
                print(f"  ✗ 无效窗口句柄: {hwnd}")
    
    def _validate_bound_windows(self, task: Task) -> List[BoundWindow]:
        """验证任务的绑定窗口，返回有效窗口列表（支持智能窗口恢复和自动重绑定）"""
        valid_windows = []
        windows_updated = False  # 标记是否有窗口被更新

        for window in task.bound_windows:
            if self.window_manager.is_window_valid(window.hwnd):
                window.is_valid = True
                valid_windows.append(window)
            else:
                window.is_valid = False
                print(f"  ✗ 窗口已失效: {window.title}")

                # 尝试智能恢复窗口
                new_hwnd = self._try_restore_window(window)

                if new_hwnd:
                    # 自动重绑定：更新窗口句柄和标题
                    old_hwnd = window.hwnd
                    window.hwnd = new_hwnd
                    window.is_valid = True
                    try:
                        import win32gui
                        window.title = win32gui.GetWindowText(new_hwnd)
                    except Exception:
                        pass
                    window.binding_time = datetime.now().isoformat()
                    valid_windows.append(window)
                    windows_updated = True
                    print(f"  ✓ 窗口已自动恢复并重绑定: {window.title}")

        # 如果有窗口被更新，触发任务更新事件以保存数据
        if windows_updated and self.on_task_updated:
            self.on_task_updated(task)

        return valid_windows

    def _try_restore_window(self, window: 'BoundWindow') -> Optional[int]:
        """尝试恢复失效的窗口

        根据窗口的 app_type 选择合适的恢复策略

        Args:
            window: 失效的绑定窗口

        Returns:
            新窗口句柄，失败返回 None
        """
        app_type = window.app_type or 'generic'
        context = window.get_restore_context()

        # Explorer 窗口：使用专门的 ExplorerHelper
        if app_type == 'explorer' or (
            window.folder_path and
            window.process_name and
            window.process_name.lower() == 'explorer.exe'
        ):
            print(f"  🔄 尝试恢复Explorer窗口: {window.folder_path}")

            if self.explorer_helper.restore_explorer_window(
                window.folder_path, window.window_rect
            ):
                # 查找新创建的Explorer窗口
                new_hwnd = self.explorer_helper._find_latest_explorer_window(
                    window.folder_path, timeout=2.0
                )
                if new_hwnd:
                    return new_hwnd

            print(f"  ✗ Explorer窗口恢复失败")
            return None

        # Terminal/VS Code 窗口：使用 app_helper_registry
        if app_type in ('terminal', 'vscode'):
            restore_path = context.get('working_directory') or context.get('folder_path')
            print(f"  🔄 尝试恢复{app_type}窗口: {restore_path}")

            # 检查是否可以恢复
            if not self.app_helper_registry.can_restore(app_type, context):
                print(f"  ✗ 无法恢复{app_type}窗口: 上下文信息不足")
                return None

            # 尝试恢复
            new_hwnd = self.app_helper_registry.restore_window(
                app_type, context, window.window_rect
            )

            if new_hwnd:
                return new_hwnd

            print(f"  ✗ {app_type}窗口恢复失败")
            return None

        # 其他类型窗口：暂不支持恢复
        return None
    
    def replace_window(self, task_id: str, old_hwnd: int, new_bound_window: BoundWindow) -> bool:
        """替换任务中的窗口绑定
        
        Args:
            task_id: 任务ID
            old_hwnd: 要替换的旧窗口句柄
            new_bound_window: 新的绑定窗口
            
        Returns:
            是否成功替换
        """
        task = self.get_task_by_id(task_id)
        if not task:
            return False
        
        # 查找要替换的窗口
        for i, window in enumerate(task.bound_windows):
            if window.hwnd == old_hwnd:
                # 替换窗口
                task.bound_windows[i] = new_bound_window
                print(f"✓ 已替换窗口: {window.title} -> {new_bound_window.title}")
                
                # 触发更新回调
                if self.on_task_updated:
                    self.on_task_updated(task)
                
                return True
        
        return False
