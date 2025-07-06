"""
任务状态管理器

负责任务状态的转换和管理:
- 状态转换逻辑
- 状态历史记录
- 状态可视化配置
- 状态统计分析
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from core.task_manager import TaskStatus, Task, TaskManager


@dataclass
class StatusChangeRecord:
    """状态变更记录"""
    task_id: str
    old_status: TaskStatus
    new_status: TaskStatus
    timestamp: str
    reason: str = ""
    user_comment: str = ""


class TaskStatusManager:
    """任务状态管理器"""
    
    # 状态颜色配置
    STATUS_COLORS = {
        TaskStatus.TODO: "#808080",        # 灰色
        TaskStatus.IN_PROGRESS: "#0078D4", # 蓝色
        TaskStatus.BLOCKED: "#D13438",     # 红色
        TaskStatus.REVIEW: "#FF8C00",      # 橙色
        TaskStatus.COMPLETED: "#107C10",   # 绿色
        TaskStatus.PAUSED: "#5C2D91"       # 紫色
    }
    
    # 状态图标配置
    STATUS_ICONS = {
        TaskStatus.TODO: "○",
        TaskStatus.IN_PROGRESS: "▶",
        TaskStatus.BLOCKED: "⚠",
        TaskStatus.REVIEW: "👁",
        TaskStatus.COMPLETED: "✓",
        TaskStatus.PAUSED: "⏸"
    }
    
    # 状态显示名称
    STATUS_NAMES = {
        TaskStatus.TODO: "待办",
        TaskStatus.IN_PROGRESS: "进行中",
        TaskStatus.BLOCKED: "已阻塞",
        TaskStatus.REVIEW: "待审查",
        TaskStatus.COMPLETED: "已完成",
        TaskStatus.PAUSED: "已暂停"
    }
    
    # 允许的状态转换规则
    ALLOWED_TRANSITIONS = {
        TaskStatus.TODO: [TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.PAUSED],
        TaskStatus.IN_PROGRESS: [TaskStatus.REVIEW, TaskStatus.COMPLETED, TaskStatus.BLOCKED, TaskStatus.PAUSED],
        TaskStatus.BLOCKED: [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.PAUSED],
        TaskStatus.REVIEW: [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
        TaskStatus.COMPLETED: [TaskStatus.REVIEW, TaskStatus.IN_PROGRESS],  # 允许重新打开
        TaskStatus.PAUSED: [TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
    }
    
    def __init__(self, task_manager: TaskManager):
        """初始化状态管理器
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.status_history: List[StatusChangeRecord] = []
        
        print("✓ 任务状态管理器初始化完成")
    
    def change_task_status(self, task_id: str, new_status: TaskStatus, 
                          reason: str = "", user_comment: str = "") -> bool:
        """改变任务状态
        
        Args:
            task_id: 任务ID
            new_status: 新状态
            reason: 状态变更原因
            user_comment: 用户备注
            
        Returns:
            是否成功变更状态
        """
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            print(f"任务不存在: {task_id}")
            return False
        
        old_status = task.status
        
        # 检查状态转换是否合法
        if not self.is_transition_allowed(old_status, new_status):
            print(f"不允许的状态转换: {old_status.value} -> {new_status.value}")
            return False
        
        # 更新任务状态
        task.status = new_status
        
        # 记录状态变更历史
        record = StatusChangeRecord(
            task_id=task_id,
            old_status=old_status,
            new_status=new_status,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            user_comment=user_comment
        )
        self.status_history.append(record)
        
        # 特殊状态处理
        if new_status == TaskStatus.IN_PROGRESS:
            # 将其他进行中的任务设为暂停（可选）
            self._handle_in_progress_status(task_id)
        elif new_status == TaskStatus.COMPLETED:
            # 完成任务时的特殊处理
            self._handle_completed_status(task)
        
        # 触发任务更新回调
        if self.task_manager.on_task_updated:
            self.task_manager.on_task_updated(task)
        
        print(f"✓ 任务状态已更新: {task.name} -> {self.STATUS_NAMES[new_status]}")
        return True
    
    def is_transition_allowed(self, current_status: TaskStatus, new_status: TaskStatus) -> bool:
        """检查状态转换是否被允许
        
        Args:
            current_status: 当前状态
            new_status: 目标状态
            
        Returns:
            是否允许转换
        """
        if current_status == new_status:
            return True  # 相同状态允许（用于更新时间戳等）
        
        allowed_transitions = self.ALLOWED_TRANSITIONS.get(current_status, [])
        return new_status in allowed_transitions
    
    def get_allowed_next_statuses(self, current_status: TaskStatus) -> List[TaskStatus]:
        """获取当前状态允许转换到的所有状态
        
        Args:
            current_status: 当前状态
            
        Returns:
            允许转换到的状态列表
        """
        return self.ALLOWED_TRANSITIONS.get(current_status, [])
    
    def get_status_icon(self, status: TaskStatus) -> str:
        """获取状态图标
        
        Args:
            status: 任务状态
            
        Returns:
            状态图标
        """
        return self.STATUS_ICONS.get(status, "○")
    
    def get_status_color(self, status: TaskStatus) -> str:
        """获取状态颜色
        
        Args:
            status: 任务状态
            
        Returns:
            状态颜色（十六进制）
        """
        return self.STATUS_COLORS.get(status, "#808080")
    
    def get_status_name(self, status: TaskStatus) -> str:
        """获取状态显示名称
        
        Args:
            status: 任务状态
            
        Returns:
            状态显示名称
        """
        return self.STATUS_NAMES.get(status, "未知")
    
    def get_status_statistics(self) -> Dict[str, Any]:
        """获取状态统计信息
        
        Returns:
            状态统计数据
        """
        all_tasks = self.task_manager.get_all_tasks()
        
        # 按状态统计任务数量
        status_count = {}
        for status in TaskStatus:
            status_count[status.value] = 0
        
        for task in all_tasks:
            status_count[task.status.value] += 1
        
        # 统计今日状态变更
        today = datetime.now().date()
        today_changes = 0
        for record in self.status_history:
            record_date = datetime.fromisoformat(record.timestamp).date()
            if record_date == today:
                today_changes += 1
        
        return {
            "total_tasks": len(all_tasks),
            "status_distribution": status_count,
            "today_changes": today_changes,
            "total_changes": len(self.status_history)
        }
    
    def get_task_status_history(self, task_id: str) -> List[StatusChangeRecord]:
        """获取任务的状态变更历史
        
        Args:
            task_id: 任务ID
            
        Returns:
            状态变更记录列表
        """
        return [record for record in self.status_history if record.task_id == task_id]
    
    def _handle_in_progress_status(self, current_task_id: str):
        """处理进行中状态的特殊逻辑
        
        Args:
            current_task_id: 当前设为进行中的任务ID
        """
        # 可选：将其他进行中的任务自动暂停
        # 这里可以根据需求决定是否启用这个功能
        pass
    
    def _handle_completed_status(self, task: Task):
        """处理已完成状态的特殊逻辑
        
        Args:
            task: 已完成的任务
        """
        # 更新完成时间
        task.last_accessed = datetime.now().isoformat()
        
        # 可以在这里添加其他完成任务后的处理逻辑
        # 比如：自动归档、生成报告等
    
    def export_status_history(self, file_path: str = None) -> str:
        """导出状态变更历史
        
        Args:
            file_path: 导出文件路径，如果为None则返回JSON字符串
            
        Returns:
            JSON格式的历史数据
        """
        history_data = []
        for record in self.status_history:
            history_data.append({
                "task_id": record.task_id,
                "old_status": record.old_status.value,
                "new_status": record.new_status.value,
                "timestamp": record.timestamp,
                "reason": record.reason,
                "user_comment": record.user_comment
            })
        
        json_data = json.dumps(history_data, indent=2, ensure_ascii=False)
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            print(f"状态历史已导出到: {file_path}")
        
        return json_data
    
    def import_status_history(self, file_path: str) -> bool:
        """导入状态变更历史
        
        Args:
            file_path: 导入文件路径
            
        Returns:
            是否成功导入
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            imported_records = []
            for data in history_data:
                record = StatusChangeRecord(
                    task_id=data["task_id"],
                    old_status=TaskStatus(data["old_status"]),
                    new_status=TaskStatus(data["new_status"]),
                    timestamp=data["timestamp"],
                    reason=data.get("reason", ""),
                    user_comment=data.get("user_comment", "")
                )
                imported_records.append(record)
            
            self.status_history.extend(imported_records)
            print(f"成功导入 {len(imported_records)} 条状态历史记录")
            return True
            
        except Exception as e:
            print(f"导入状态历史失败: {e}")
            return False