"""
任务状态转换器模块

负责任务状态枚举与文本之间的互相转换
"""

from core.task_manager import TaskStatus


class TaskStatusConverter:
    """任务状态转换器 - 负责状态与文本互转"""

    # 状态到文本的映射
    STATUS_TO_TEXT_MAP = {
        TaskStatus.TODO: "待办",
        TaskStatus.IN_PROGRESS: "进行中",
        TaskStatus.BLOCKED: "已阻塞",
        TaskStatus.REVIEW: "待审查",
        TaskStatus.COMPLETED: "已完成",
        TaskStatus.PAUSED: "已暂停"
    }

    # 文本到状态的映射
    TEXT_TO_STATUS_MAP = {
        "待办": TaskStatus.TODO,
        "进行中": TaskStatus.IN_PROGRESS,
        "已阻塞": TaskStatus.BLOCKED,
        "待审查": TaskStatus.REVIEW,
        "已完成": TaskStatus.COMPLETED,
        "已暂停": TaskStatus.PAUSED
    }

    # 所有状态选项（用于下拉框）
    STATUS_OPTIONS = ["待办", "进行中", "已阻塞", "待审查", "已完成", "已暂停"]

    @classmethod
    def status_to_text(cls, status: TaskStatus) -> str:
        """状态枚举转换为文本

        Args:
            status: 任务状态枚举

        Returns:
            状态文本
        """
        return cls.STATUS_TO_TEXT_MAP.get(status, "待办")

    @classmethod
    def text_to_status(cls, text: str) -> TaskStatus:
        """文本转换为状态枚举

        Args:
            text: 状态文本

        Returns:
            任务状态枚举
        """
        return cls.TEXT_TO_STATUS_MAP.get(text, TaskStatus.TODO)

    @classmethod
    def get_all_status_options(cls) -> list:
        """获取所有状态选项

        Returns:
            状态选项列表
        """
        return cls.STATUS_OPTIONS.copy()
