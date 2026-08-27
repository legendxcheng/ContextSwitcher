"""
任务时间追踪模块

负责追踪用户在每个任务上花费的时间:
- 自动记录任务切换时间
- 计算每个任务的专注时间
- 提供今日/本周/总计时间统计
- 支持时间段查询
"""

import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import json


@dataclass
class TimeSession:
    """一次任务工作会话"""
    task_id: str           # 任务ID
    start_time: str        # 开始时间 (ISO格式)
    end_time: Optional[str] = None  # 结束时间 (ISO格式)
    duration_seconds: int = 0       # 持续时间(秒)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeSession':
        """从字典创建"""
        return cls(**data)


@dataclass
class TaskTimeStats:
    """任务时间统计"""
    task_id: str
    task_name: str
    total_seconds: int = 0          # 总时间(秒)
    today_seconds: int = 0          # 今日时间(秒)
    week_seconds: int = 0           # 本周时间(秒)
    session_count: int = 0          # 会话次数
    last_session: Optional[str] = None  # 最后一次会话时间

    @property
    def total_hours(self) -> float:
        """总时间(小时)"""
        return self.total_seconds / 3600

    @property
    def today_hours(self) -> float:
        """今日时间(小时)"""
        return self.today_seconds / 3600

    @property
    def today_display(self) -> str:
        """今日时间显示格式"""
        hours = self.today_seconds // 3600
        minutes = (self.today_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "< 1m"

    @property
    def total_display(self) -> str:
        """总时间显示格式"""
        hours = self.total_seconds // 3600
        minutes = (self.total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "< 1m"


class TimeTracker:
    """时间追踪器"""

    def __init__(self):
        """初始化时间追踪器"""
        self.sessions: List[TimeSession] = []
        self.current_session: Optional[TimeSession] = None
        self.current_task_id: Optional[str] = None

        # 任务名称映射 (task_id -> task_name)
        self.task_names: Dict[str, str] = {}

        # 回调函数
        self.on_session_started = None
        self.on_session_ended = None

        print("[OK] 时间追踪器初始化完成")

    def start_session(self, task_id: str, task_name: str = "") -> TimeSession:
        """开始一个新的时间会话

        Args:
            task_id: 任务ID
            task_name: 任务名称(可选)

        Returns:
            创建的会话对象
        """
        # 如果有正在进行的会话，先结束它
        if self.current_session:
            self.end_session()

        # 记录任务名称
        if task_name:
            self.task_names[task_id] = task_name

        # 创建新会话
        session = TimeSession(
            task_id=task_id,
            start_time=datetime.now().isoformat()
        )

        self.current_session = session
        self.current_task_id = task_id

        print(f"[TIME] 开始计时: {task_name or task_id}")

        # 触发回调
        if self.on_session_started:
            self.on_session_started(session)

        return session

    def end_session(self) -> Optional[TimeSession]:
        """结束当前会话

        Returns:
            结束的会话对象
        """
        if not self.current_session:
            return None

        session = self.current_session

        # 计算持续时间
        start_time = datetime.fromisoformat(session.start_time)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        session.end_time = end_time.isoformat()
        session.duration_seconds = int(duration)

        # 添加到会话列表
        self.sessions.append(session)

        # 清除当前会话
        self.current_session = None
        self.current_task_id = None

        task_name = self.task_names.get(session.task_id, session.task_id)
        print(f"[TIME] 结束计时: {task_name} - {self._format_duration(int(duration))}")

        # 触发回调
        if self.on_session_ended:
            self.on_session_ended(session)

        return session

    def switch_task(self, new_task_id: str, new_task_name: str = "") -> Tuple[Optional[TimeSession], TimeSession]:
        """切换任务 (结束当前会话并开始新会话)

        Args:
            new_task_id: 新任务ID
            new_task_name: 新任务名称

        Returns:
            (结束的会话, 新开始的会话)
        """
        ended_session = self.end_session()
        new_session = self.start_session(new_task_id, new_task_name)
        return ended_session, new_session

    def get_task_stats(self, task_id: str) -> TaskTimeStats:
        """获取指定任务的时间统计

        Args:
            task_id: 任务ID

        Returns:
            任务时间统计对象
        """
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())

        total_seconds = 0
        today_seconds = 0
        week_seconds = 0
        session_count = 0
        last_session = None

        for session in self.sessions:
            if session.task_id != task_id:
                continue

            session_count += 1
            total_seconds += session.duration_seconds

            if session.end_time:
                session_end = datetime.fromisoformat(session.end_time)

                # 今日时间
                if session_end >= today_start:
                    session_start = datetime.fromisoformat(session.start_time)
                    if session_start < today_start:
                        # 会话跨越今天开始
                        today_seconds += int((session_end - today_start).total_seconds())
                    else:
                        today_seconds += session.duration_seconds

                # 本周时间
                if session_end >= week_start:
                    session_start = datetime.fromisoformat(session.start_time)
                    if session_start < week_start:
                        week_seconds += int((session_end - week_start).total_seconds())
                    else:
                        week_seconds += session.duration_seconds

                # 最后会话时间
                if not last_session or session_end > datetime.fromisoformat(last_session):
                    last_session = session.end_time

        # 加上当前正在进行的会话时间
        if self.current_session and self.current_session.task_id == task_id:
            current_duration = int((datetime.now() -
                datetime.fromisoformat(self.current_session.start_time)).total_seconds())
            total_seconds += current_duration
            today_seconds += current_duration
            week_seconds += current_duration

        return TaskTimeStats(
            task_id=task_id,
            task_name=self.task_names.get(task_id, task_id),
            total_seconds=total_seconds,
            today_seconds=today_seconds,
            week_seconds=week_seconds,
            session_count=session_count,
            last_session=last_session
        )

    def get_all_stats(self) -> List[TaskTimeStats]:
        """获取所有任务的时间统计

        Returns:
            所有任务的时间统计列表
        """
        task_ids = set(session.task_id for session in self.sessions)
        if self.current_session:
            task_ids.add(self.current_session.task_id)

        return [self.get_task_stats(task_id) for task_id in task_ids]

    def get_today_total(self) -> int:
        """获取今日总专注时间(秒)"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())

        total = 0
        for session in self.sessions:
            if session.end_time:
                session_end = datetime.fromisoformat(session.end_time)
                if session_end >= today_start:
                    session_start = datetime.fromisoformat(session.start_time)
                    if session_start < today_start:
                        total += int((session_end - today_start).total_seconds())
                    else:
                        total += session.duration_seconds

        # 加上当前会话
        if self.current_session:
            current_duration = int((datetime.now() -
                datetime.fromisoformat(self.current_session.start_time)).total_seconds())
            total += current_duration

        return total

    def get_today_display(self) -> str:
        """获取今日总时间的显示格式"""
        seconds = self.get_today_total()
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return "< 1m"

    def get_week_total(self) -> int:
        """获取本周总专注时间(秒)"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())

        total = 0
        for session in self.sessions:
            if session.end_time:
                session_end = datetime.fromisoformat(session.end_time)
                if session_end >= week_start:
                    session_start = datetime.fromisoformat(session.start_time)
                    if session_start < week_start:
                        # 会话跨越本周开始
                        total += int((session_end - week_start).total_seconds())
                    else:
                        total += session.duration_seconds

        # 加上当前会话
        if self.current_session:
            session_start = datetime.fromisoformat(self.current_session.start_time)
            if session_start >= week_start:
                current_duration = int((datetime.now() - session_start).total_seconds())
                total += current_duration

        return total

    def get_current_task_duration(self) -> int:
        """获取当前任务的持续时间(秒)"""
        if not self.current_session:
            return 0

        start_time = datetime.fromisoformat(self.current_session.start_time)
        return int((datetime.now() - start_time).total_seconds())

    def get_current_duration_display(self) -> str:
        """获取当前任务持续时间的显示格式"""
        seconds = self.get_current_task_duration()
        if seconds == 0:
            return "--:--"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于持久化"""
        return {
            "sessions": [s.to_dict() for s in self.sessions],
            "current_session": self.current_session.to_dict() if self.current_session else None,
            "task_names": self.task_names
        }

    def from_dict(self, data: Dict[str, Any]):
        """从字典恢复状态"""
        if "sessions" in data:
            self.sessions = [TimeSession.from_dict(s) for s in data["sessions"]]

        if "current_session" in data and data["current_session"]:
            self.current_session = TimeSession.from_dict(data["current_session"])
            self.current_task_id = self.current_session.task_id

        if "task_names" in data:
            self.task_names = data["task_names"]

    def cleanup_old_sessions(self, days: int = 30):
        """清理旧的会话记录

        Args:
            days: 保留最近多少天的记录
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        original_count = len(self.sessions)
        self.sessions = [s for s in self.sessions
                        if s.end_time and s.end_time >= cutoff_str]

        cleaned = original_count - len(self.sessions)
        if cleaned > 0:
            print(f"[TIME] 已清理 {cleaned} 个旧会话记录")

    def _format_duration(self, seconds: int) -> str:
        """格式化持续时间"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"


# 全局时间追踪器实例
_time_tracker: Optional[TimeTracker] = None


def get_time_tracker() -> TimeTracker:
    """获取全局时间追踪器实例"""
    global _time_tracker
    if _time_tracker is None:
        _time_tracker = TimeTracker()
    return _time_tracker
