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
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from core.window_manager import WindowManager, WindowInfo
from core.explorer_helper import ExplorerHelper


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
        # 处理状态枚举
        if 'status' in data and isinstance(data['status'], str):
            try:
                data['status'] = TaskStatus(data['status'])
            except ValueError:
                data['status'] = TaskStatus.TODO
        
        # 处理绑定窗口
        if 'bound_windows' in data:
            windows = []
            for window_data in data['bound_windows']:
                if isinstance(window_data, dict):
                    # 确保新字段有默认值（向后兼容性）
                    if 'folder_path' not in window_data:
                        window_data['folder_path'] = None
                    if 'window_rect' not in window_data:
                        window_data['window_rect'] = None
                    windows.append(BoundWindow(**window_data))
                else:
                    windows.append(window_data)
            data['bound_windows'] = windows
        
        return cls(**data)


class TaskManager:
    """任务管理器"""
    
    def __init__(self, window_manager: Optional[WindowManager] = None):
        """初始化任务管理器
        
        Args:
            window_manager: 窗口管理器实例
        """
        self.window_manager = window_manager or WindowManager()
        self.explorer_helper = ExplorerHelper()
        self.tasks: List[Task] = []
        self.current_task_index: int = -1
        self.max_tasks = 9  # 最多支持9个任务（对应数字键1-9）
        
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
                  status: TaskStatus = None, window_hwnds: List[int] = None) -> bool:
        """编辑任务
        
        Args:
            task_id: 任务ID
            name: 新的任务名称
            description: 新的任务描述
            status: 新的任务状态
            window_hwnds: 新的窗口绑定列表
            
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
        """切换到指定任务（支持中止机制）
        
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
        
        # 更新访问信息
        task.last_accessed = datetime.now().isoformat()
        task.access_count += 1
        self.current_task_index = index
        
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
        """为任务绑定窗口"""
        for hwnd in window_hwnds:
            window_info = self.window_manager.get_window_info(hwnd)
            if window_info:
                # 获取窗口位置信息
                window_rect = self.explorer_helper.get_window_rect(hwnd)
                
                # 如果是Explorer窗口，获取文件夹路径
                folder_path = None
                if self.explorer_helper.is_explorer_window(hwnd):
                    folder_path = self.explorer_helper.get_explorer_folder_path(hwnd)
                    if folder_path:
                        print(f"  ✓ 检测到Explorer路径: {folder_path}")
                
                bound_window = BoundWindow(
                    hwnd=hwnd,
                    title=window_info.title,
                    process_name=window_info.process_name,
                    binding_time=datetime.now().isoformat(),
                    is_valid=True,
                    folder_path=folder_path,
                    window_rect=window_rect
                )
                task.bound_windows.append(bound_window)
                print(f"  ✓ 已绑定窗口: {window_info.title}")
            else:
                print(f"  ✗ 无效窗口句柄: {hwnd}")
    
    def _validate_bound_windows(self, task: Task) -> List[BoundWindow]:
        """验证任务的绑定窗口，返回有效窗口列表（支持Explorer窗口恢复）"""
        valid_windows = []
        
        for window in task.bound_windows:
            if self.window_manager.is_window_valid(window.hwnd):
                window.is_valid = True
                valid_windows.append(window)
            else:
                window.is_valid = False
                print(f"  ✗ 窗口已失效: {window.title}")
                
                # 如果是Explorer窗口且有路径信息，尝试恢复
                if (window.folder_path and 
                    window.process_name and 
                    window.process_name.lower() == 'explorer.exe'):
                    
                    print(f"  🔄 尝试恢复Explorer窗口: {window.folder_path}")
                    
                    if self.explorer_helper.restore_explorer_window(
                        window.folder_path, window.window_rect):
                        
                        print(f"  ✓ Explorer窗口恢复成功，请手动重新绑定")
                        # 注意：这里不更新window.hwnd，因为需要用户手动重新绑定新窗口
                    else:
                        print(f"  ✗ Explorer窗口恢复失败")
        
        return valid_windows
    
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