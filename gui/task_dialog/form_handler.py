"""
任务表单处理器模块

负责表单数据验证、保存和加载
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.task_manager import TaskManager, Task, TaskStatus
from gui.task_dialog.status_converter import TaskStatusConverter


@dataclass
class TaskFormData:
    """任务表单数据"""
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: int = 0
    notes: str = ""
    wave_workspace: str = ""
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class TaskFormHandler:
    """任务表单处理器 - 负责验证和保存"""

    # 优先级文本到数值的映射
    PRIORITY_MAP = {
        "普通": 0,
        "低": 1,
        "中": 2,
        "高": 3
    }

    def __init__(self, task_manager: TaskManager):
        """初始化表单处理器

        Args:
            task_manager: 任务管理器
        """
        self.task_manager = task_manager
        self.status_converter = TaskStatusConverter()

        # 当前表单数据
        self.form_data = TaskFormData()

        # 编辑模式标识
        self._editing_task_id: Optional[str] = None

    def reset_form(self) -> None:
        """重置表单数据"""
        self.form_data = TaskFormData()
        self._editing_task_id = None

    def load_task(self, task: Task) -> None:
        """加载任务数据到表单

        Args:
            task: 要加载的任务
        """
        self._editing_task_id = task.id
        self.form_data = TaskFormData(
            name=task.name,
            description=task.description,
            status=task.status,
            priority=getattr(task, 'priority', 0),
            notes=getattr(task, 'notes', ""),
            wave_workspace=getattr(task, 'wave_workspace', "") or "",
            tags=getattr(task, 'tags', []) or []
        )

    def save_from_values(self, values: Dict[str, Any]) -> None:
        """从表单值保存数据

        Args:
            values: 表单值字典
        """
        self.form_data.name = values.get("-TASK_NAME-", "").strip()
        self.form_data.description = values.get("-TASK_DESC-", "").strip()
        self.form_data.notes = values.get("-TASK_NOTES-", "").strip()
        self.form_data.wave_workspace = values.get("-TASK_WAVE_WORKSPACE-", "").strip()

        # 转换状态
        status_text = values.get("-TASK_STATUS-", "待办")
        self.form_data.status = self.status_converter.text_to_status(status_text)

        # 转换优先级
        priority_text = values.get("-TASK_PRIORITY-", "普通")
        self.form_data.priority = self.PRIORITY_MAP.get(priority_text, 0)

        # 解析标签
        tags_text = values.get("-TASK_TAGS-", "").strip()
        if tags_text:
            self.form_data.tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        else:
            self.form_data.tags = []

    def validate(self, selected_window_count: int,
                 popup_manager) -> tuple[bool, str]:
        """验证表单数据

        Args:
            selected_window_count: 已选择窗口数量
            popup_manager: 弹窗管理器

        Returns:
            (是否有效, 错误消息)
        """
        # 检查任务名称
        if not self.form_data.name:
            return False, "请输入任务名称"

        # 检查名称重复（编辑时跳过当前任务）
        existing_tasks = self.task_manager.get_all_tasks()
        for task in existing_tasks:
            if task.name == self.form_data.name:
                if self._editing_task_id and task.id == self._editing_task_id:
                    continue
                return False, f"任务名称 '{self.form_data.name}' 已存在"

        # 检查是否选择了窗口
        if selected_window_count == 0:
            # 允许无窗口创建，返回警告但不阻止
            pass

        return True, ""

    def create_task(self, window_hwnds: List[int]) -> Optional[Task]:
        """创建新任务

        Args:
            window_hwnds: 窗口句柄列表

        Returns:
            创建的任务，如果失败则返回None
        """
        task = self.task_manager.add_task(
            name=self.form_data.name,
            description=self.form_data.description,
            window_hwnds=window_hwnds
        )

        if task:
            # 设置状态、优先级、笔记和标签
            self.task_manager.edit_task(
                task.id,
                status=self.form_data.status,
                priority=self.form_data.priority,
                notes=self.form_data.notes,
                wave_workspace=self.form_data.wave_workspace,
                tags=self.form_data.tags
            )

        return task

    def update_task(self, task_id: str, window_hwnds: List[int]) -> bool:
        """更新现有任务

        Args:
            task_id: 任务ID
            window_hwnds: 窗口句柄列表

        Returns:
            是否成功更新
        """
        return self.task_manager.edit_task(
            task_id,
            name=self.form_data.name,
            description=self.form_data.description,
            status=self.form_data.status,
            window_hwnds=window_hwnds,
            priority=self.form_data.priority,
            notes=self.form_data.notes,
            wave_workspace=self.form_data.wave_workspace,
            tags=self.form_data.tags
        )

    def get_form_data(self) -> TaskFormData:
        """获取当前表单数据

        Returns:
            表单数据
        """
        return self.form_data

    def get_layout_values(self) -> Dict[str, Any]:
        """获取用于布局的表单值

        Returns:
            表单值字典
        """
        tags_display = ", ".join(self.form_data.tags) if self.form_data.tags else ""

        return {
            "task_name": self.form_data.name,
            "task_description": self.form_data.description,
            "task_status": self.status_converter.status_to_text(self.form_data.status),
            "task_priority": self.PRIORITY_MAP.get(
                self.form_data.priority,
                self.PRIORITY_MAP["普通"]
            ),
            "task_notes": self.form_data.notes,
            "task_wave_workspace": self.form_data.wave_workspace,
            "task_tags": tags_display
        }

    def is_editing(self) -> bool:
        """是否处于编辑模式

        Returns:
            是否编辑模式
        """
        return self._editing_task_id is not None

    def get_editing_task_id(self) -> Optional[str]:
        """获取正在编辑的任务ID

        Returns:
            任务ID，如果不是编辑模式则返回None
        """
        return self._editing_task_id

    @staticmethod
    def get_priority_options() -> List[str]:
        """获取优先级选项

        Returns:
            优先级选项列表
        """
        return ["普通", "低", "中", "高"]
