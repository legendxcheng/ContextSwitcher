"""
智能重新绑定管理器

负责检测失效窗口并提供智能重新绑定功能:
- 窗口失效检测
- 智能窗口匹配
- 自动/手动重新绑定
- 绑定历史记录
"""

import re
import time
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from core.task_manager import TaskManager, Task, BoundWindow
from core.window_manager import WindowManager


@dataclass
class RebindSuggestion:
    """重新绑定建议"""
    window_hwnd: int
    window_title: str
    window_process: str
    similarity_score: float
    match_reason: str


@dataclass
class RebindHistory:
    """重新绑定历史记录"""
    task_id: str
    old_window_title: str
    new_window_title: str
    new_window_hwnd: int
    timestamp: str
    method: str  # 'auto' or 'manual'
    similarity_score: float


class SmartRebindManager:
    """智能重新绑定管理器"""
    
    def __init__(self, task_manager: TaskManager, window_manager: WindowManager):
        """初始化智能重新绑定管理器
        
        Args:
            task_manager: 任务管理器
            window_manager: 窗口管理器
        """
        self.task_manager = task_manager
        self.window_manager = window_manager
        self.binding_history: List[RebindHistory] = []
        
        # 相似度阈值
        self.AUTO_REBIND_THRESHOLD = 0.9  # 90%相似度自动绑定
        self.SUGGEST_THRESHOLD = 0.7      # 70%相似度提供建议
        
        print("[OK] 智能重新绑定管理器初始化完成")
    
    def detect_invalid_windows(self, task: Task) -> List[BoundWindow]:
        """检测任务中的失效窗口
        
        Args:
            task: 要检测的任务
            
        Returns:
            失效窗口列表
        """
        invalid_windows = []
        
        for window in task.bound_windows:
            if not self.window_manager.is_window_valid(window.hwnd):
                invalid_windows.append(window)
        
        return invalid_windows
    
    def suggest_replacements(self, invalid_window: BoundWindow) -> List[RebindSuggestion]:
        """为失效窗口建议替代窗口
        
        Args:
            invalid_window: 失效的窗口
            
        Returns:
            建议的替代窗口列表，按相似度排序
        """
        current_windows = self.window_manager.enumerate_windows()
        suggestions = []
        
        for hwnd, title in current_windows:
            # 获取窗口进程信息
            try:
                process_name = self.window_manager.get_window_process(hwnd)
            except:
                process_name = "Unknown"
            
            # 计算相似度
            similarity, match_reason = self._calculate_similarity(
                invalid_window.title, title, invalid_window.process_name, process_name
            )
            
            if similarity >= self.SUGGEST_THRESHOLD:
                suggestion = RebindSuggestion(
                    window_hwnd=hwnd,
                    window_title=title,
                    window_process=process_name,
                    similarity_score=similarity,
                    match_reason=match_reason
                )
                suggestions.append(suggestion)
        
        # 按相似度排序
        suggestions.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return suggestions
    
    def auto_rebind_windows(self, task: Task) -> List[Tuple[BoundWindow, RebindSuggestion, str]]:
        """自动重新绑定窗口
        
        Args:
            task: 要处理的任务
            
        Returns:
            重新绑定结果列表: (原窗口, 新窗口建议, 结果状态)
        """
        invalid_windows = self.detect_invalid_windows(task)
        rebind_results = []
        
        for invalid_window in invalid_windows:
            suggestions = self.suggest_replacements(invalid_window)
            
            if suggestions and suggestions[0].similarity_score >= self.AUTO_REBIND_THRESHOLD:
                # 自动绑定最佳匹配
                best_suggestion = suggestions[0]
                
                # 创建新的绑定窗口
                new_bound_window = BoundWindow(
                    hwnd=best_suggestion.window_hwnd,
                    title=best_suggestion.window_title,
                    process_name=best_suggestion.window_process
                )
                
                # 替换窗口
                success = self.task_manager.replace_window(
                    task.id, invalid_window.hwnd, new_bound_window
                )
                
                if success:
                    # 记录历史
                    self._record_rebind_history(
                        task.id, invalid_window.title, best_suggestion.window_title,
                        best_suggestion.window_hwnd, 'auto', best_suggestion.similarity_score
                    )
                    
                    rebind_results.append((invalid_window, best_suggestion, 'auto_success'))
                else:
                    rebind_results.append((invalid_window, best_suggestion, 'auto_failed'))
            else:
                rebind_results.append((invalid_window, None, 'no_auto_match'))
        
        return rebind_results
    
    def manual_rebind_window(self, task: Task, old_hwnd: int, new_hwnd: int) -> bool:
        """手动重新绑定窗口
        
        Args:
            task: 任务
            old_hwnd: 旧窗口句柄
            new_hwnd: 新窗口句柄
            
        Returns:
            绑定是否成功
        """
        # 获取新窗口信息
        new_window_info = self.window_manager.get_window_info(new_hwnd)
        if not new_window_info:
            return False
        
        # 创建新的绑定窗口
        new_bound_window = BoundWindow(
            hwnd=new_hwnd,
            title=new_window_info['title'],
            process_name=new_window_info['process']
        )
        
        # 获取旧窗口标题（用于历史记录）
        old_window_title = "Unknown"
        for window in task.bound_windows:
            if window.hwnd == old_hwnd:
                old_window_title = window.title
                break
        
        # 替换窗口
        success = self.task_manager.replace_window(task.id, old_hwnd, new_bound_window)
        
        if success:
            # 记录历史
            self._record_rebind_history(
                task.id, old_window_title, new_window_info['title'],
                new_hwnd, 'manual', 1.0
            )
        
        return success
    
    def get_rebind_history(self, task_id: Optional[str] = None) -> List[RebindHistory]:
        """获取重新绑定历史
        
        Args:
            task_id: 任务ID，如果为None则返回所有历史
            
        Returns:
            历史记录列表
        """
        if task_id:
            return [h for h in self.binding_history if h.task_id == task_id]
        return self.binding_history.copy()
    
    def _calculate_similarity(self, title1: str, title2: str, 
                            process1: str, process2: str) -> Tuple[float, str]:
        """计算两个窗口的相似度
        
        Args:
            title1: 第一个窗口标题
            title2: 第二个窗口标题
            process1: 第一个进程名
            process2: 第二个进程名
            
        Returns:
            (相似度分数, 匹配原因)
        """
        # 进程名完全匹配权重更高
        if process1.lower() == process2.lower():
            # 标题相似度
            title_similarity = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
            
            # 进程匹配+高标题相似度
            if title_similarity > 0.8:
                return title_similarity * 0.95, f"进程匹配({process1})+高标题相似度"
            # 进程匹配+中等标题相似度
            elif title_similarity > 0.5:
                return title_similarity * 0.85, f"进程匹配({process1})+中等标题相似度"
            # 只有进程匹配
            else:
                return 0.7, f"进程匹配({process1})"
        
        # 进程名不匹配，只看标题相似度
        title_similarity = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
        
        # 检查特殊模式
        if self._check_special_patterns(title1, title2):
            return min(title_similarity + 0.1, 1.0), "特殊模式匹配"
        
        if title_similarity > 0.8:
            return title_similarity * 0.7, "高标题相似度"
        elif title_similarity > 0.5:
            return title_similarity * 0.6, "中等标题相似度"
        else:
            return title_similarity * 0.5, "低标题相似度"
    
    def _check_special_patterns(self, title1: str, title2: str) -> bool:
        """检查特殊匹配模式
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            是否匹配特殊模式
        """
        # 移除常见的时间戳和版本号
        def clean_title(title):
            # 移除时间戳 (如: 2023-07-05, 14:30:25)
            title = re.sub(r'\d{4}-\d{2}-\d{2}', '', title)
            title = re.sub(r'\d{2}:\d{2}:\d{2}', '', title)
            # 移除版本号 (如: v1.0.0, 1.2.3)
            title = re.sub(r'v?\d+\.\d+\.\d+', '', title)
            # 移除括号内容 (如: (DEBUG), (Release))
            title = re.sub(r'\([^)]*\)', '', title)
            return title.strip()
        
        clean1 = clean_title(title1)
        clean2 = clean_title(title2)
        
        # 清理后的标题相似度
        if clean1 and clean2:
            similarity = SequenceMatcher(None, clean1.lower(), clean2.lower()).ratio()
            return similarity > 0.8
        
        return False
    
    def _record_rebind_history(self, task_id: str, old_title: str, new_title: str,
                              new_hwnd: int, method: str, similarity: float):
        """记录重新绑定历史
        
        Args:
            task_id: 任务ID
            old_title: 旧窗口标题
            new_title: 新窗口标题
            new_hwnd: 新窗口句柄
            method: 绑定方法 ('auto' or 'manual')
            similarity: 相似度分数
        """
        history = RebindHistory(
            task_id=task_id,
            old_window_title=old_title,
            new_window_title=new_title,
            new_window_hwnd=new_hwnd,
            timestamp=datetime.now().isoformat(),
            method=method,
            similarity_score=similarity
        )
        
        self.binding_history.append(history)
        
        # 保持历史记录数量限制（最多保留100条）
        if len(self.binding_history) > 100:
            self.binding_history = self.binding_history[-100:]
    
    def validate_and_suggest_rebinds(self, task: Task) -> Dict[str, Any]:
        """验证任务并提供重新绑定建议
        
        Args:
            task: 要验证的任务
            
        Returns:
            包含验证结果和建议的字典
        """
        invalid_windows = self.detect_invalid_windows(task)
        
        if not invalid_windows:
            return {
                'valid': True,
                'invalid_windows': [],
                'suggestions': {},
                'auto_rebind_available': False
            }
        
        # 为每个失效窗口生成建议
        suggestions = {}
        auto_rebind_available = False
        
        for invalid_window in invalid_windows:
            window_suggestions = self.suggest_replacements(invalid_window)
            suggestions[invalid_window.hwnd] = window_suggestions
            
            # 检查是否有自动绑定的选项
            if window_suggestions and window_suggestions[0].similarity_score >= self.AUTO_REBIND_THRESHOLD:
                auto_rebind_available = True
        
        return {
            'valid': False,
            'invalid_windows': invalid_windows,
            'suggestions': suggestions,
            'auto_rebind_available': auto_rebind_available
        }