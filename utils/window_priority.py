"""
窗口优先级管理模块

负责窗口显示优先级的计算和排序：
- 当前前台窗口优先级
- 活跃窗口检测和评分
- 搜索匹配度优先级
- 最近使用窗口历史
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from core.window_manager import WindowInfo


@dataclass
class WindowPriority:
    """窗口优先级信息"""
    window: WindowInfo
    total_score: int
    is_foreground: bool = False
    is_active: bool = False
    is_recent: bool = False
    search_score: int = 0
    activity_score: int = 0
    recency_score: int = 0
    special_flags: List[str] = None
    
    def __post_init__(self):
        if self.special_flags is None:
            self.special_flags = []


class WindowPriorityManager:
    """窗口优先级管理器"""
    
    def __init__(self):
        """初始化优先级管理器"""
        self.window_usage_history = {}  # 窗口使用历史
        self.last_foreground_update = 0
        self.foreground_cache = None
    
    def calculate_window_priorities(self, 
                                   windows: List[WindowInfo],
                                   active_windows_info: Dict[str, Any] = None,
                                   search_results: Dict[int, Any] = None) -> List[WindowPriority]:
        """计算所有窗口的显示优先级
        
        Args:
            windows: 窗口列表
            active_windows_info: 活跃窗口信息（来自WindowManager.get_active_windows_info）
            search_results: 搜索结果信息
            
        Returns:
            按优先级排序的窗口优先级列表
        """
        priorities = []
        
        # 获取前台窗口信息
        foreground_hwnd = None
        active_hwnds = set()
        recent_hwnds = set()
        
        if active_windows_info:
            if active_windows_info.get('foreground_window'):
                foreground_hwnd = active_windows_info['foreground_window'].hwnd
            
            for window in active_windows_info.get('active_windows', []):
                active_hwnds.add(window.hwnd)
            
            for window in active_windows_info.get('recent_windows', []):
                recent_hwnds.add(window.hwnd)
        
        # 为每个窗口计算优先级
        for window in windows:
            priority = self._calculate_single_window_priority(
                window, foreground_hwnd, active_hwnds, recent_hwnds, search_results
            )
            priorities.append(priority)
        
        # 按总分排序（降序）
        priorities.sort(key=lambda x: x.total_score, reverse=True)
        
        return priorities
    
    def _calculate_single_window_priority(self,
                                        window: WindowInfo,
                                        foreground_hwnd: int,
                                        active_hwnds: set,
                                        recent_hwnds: set,
                                        search_results: Dict[int, Any] = None) -> WindowPriority:
        """计算单个窗口的优先级
        
        Args:
            window: 窗口信息
            foreground_hwnd: 前台窗口句柄
            active_hwnds: 活跃窗口句柄集合
            recent_hwnds: 最近使用窗口句柄集合
            search_results: 搜索结果
            
        Returns:
            窗口优先级信息
        """
        # 基础分数
        total_score = 0
        special_flags = []
        
        # 1. 前台窗口最高优先级
        is_foreground = window.hwnd == foreground_hwnd
        if is_foreground:
            total_score += 1000
            special_flags.append("foreground")
        
        # 2. 活跃窗口高优先级
        is_active = window.hwnd in active_hwnds
        activity_score = 0
        if is_active:
            activity_score = 500
            total_score += activity_score
            special_flags.append("active")
        
        # 3. 最近使用窗口中等优先级
        is_recent = window.hwnd in recent_hwnds
        recency_score = 0
        if is_recent:
            recency_score = 200
            total_score += recency_score
            special_flags.append("recent")
        
        # 4. 搜索匹配分数
        search_score = 0
        if search_results and window.hwnd in search_results:
            search_result = search_results[window.hwnd]
            search_score = getattr(search_result, 'score', 0)
            total_score += search_score
            if search_score > 0:
                special_flags.append("search_match")
        
        # 5. 窗口类型加分
        type_bonus = self._get_window_type_bonus(window)
        total_score += type_bonus
        
        # 6. 窗口大小和位置加分
        size_bonus = self._get_window_size_bonus(window)
        total_score += size_bonus
        
        # 7. 使用历史加分
        history_bonus = self._get_window_history_bonus(window)
        total_score += history_bonus
        
        return WindowPriority(
            window=window,
            total_score=total_score,
            is_foreground=is_foreground,
            is_active=is_active,
            is_recent=is_recent,
            search_score=search_score,
            activity_score=activity_score,
            recency_score=recency_score,
            special_flags=special_flags
        )
    
    def _get_window_type_bonus(self, window: WindowInfo) -> int:
        """根据窗口类型计算加分
        
        Args:
            window: 窗口信息
            
        Returns:
            类型加分
        """
        process_name = window.process_name.lower()
        
        # 高优先级应用（常用开发工具）
        high_priority_apps = {
            'code.exe': 50,
            'devenv.exe': 50,
            'notepad++.exe': 40,
            'sublime_text.exe': 40,
            'atom.exe': 40,
        }
        
        # 中优先级应用（浏览器和办公）
        medium_priority_apps = {
            'chrome.exe': 30,
            'firefox.exe': 30,
            'edge.exe': 30,
            'winword.exe': 25,
            'excel.exe': 25,
            'powerpnt.exe': 25,
        }
        
        # 通讯工具
        communication_apps = {
            'wechat.exe': 20,
            'qq.exe': 20,
            'dingding.exe': 20,
            'teams.exe': 20,
            'slack.exe': 20,
        }
        
        if process_name in high_priority_apps:
            return high_priority_apps[process_name]
        elif process_name in medium_priority_apps:
            return medium_priority_apps[process_name]
        elif process_name in communication_apps:
            return communication_apps[process_name]
        
        return 0
    
    def _get_window_size_bonus(self, window: WindowInfo) -> int:
        """根据窗口大小和位置计算加分
        
        Args:
            window: 窗口信息
            
        Returns:
            大小位置加分
        """
        try:
            left, top, right, bottom = window.rect
            width = right - left
            height = bottom - top
            
            # 合理大小的窗口加分
            if 800 <= width <= 2000 and 600 <= height <= 1500:
                size_bonus = 15
            elif 400 <= width < 800 and 300 <= height < 600:
                size_bonus = 10
            elif width >= 2000 or height >= 1500:
                size_bonus = 5  # 太大的窗口可能不是主要工作窗口
            else:
                size_bonus = 0  # 太小的窗口
            
            # 位置加分（主屏幕中央区域）
            position_bonus = 0
            if 0 <= left <= 100 and 0 <= top <= 100:
                position_bonus = 5  # 左上角位置
            
            return size_bonus + position_bonus
            
        except Exception:
            return 0
    
    def _get_window_history_bonus(self, window: WindowInfo) -> int:
        """根据窗口使用历史计算加分
        
        Args:
            window: 窗口信息
            
        Returns:
            历史加分
        """
        # 简化的历史加分逻辑
        # 在实际实现中，可以记录窗口的使用频率和最近访问时间
        
        process_name = window.process_name.lower()
        
        # 模拟历史数据（实际应该从配置或缓存中读取）
        if hasattr(self, '_mock_history'):
            return self._mock_history.get(process_name, 0)
        
        return 0
    
    def update_window_usage(self, window_hwnd: int):
        """更新窗口使用记录
        
        Args:
            window_hwnd: 窗口句柄
        """
        import time
        
        if window_hwnd not in self.window_usage_history:
            self.window_usage_history[window_hwnd] = {
                'count': 0,
                'last_used': 0,
                'first_used': time.time()
            }
        
        history = self.window_usage_history[window_hwnd]
        history['count'] += 1
        history['last_used'] = time.time()
    
    def get_priority_summary(self, priorities: List[WindowPriority]) -> Dict[str, Any]:
        """获取优先级统计摘要
        
        Args:
            priorities: 窗口优先级列表
            
        Returns:
            统计摘要
        """
        if not priorities:
            return {}
        
        foreground_count = sum(1 for p in priorities if p.is_foreground)
        active_count = sum(1 for p in priorities if p.is_active)
        recent_count = sum(1 for p in priorities if p.is_recent)
        search_match_count = sum(1 for p in priorities if p.search_score > 0)
        
        avg_score = sum(p.total_score for p in priorities) / len(priorities)
        max_score = max(p.total_score for p in priorities)
        
        return {
            'total_windows': len(priorities),
            'foreground_count': foreground_count,
            'active_count': active_count,
            'recent_count': recent_count,
            'search_match_count': search_match_count,
            'average_score': avg_score,
            'max_score': max_score,
            'top_window': priorities[0].window.title if priorities else None
        }
    
    def set_mock_history_for_testing(self, history_data: Dict[str, int]):
        """设置模拟历史数据（用于测试）
        
        Args:
            history_data: 进程名到历史分数的映射
        """
        self._mock_history = history_data


def test_window_priority():
    """测试窗口优先级功能"""
    print("🧪 测试窗口优先级计算...")
    
    # 创建模拟窗口数据
    class MockWindow:
        def __init__(self, hwnd, title, process_name, rect=(100, 100, 900, 700)):
            self.hwnd = hwnd
            self.title = title
            self.process_name = process_name
            self.rect = rect
            self.is_visible = True
            self.is_enabled = True
            self.class_name = "MockWindow"
    
    windows = [
        MockWindow(1001, "Visual Studio Code", "Code.exe"),
        MockWindow(1002, "Google Chrome", "chrome.exe"),
        MockWindow(1003, "微信", "WeChat.exe"),
        MockWindow(1004, "Notepad", "notepad.exe"),
        MockWindow(1005, "Windows Terminal", "WindowsTerminal.exe"),
    ]
    
    # 模拟活跃窗口信息
    active_info = {
        'foreground_window': windows[1],  # Chrome是前台
        'active_windows': windows[:3],    # 前三个是活跃的
        'recent_windows': windows[:4],    # 前四个是最近使用的
        'total_windows': len(windows)
    }
    
    # 创建优先级管理器并计算
    manager = WindowPriorityManager()
    manager.set_mock_history_for_testing({
        'code.exe': 30,
        'chrome.exe': 20,
        'wechat.exe': 15
    })
    
    priorities = manager.calculate_window_priorities(windows, active_info)
    
    print("窗口优先级排序结果:")
    for i, priority in enumerate(priorities):
        flags_str = ", ".join(priority.special_flags) if priority.special_flags else "无"
        print(f"  {i+1}. {priority.window.title}")
        print(f"     进程: {priority.window.process_name}")
        print(f"     总分: {priority.total_score}")
        print(f"     标识: {flags_str}")
        print()
    
    # 显示统计摘要
    summary = manager.get_priority_summary(priorities)
    print("统计摘要:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    test_window_priority()