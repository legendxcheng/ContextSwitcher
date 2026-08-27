"""
专注计时器模块 (番茄钟)

提供番茄钟工作法支持:
- 可配置的专注时长 (默认25分钟)
- 可配置的休息时长 (默认5分钟)
- 自动计时和提醒
- 专注统计
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TimerState(Enum):
    """计时器状态"""
    IDLE = "idle"           # 空闲
    FOCUSING = "focusing"   # 专注中
    BREAK = "break"         # 休息中
    PAUSED = "paused"       # 暂停


@dataclass
class FocusSession:
    """专注会话记录"""
    task_id: Optional[str]
    task_name: str
    start_time: str
    end_time: Optional[str] = None
    planned_duration: int = 25 * 60  # 计划时长(秒)
    actual_duration: int = 0         # 实际时长(秒)
    completed: bool = False          # 是否完成


class FocusTimer:
    """专注计时器"""

    def __init__(self):
        """初始化专注计时器"""
        # 配置
        self.focus_duration = 25 * 60   # 专注时长(秒) - 25分钟
        self.short_break = 5 * 60       # 短休息(秒) - 5分钟
        self.long_break = 15 * 60       # 长休息(秒) - 15分钟
        self.sessions_before_long_break = 4  # 长休息前的专注次数

        # 状态
        self.state = TimerState.IDLE
        self.current_task_id: Optional[str] = None
        self.current_task_name: str = ""

        # 计时
        self.start_time: Optional[float] = None
        self.remaining_seconds: int = 0
        self.pause_time: Optional[float] = None

        # 统计
        self.completed_sessions: int = 0
        self.today_focus_seconds: int = 0
        self.sessions_history: list = []

        # 回调
        self.on_timer_tick: Optional[Callable[[int], None]] = None
        self.on_session_complete: Optional[Callable[[FocusSession], None]] = None
        self.on_break_complete: Optional[Callable, None] = None
        self.on_state_changed: Optional[Callable[[TimerState], None]] = None

        # 计时器线程
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

        print("[OK] 专注计时器初始化完成")

    def start_focus(self, task_id: Optional[str] = None, task_name: str = "",
                   duration_minutes: int = None) -> bool:
        """开始专注计时

        Args:
            task_id: 关联的任务ID
            task_name: 任务名称
            duration_minutes: 自定义专注时长(分钟)

        Returns:
            是否成功开始
        """
        if self.state == TimerState.FOCUSING:
            print("已有专注会话进行中")
            return False

        # 设置任务信息
        self.current_task_id = task_id
        self.current_task_name = task_name or "专注时间"

        # 设置时长
        if duration_minutes:
            self.remaining_seconds = duration_minutes * 60
        else:
            self.remaining_seconds = self.focus_duration

        # 更新状态
        self.state = TimerState.FOCUSING
        self.start_time = time.time()
        self.pause_time = None

        # 启动计时器线程
        self._stop_flag.clear()
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

        # 触发回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

        print(f"[FOCUS] 开始专注: {self.current_task_name} ({self.remaining_seconds // 60}分钟)")
        return True

    def start_break(self, is_long: bool = False) -> bool:
        """开始休息

        Args:
            is_long: 是否长休息

        Returns:
            是否成功开始
        """
        if self.state == TimerState.BREAK:
            return False

        # 设置时长
        self.remaining_seconds = self.long_break if is_long else self.short_break

        # 更新状态
        self.state = TimerState.BREAK
        self.start_time = time.time()
        self.pause_time = None

        # 启动计时器线程
        self._stop_flag.clear()
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

        # 触发回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

        break_type = "长休息" if is_long else "短休息"
        print(f"[BREAK] 开始{break_type}: {self.remaining_seconds // 60}分钟")
        return True

    def pause(self) -> bool:
        """暂停计时"""
        if self.state not in (TimerState.FOCUSING, TimerState.BREAK):
            return False

        self.pause_time = time.time()
        self._stop_flag.set()

        previous_state = self.state
        self.state = TimerState.PAUSED

        # 触发回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

        print(f"[PAUSE] 计时已暂停，剩余 {self.remaining_seconds // 60}:{self.remaining_seconds % 60:02d}")
        return True

    def resume(self) -> bool:
        """恢复计时"""
        if self.state != TimerState.PAUSED:
            return False

        # 恢复到专注状态
        self.state = TimerState.FOCUSING
        self.pause_time = None

        # 重新启动计时器线程
        self._stop_flag.clear()
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

        # 触发回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

        print(f"[RESUME] 计时已恢复，剩余 {self.remaining_seconds // 60}:{self.remaining_seconds % 60:02d}")
        return True

    def stop(self) -> Optional[FocusSession]:
        """停止计时

        Returns:
            如果是专注会话，返回会话记录
        """
        if self.state == TimerState.IDLE:
            return None

        # 停止计时器线程
        self._stop_flag.set()

        # 如果是专注会话，记录会话
        session = None
        if self.state in (TimerState.FOCUSING, TimerState.PAUSED):
            elapsed = int(time.time() - self.start_time) if self.start_time else 0

            session = FocusSession(
                task_id=self.current_task_id,
                task_name=self.current_task_name,
                start_time=datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else "",
                end_time=datetime.now().isoformat(),
                planned_duration=self.focus_duration,
                actual_duration=elapsed,
                completed=False
            )

            # 更新今日统计
            self.today_focus_seconds += elapsed
            self.sessions_history.append(session)

            print(f"[STOP] 专注中断，已专注 {elapsed // 60}分{elapsed % 60}秒")

        # 重置状态
        self.state = TimerState.IDLE
        self.start_time = None
        self.pause_time = None
        self.remaining_seconds = 0
        self.current_task_id = None
        self.current_task_name = ""

        # 触发回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

        return session

    def _timer_loop(self):
        """计时器循环"""
        last_second = self.remaining_seconds

        while not self._stop_flag.is_set() and self.remaining_seconds > 0:
            time.sleep(0.1)  # 100ms检查间隔

            if self._stop_flag.is_set():
                break

            # 计算剩余时间
            if self.start_time and self.state in (TimerState.FOCUSING, TimerState.BREAK):
                elapsed = int(time.time() - self.start_time)
                if self.state == TimerState.FOCUSING:
                    self.remaining_seconds = max(0, self.focus_duration - elapsed)
                else:
                    break_duration = self.long_break if self.completed_sessions % self.sessions_before_long_break == 0 else self.short_break
                    self.remaining_seconds = max(0, break_duration - elapsed)

                # 每秒触发一次回调
                if self.remaining_seconds != last_second:
                    last_second = self.remaining_seconds
                    if self.on_timer_tick:
                        self.on_timer_tick(self.remaining_seconds)

        # 检查是否完成
        if self.remaining_seconds <= 0 and not self._stop_flag.is_set():
            self._on_timer_complete()

    def _on_timer_complete(self):
        """计时完成处理"""
        if self.state == TimerState.FOCUSING:
            # 专注完成
            self.completed_sessions += 1
            elapsed = int(time.time() - self.start_time) if self.start_time else self.focus_duration

            session = FocusSession(
                task_id=self.current_task_id,
                task_name=self.current_task_name,
                start_time=datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else "",
                end_time=datetime.now().isoformat(),
                planned_duration=self.focus_duration,
                actual_duration=elapsed,
                completed=True
            )

            # 更新统计
            self.today_focus_seconds += elapsed
            self.sessions_history.append(session)

            print(f"[COMPLETE] 专注完成! 今日已完成 {self.completed_sessions} 个番茄钟")

            # 触发回调
            if self.on_session_complete:
                self.on_session_complete(session)

            # 重置状态
            self.state = TimerState.IDLE

        elif self.state == TimerState.BREAK:
            # 休息完成
            print("[COMPLETE] 休息结束!")

            # 触发回调
            if self.on_break_complete:
                self.on_break_complete()

            # 重置状态
            self.state = TimerState.IDLE

        # 触发状态变化回调
        if self.on_state_changed:
            self.on_state_changed(self.state)

    def get_display_time(self) -> str:
        """获取显示时间格式

        Returns:
            格式化的时间字符串 (MM:SS)
        """
        if self.state == TimerState.IDLE:
            return "--:--"

        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_status(self) -> Dict[str, Any]:
        """获取计时器状态"""
        return {
            "state": self.state.value,
            "remaining_seconds": self.remaining_seconds,
            "remaining_display": self.get_display_time(),
            "current_task": self.current_task_name,
            "completed_sessions": self.completed_sessions,
            "today_focus_minutes": self.today_focus_seconds // 60,
            "focus_duration": self.focus_duration // 60,
            "short_break": self.short_break // 60,
            "long_break": self.long_break // 60
        }

    def set_durations(self, focus_minutes: int = 25, short_break_minutes: int = 5,
                     long_break_minutes: int = 15):
        """设置时长配置

        Args:
            focus_minutes: 专注时长(分钟)
            short_break_minutes: 短休息时长(分钟)
            long_break_minutes: 长休息时长(分钟)
        """
        self.focus_duration = focus_minutes * 60
        self.short_break = short_break_minutes * 60
        self.long_break = long_break_minutes * 60
        print(f"[CONFIG] 番茄钟配置更新: 专注{focus_minutes}分 / 短休息{short_break_minutes}分 / 长休息{long_break_minutes}分")

    def reset_today_stats(self):
        """重置今日统计"""
        self.completed_sessions = 0
        self.today_focus_seconds = 0
        self.sessions_history.clear()
        print("[RESET] 今日统计已重置")

    def cleanup(self):
        """清理资源"""
        self._stop_flag.set()
        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=1)
        print("[OK] 专注计时器已清理")


# 全局计时器实例
_focus_timer: Optional[FocusTimer] = None


def get_focus_timer() -> FocusTimer:
    """获取全局专注计时器实例"""
    global _focus_timer
    if _focus_timer is None:
        _focus_timer = FocusTimer()
    return _focus_timer
