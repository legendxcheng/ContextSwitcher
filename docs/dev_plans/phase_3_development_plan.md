# Phase 3 开发计划：实验性功能实现

**项目**: ContextSwitcher - 开发者多任务切换器  
**阶段**: Phase 3 (v2.0+ 实验性功能)  
**前置条件**: Phase 1 + Phase 2 完成  
**预计时间**: 5-7天 (25-35小时)  
**创建日期**: 2025年7月5日  
**风险等级**: 高 (包含不稳定API依赖)

---

## ⚠️ 重要声明

**高风险功能警告**: Phase 3 包含依赖不稳定Windows API的功能，特别是虚拟桌面集成。这些功能可能在Windows系统更新后失效，因此被设计为可选的实验性功能，不影响核心应用功能。

---

## 📋 阶段目标

实现ContextSwitcher的前沿和实验性功能：
- **虚拟桌面集成** (核心实验功能)
- 简易计时器和时间统计
- 任务排序和优先级管理
- 高级窗口管理(位置记忆)
- 工作流自动化
- 数据分析和报告

---

## 🎯 Phase 3 功能清单

### 核心实验功能 (高风险)
- **虚拟桌面集成**: 为任务创建专用虚拟桌面
- **高级窗口管理**: 窗口位置、大小记忆和恢复

### 增值功能 (中风险)
- **简易计时器**: 任务专注时长统计
- **任务排序**: 拖拽调整任务顺序
- **工作流自动化**: 任务切换时的自定义动作

### 分析功能 (低风险)
- **生产力分析**: 工作时间和效率报告
- **使用习惯统计**: 任务切换模式分析

---

## 📝 详细任务清单

### 任务1: 虚拟桌面集成 (8-10小时) ⚠️ 高风险
**优先级**: 高 (实验性)  
**风险等级**: 极高  
**依赖**: Phase 2 完成

**技术风险评估**:
- **API稳定性**: 依赖未公开的Windows COM接口
- **系统兼容性**: 仅支持Windows 10 1903+
- **更新风险**: 可能在Windows更新后失效
- **降级策略**: 必须提供传统窗口切换备选方案

**子任务**:
- [ ] 评估pyvda库兼容性和稳定性
- [ ] 实现虚拟桌面检测和创建
- [ ] 任务-虚拟桌面绑定机制
- [ ] 虚拟桌面切换功能
- [ ] 错误处理和降级方案
- [ ] 用户选择退出机制

**核心功能架构**:
```python
import os
import sys
from typing import Optional, List

class VirtualDesktopManager:
    """虚拟桌面管理器 - 实验性功能"""
    
    def __init__(self):
        self.is_available = False
        self.vd_manager = None
        self.desktop_mappings = {}  # task_id -> desktop_id
        self.fallback_mode = True
        
        # 初始化时检测可用性
        self._initialize_virtual_desktop_support()
    
    def _initialize_virtual_desktop_support(self):
        """初始化虚拟桌面支持"""
        try:
            # 检查Windows版本
            if not self._check_windows_version():
                print("⚠️ 虚拟桌面功能需要Windows 10 1903+")
                return
            
            # 尝试导入pyvda
            import pyvda
            self.vd_manager = pyvda.VirtualDesktop
            self.is_available = True
            self.fallback_mode = False
            print("✓ 虚拟桌面功能已启用")
            
        except ImportError:
            print("⚠️ pyvda库未安装，虚拟桌面功能不可用")
        except Exception as e:
            print(f"⚠️ 虚拟桌面初始化失败: {e}")
    
    def _check_windows_version(self):
        """检查Windows版本是否支持虚拟桌面"""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                              r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                build = winreg.QueryValueEx(key, "CurrentBuild")[0]
                return int(build) >= 18362  # Windows 10 1903
        except:
            return False
    
    def create_task_desktop(self, task_id: str, task_name: str) -> Optional[str]:
        """为任务创建专用虚拟桌面"""
        if not self.is_available:
            return None
        
        try:
            # 创建新的虚拟桌面
            desktop = self.vd_manager.create()
            desktop_id = str(desktop.id)
            
            # 记录映射关系
            self.desktop_mappings[task_id] = desktop_id
            
            print(f"✓ 为任务 '{task_name}' 创建虚拟桌面: {desktop_id}")
            return desktop_id
            
        except Exception as e:
            print(f"✗ 创建虚拟桌面失败: {e}")
            return None
    
    def switch_to_task_desktop(self, task_id: str) -> bool:
        """切换到任务对应的虚拟桌面"""
        if not self.is_available or task_id not in self.desktop_mappings:
            return False
        
        try:
            desktop_id = self.desktop_mappings[task_id]
            desktop = self.vd_manager.from_id(desktop_id)
            desktop.go()
            return True
            
        except Exception as e:
            print(f"✗ 切换虚拟桌面失败: {e}")
            # 降级到传统窗口切换
            return False
    
    def move_windows_to_desktop(self, window_handles: List[int], task_id: str) -> bool:
        """将窗口移动到指定任务的虚拟桌面"""
        if not self.is_available or task_id not in self.desktop_mappings:
            return False
        
        try:
            desktop_id = self.desktop_mappings[task_id]
            desktop = self.vd_manager.from_id(desktop_id)
            
            for hwnd in window_handles:
                try:
                    # 将窗口移动到虚拟桌面
                    desktop.move_window(hwnd)
                except Exception as e:
                    print(f"✗ 移动窗口失败 {hwnd}: {e}")
            
            return True
            
        except Exception as e:
            print(f"✗ 批量移动窗口失败: {e}")
            return False
    
    def cleanup_task_desktop(self, task_id: str) -> bool:
        """清理任务对应的虚拟桌面"""
        if not self.is_available or task_id not in self.desktop_mappings:
            return False
        
        try:
            desktop_id = self.desktop_mappings[task_id]
            desktop = self.vd_manager.from_id(desktop_id)
            desktop.remove()
            
            del self.desktop_mappings[task_id]
            return True
            
        except Exception as e:
            print(f"✗ 清理虚拟桌面失败: {e}")
            return False

class EnhancedTaskManager:
    """增强的任务管理器，集成虚拟桌面功能"""
    
    def __init__(self, window_manager):
        self.window_manager = window_manager
        self.vd_manager = VirtualDesktopManager()
        self.tasks = []
        self.current_task_index = -1
    
    def add_task_with_desktop(self, name: str, windows: List[tuple], 
                            use_virtual_desktop: bool = True) -> bool:
        """添加任务并可选创建虚拟桌面"""
        try:
            # 创建基础任务
            task = Task(name=name, bound_windows=windows)
            
            # 如果启用虚拟桌面且可用
            if use_virtual_desktop and self.vd_manager.is_available:
                desktop_id = self.vd_manager.create_task_desktop(task.id, name)
                if desktop_id:
                    task.virtual_desktop_id = desktop_id
                    # 移动窗口到新桌面
                    window_handles = [w[0] for w in windows]
                    self.vd_manager.move_windows_to_desktop(window_handles, task.id)
            
            self.tasks.append(task)
            return True
            
        except Exception as e:
            print(f"✗ 添加任务失败: {e}")
            return False
    
    def switch_to_task_enhanced(self, task_index: int) -> bool:
        """增强的任务切换，支持虚拟桌面"""
        if not (0 <= task_index < len(self.tasks)):
            return False
        
        task = self.tasks[task_index]
        success = False
        
        # 优先尝试虚拟桌面切换
        if hasattr(task, 'virtual_desktop_id') and task.virtual_desktop_id:
            success = self.vd_manager.switch_to_task_desktop(task.id)
        
        # 降级到传统窗口切换
        if not success:
            success = self._traditional_window_switch(task)
        
        if success:
            self.current_task_index = task_index
            task.update_timestamp()
        
        return success
    
    def _traditional_window_switch(self, task) -> bool:
        """传统窗口切换方法(降级方案)"""
        try:
            for window in task.bound_windows:
                if self.window_manager.is_window_valid(window.hwnd):
                    self.window_manager.activate_window(window.hwnd)
            return True
        except:
            return False
```

**验收标准**:
- [ ] 能够检测虚拟桌面API可用性
- [ ] 为任务创建专用虚拟桌面
- [ ] 支持虚拟桌面间的任务切换
- [ ] 窗口能够移动到指定虚拟桌面
- [ ] 提供完整的降级方案
- [ ] 用户可以选择禁用此功能

---

### 任务2: 简易计时器和时间统计 (4-5小时)
**优先级**: 中  
**风险等级**: 低  
**依赖**: Phase 2 完成

**子任务**:
- [ ] 实现任务计时器系统
- [ ] 时间数据存储和统计
- [ ] 时间显示和可视化
- [ ] 工作时间报告生成
- [ ] 时间目标设置功能

**核心功能**:
```python
from datetime import datetime, timedelta
import time
import threading

class TaskTimer:
    """任务计时器"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.start_time = None
        self.total_time = timedelta()
        self.is_running = False
        self.session_start = None
    
    def start(self):
        """开始计时"""
        if not self.is_running:
            self.start_time = datetime.now()
            self.session_start = self.start_time
            self.is_running = True
    
    def pause(self):
        """暂停计时"""
        if self.is_running:
            now = datetime.now()
            session_duration = now - self.session_start
            self.total_time += session_duration
            self.is_running = False
    
    def get_current_duration(self) -> timedelta:
        """获取当前会话时长"""
        if self.is_running and self.session_start:
            return datetime.now() - self.session_start
        return timedelta()
    
    def get_total_duration(self) -> timedelta:
        """获取总时长"""
        total = self.total_time
        if self.is_running:
            total += self.get_current_duration()
        return total

class TimeTrackingManager:
    """时间跟踪管理器"""
    
    def __init__(self):
        self.task_timers = {}
        self.active_task_id = None
        self.time_logs = []  # 详细时间日志
        self.daily_goals = {}  # 每日目标
        
        # 启动后台时间记录线程
        self._start_background_tracking()
    
    def start_task_timer(self, task_id: str):
        """开始任务计时"""
        # 停止当前活跃任务
        if self.active_task_id and self.active_task_id != task_id:
            self.pause_task_timer(self.active_task_id)
        
        # 获取或创建计时器
        if task_id not in self.task_timers:
            self.task_timers[task_id] = TaskTimer(task_id)
        
        self.task_timers[task_id].start()
        self.active_task_id = task_id
        
        # 记录开始日志
        self._log_time_event(task_id, 'start')
    
    def pause_task_timer(self, task_id: str):
        """暂停任务计时"""
        if task_id in self.task_timers:
            self.task_timers[task_id].pause()
            self._log_time_event(task_id, 'pause')
            
            if self.active_task_id == task_id:
                self.active_task_id = None
    
    def get_task_time_info(self, task_id: str) -> dict:
        """获取任务时间信息"""
        if task_id not in self.task_timers:
            return {
                'total_time': timedelta(),
                'current_session': timedelta(),
                'is_running': False,
                'today_time': timedelta()
            }
        
        timer = self.task_timers[task_id]
        today_time = self._get_today_time(task_id)
        
        return {
            'total_time': timer.get_total_duration(),
            'current_session': timer.get_current_duration(),
            'is_running': timer.is_running,
            'today_time': today_time
        }
    
    def _get_today_time(self, task_id: str) -> timedelta:
        """获取今日任务时间"""
        today = datetime.now().date()
        total_today = timedelta()
        
        for log in self.time_logs:
            if (log['task_id'] == task_id and 
                log['timestamp'].date() == today and 
                log['duration'] > timedelta()):
                total_today += log['duration']
        
        return total_today
    
    def _log_time_event(self, task_id: str, event_type: str):
        """记录时间事件"""
        self.time_logs.append({
            'task_id': task_id,
            'event_type': event_type,
            'timestamp': datetime.now(),
            'duration': timedelta()  # 计算会话时间
        })
    
    def generate_daily_report(self, date=None) -> dict:
        """生成日报告"""
        if date is None:
            date = datetime.now().date()
        
        report = {
            'date': date,
            'total_time': timedelta(),
            'tasks': {},
            'most_productive_hour': None,
            'task_switches': 0
        }
        
        # 统计各任务时间
        for log in self.time_logs:
            if log['timestamp'].date() == date:
                task_id = log['task_id']
                if task_id not in report['tasks']:
                    report['tasks'][task_id] = timedelta()
                
                if log['duration'] > timedelta():
                    report['tasks'][task_id] += log['duration']
                    report['total_time'] += log['duration']
        
        return report
    
    def _start_background_tracking(self):
        """启动后台时间跟踪"""
        def track_time():
            while True:
                if self.active_task_id:
                    # 每分钟记录一次活跃状态
                    self._record_activity_minute(self.active_task_id)
                time.sleep(60)  # 每分钟检查一次
        
        thread = threading.Thread(target=track_time, daemon=True)
        thread.start()
    
    def _record_activity_minute(self, task_id: str):
        """记录活动分钟"""
        # 记录这一分钟的活动
        pass
```

**验收标准**:
- [ ] 任务切换时自动开始/停止计时
- [ ] 准确记录任务工作时间
- [ ] 生成日/周/月时间报告
- [ ] 支持时间目标设置和提醒
- [ ] 时间数据可视化显示

---

### 任务3: 任务排序和优先级管理 (3-4小时)
**优先级**: 中  
**风险等级**: 低  
**依赖**: Phase 2 任务状态管理

**子任务**:
- [ ] 实现拖拽排序功能
- [ ] 优先级设置系统
- [ ] 自动排序算法
- [ ] 排序状态持久化
- [ ] 优先级可视化

**核心功能**:
```python
from enum import Enum

class TaskPriority(Enum):
    URGENT = 1      # 紧急
    HIGH = 2        # 高
    MEDIUM = 3      # 中
    LOW = 4         # 低
    DEFERRED = 5    # 延期

class TaskSortManager:
    """任务排序管理器"""
    
    PRIORITY_COLORS = {
        TaskPriority.URGENT: "#FF4444",
        TaskPriority.HIGH: "#FF8800",
        TaskPriority.MEDIUM: "#0078D4",
        TaskPriority.LOW: "#808080",
        TaskPriority.DEFERRED: "#666666"
    }
    
    PRIORITY_ICONS = {
        TaskPriority.URGENT: "🔥",
        TaskPriority.HIGH: "⬆️",
        TaskPriority.MEDIUM: "➡️",
        TaskPriority.LOW: "⬇️",
        TaskPriority.DEFERRED: "⏳"
    }
    
    def __init__(self):
        self.custom_order = []  # 用户自定义顺序
        self.auto_sort_enabled = False
        self.sort_criteria = ['priority', 'last_accessed', 'status']
    
    def set_task_priority(self, task_id: str, priority: TaskPriority):
        """设置任务优先级"""
        # 更新任务优先级
        # 如果启用自动排序，重新排序
        if self.auto_sort_enabled:
            self._auto_sort_tasks()
    
    def move_task(self, from_index: int, to_index: int) -> bool:
        """移动任务位置"""
        try:
            if 0 <= from_index < len(self.custom_order) and 0 <= to_index < len(self.custom_order):
                task_id = self.custom_order.pop(from_index)
                self.custom_order.insert(to_index, task_id)
                self.auto_sort_enabled = False  # 手动排序后禁用自动排序
                return True
        except:
            pass
        return False
    
    def _auto_sort_tasks(self):
        """自动排序任务"""
        # 根据优先级、状态、最后访问时间等排序
        pass
    
    def get_priority_info(self, priority: TaskPriority) -> dict:
        """获取优先级信息"""
        return {
            'color': self.PRIORITY_COLORS.get(priority, "#808080"),
            'icon': self.PRIORITY_ICONS.get(priority, "➡️"),
            'name': priority.name
        }

# 拖拽排序UI组件
class DragDropTaskList:
    """支持拖拽的任务列表"""
    
    def __init__(self, task_manager, sort_manager):
        self.task_manager = task_manager
        self.sort_manager = sort_manager
        self.drag_source = None
        self.drag_target = None
    
    def handle_drag_start(self, task_index: int):
        """处理拖拽开始"""
        self.drag_source = task_index
    
    def handle_drag_over(self, task_index: int):
        """处理拖拽悬停"""
        self.drag_target = task_index
        # 更新视觉反馈
    
    def handle_drop(self):
        """处理拖拽放下"""
        if self.drag_source is not None and self.drag_target is not None:
            success = self.sort_manager.move_task(self.drag_source, self.drag_target)
            if success:
                # 更新UI显示
                self._refresh_task_list()
        
        self.drag_source = None
        self.drag_target = None
```

**验收标准**:
- [ ] 支持鼠标拖拽调整任务顺序
- [ ] 优先级设置和可视化
- [ ] 自动排序功能可开关
- [ ] 排序状态能够保存
- [ ] 排序操作流畅直观

---

### 任务4: 高级窗口管理 (4-5小时)
**优先级**: 中  
**风险等级**: 中  
**依赖**: 任务1 虚拟桌面集成

**子任务**:
- [ ] 窗口位置和大小记忆
- [ ] 窗口布局模板
- [ ] 多显示器支持
- [ ] 窗口自动排列
- [ ] 窗口状态恢复

**核心功能**:
```python
import win32gui
import win32con
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class WindowGeometry:
    """窗口几何信息"""
    x: int
    y: int
    width: int
    height: int
    is_maximized: bool
    is_minimized: bool
    monitor_index: int

class AdvancedWindowManager:
    """高级窗口管理器"""
    
    def __init__(self):
        self.window_layouts = {}  # task_id -> window_geometries
        self.layout_templates = {}  # 预设布局模板
        self.monitor_info = []
        
        self._initialize_monitor_info()
    
    def _initialize_monitor_info(self):
        """初始化显示器信息"""
        def monitor_enum_proc(hmonitor, hdc, rect, data):
            monitor_info = {
                'handle': hmonitor,
                'rect': rect,
                'work_area': win32gui.GetMonitorInfo(hmonitor)['Work']
            }
            self.monitor_info.append(monitor_info)
            return True
        
        win32gui.EnumDisplayMonitors(None, None, monitor_enum_proc, None)
    
    def save_task_layout(self, task_id: str, window_handles: List[int]):
        """保存任务的窗口布局"""
        layout = {}
        
        for hwnd in window_handles:
            try:
                if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    geometry = self._get_window_geometry(hwnd)
                    layout[hwnd] = geometry
            except:
                continue
        
        self.window_layouts[task_id] = layout
        print(f"✓ 保存任务 {task_id} 的窗口布局")
    
    def restore_task_layout(self, task_id: str, window_handles: List[int]) -> bool:
        """恢复任务的窗口布局"""
        if task_id not in self.window_layouts:
            return False
        
        saved_layout = self.window_layouts[task_id]
        restored_count = 0
        
        for hwnd in window_handles:
            if hwnd in saved_layout:
                geometry = saved_layout[hwnd]
                if self._restore_window_geometry(hwnd, geometry):
                    restored_count += 1
        
        print(f"✓ 恢复了 {restored_count} 个窗口的布局")
        return restored_count > 0
    
    def _get_window_geometry(self, hwnd: int) -> WindowGeometry:
        """获取窗口几何信息"""
        rect = win32gui.GetWindowRect(hwnd)
        placement = win32gui.GetWindowPlacement(hwnd)
        
        # 确定窗口所在的显示器
        monitor_index = self._get_window_monitor_index(hwnd)
        
        return WindowGeometry(
            x=rect[0],
            y=rect[1],
            width=rect[2] - rect[0],
            height=rect[3] - rect[1],
            is_maximized=(placement[1] == win32con.SW_SHOWMAXIMIZED),
            is_minimized=(placement[1] == win32con.SW_SHOWMINIMIZED),
            monitor_index=monitor_index
        )
    
    def _restore_window_geometry(self, hwnd: int, geometry: WindowGeometry) -> bool:
        """恢复窗口几何信息"""
        try:
            # 检查目标显示器是否仍然存在
            if geometry.monitor_index >= len(self.monitor_info):
                # 显示器不存在，使用主显示器
                geometry.monitor_index = 0
            
            # 恢复窗口状态
            if geometry.is_maximized:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
            elif geometry.is_minimized:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWMINIMIZED)
            else:
                # 恢复窗口位置和大小
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    geometry.x,
                    geometry.y,
                    geometry.width,
                    geometry.height,
                    win32con.SWP_SHOWWINDOW
                )
            
            return True
            
        except Exception as e:
            print(f"✗ 恢复窗口几何信息失败: {e}")
            return False
    
    def _get_window_monitor_index(self, hwnd: int) -> int:
        """获取窗口所在显示器索引"""
        try:
            window_rect = win32gui.GetWindowRect(hwnd)
            window_center_x = (window_rect[0] + window_rect[2]) // 2
            window_center_y = (window_rect[1] + window_rect[3]) // 2
            
            for i, monitor in enumerate(self.monitor_info):
                rect = monitor['rect']
                if (rect[0] <= window_center_x <= rect[2] and 
                    rect[1] <= window_center_y <= rect[3]):
                    return i
            
            return 0  # 默认主显示器
            
        except:
            return 0
    
    def create_layout_template(self, template_name: str, task_id: str):
        """创建布局模板"""
        if task_id in self.window_layouts:
            self.layout_templates[template_name] = self.window_layouts[task_id].copy()
            print(f"✓ 创建布局模板: {template_name}")
            return True
        return False
    
    def apply_layout_template(self, template_name: str, window_handles: List[int]) -> bool:
        """应用布局模板"""
        if template_name not in self.layout_templates:
            return False
        
        template = self.layout_templates[template_name]
        applied_count = 0
        
        # 简单映射：按顺序应用布局
        for i, hwnd in enumerate(window_handles):
            if i < len(template):
                geometry = list(template.values())[i]
                if self._restore_window_geometry(hwnd, geometry):
                    applied_count += 1
        
        print(f"✓ 应用布局模板，影响 {applied_count} 个窗口")
        return applied_count > 0
```

**验收标准**:
- [ ] 能够记忆并恢复窗口位置大小
- [ ] 支持多显示器环境
- [ ] 提供布局模板功能
- [ ] 窗口状态(最大化/最小化)正确恢复
- [ ] 显示器变化时的适应性处理

---

### 任务5: 工作流自动化 (3-4小时)
**优先级**: 低  
**风险等级**: 低  
**依赖**: 任务2, 任务4

**子任务**:
- [ ] 自定义动作系统
- [ ] 任务切换触发器
- [ ] 条件执行逻辑
- [ ] 动作脚本支持
- [ ] 自动化规则管理

**核心功能**:
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import subprocess
import time

class WorkflowAction(ABC):
    """工作流动作基类"""
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> bool:
        """执行动作"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取动作描述"""
        pass

class LaunchApplicationAction(WorkflowAction):
    """启动应用程序动作"""
    
    def __init__(self, app_path: str, args: str = ""):
        self.app_path = app_path
        self.args = args
    
    def execute(self, context: Dict[str, Any]) -> bool:
        try:
            cmd = f'"{self.app_path}" {self.args}'.strip()
            subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            print(f"✗ 启动应用失败: {e}")
            return False
    
    def get_description(self) -> str:
        return f"启动应用: {self.app_path}"

class SendKeystrokeAction(WorkflowAction):
    """发送按键动作"""
    
    def __init__(self, keys: str):
        self.keys = keys
    
    def execute(self, context: Dict[str, Any]) -> bool:
        try:
            import pyautogui
            pyautogui.hotkey(*self.keys.split('+'))
            return True
        except Exception as e:
            print(f"✗ 发送按键失败: {e}")
            return False
    
    def get_description(self) -> str:
        return f"发送按键: {self.keys}"

class DelayAction(WorkflowAction):
    """延迟动作"""
    
    def __init__(self, seconds: float):
        self.seconds = seconds
    
    def execute(self, context: Dict[str, Any]) -> bool:
        time.sleep(self.seconds)
        return True
    
    def get_description(self) -> str:
        return f"延迟 {self.seconds} 秒"

class WorkflowManager:
    """工作流管理器"""
    
    def __init__(self):
        self.workflows = {}  # task_id -> List[WorkflowAction]
        self.global_workflows = {}  # 全局工作流
        self.enabled = True
    
    def add_task_workflow(self, task_id: str, actions: List[WorkflowAction]):
        """为任务添加工作流"""
        self.workflows[task_id] = actions
        print(f"✓ 为任务 {task_id} 添加了 {len(actions)} 个动作")
    
    def execute_task_workflow(self, task_id: str, context: Dict[str, Any] = None) -> bool:
        """执行任务工作流"""
        if not self.enabled or task_id not in self.workflows:
            return False
        
        if context is None:
            context = {}
        
        actions = self.workflows[task_id]
        success_count = 0
        
        for i, action in enumerate(actions):
            try:
                print(f"执行动作 {i+1}/{len(actions)}: {action.get_description()}")
                if action.execute(context):
                    success_count += 1
                else:
                    print(f"✗ 动作执行失败: {action.get_description()}")
            except Exception as e:
                print(f"✗ 动作执行异常: {e}")
        
        print(f"✓ 工作流完成: {success_count}/{len(actions)} 个动作成功")
        return success_count == len(actions)
    
    def create_quick_workflow(self, task_id: str, workflow_type: str) -> bool:
        """创建快速工作流"""
        quick_workflows = {
            'dev_start': [
                LaunchApplicationAction("code", "."),  # 启动VS Code
                DelayAction(2.0),
                SendKeystrokeAction("ctrl+shift+p"),   # 打开命令面板
            ],
            'focus_mode': [
                SendKeystrokeAction("f11"),             # 全屏
                DelayAction(0.5),
                SendKeystrokeAction("ctrl+shift+p"),   # 禅模式
            ]
        }
        
        if workflow_type in quick_workflows:
            self.workflows[task_id] = quick_workflows[workflow_type]
            return True
        
        return False
```

**验收标准**:
- [ ] 支持常见的自动化动作类型
- [ ] 任务切换时能够触发工作流
- [ ] 提供快速工作流模板
- [ ] 工作流执行状态可见
- [ ] 支持工作流的启用/禁用

---

### 任务6: 数据分析和报告 (2-3小时)
**优先级**: 低  
**风险等级**: 低  
**依赖**: 任务2 时间统计

**子任务**:
- [ ] 使用习惯数据收集
- [ ] 生产力指标计算
- [ ] 报告生成系统
- [ ] 数据可视化
- [ ] 导出功能

**验收标准**:
- [ ] 生成日/周/月工作报告
- [ ] 分析任务切换模式
- [ ] 提供生产力建议
- [ ] 支持数据导出

---

## ⏰ 开发时间安排

### 第1-2天 (10-12小时) - 虚拟桌面集成
- **重点**: 任务1 虚拟桌面集成(高风险功能)
- **策略**: 优先实现降级方案，确保基础功能不受影响

### 第3天 (6-8小时) - 时间管理功能
- **上午**: 任务2 简易计时器和时间统计
- **下午**: 任务3 任务排序和优先级管理

### 第4天 (6-8小时) - 高级功能
- **上午**: 任务4 高级窗口管理
- **下午**: 任务5 工作流自动化

### 第5天 (4-6小时) - 收尾和优化
- **上午**: 任务6 数据分析和报告
- **下午**: 集成测试、性能优化、文档完善

---

## ✅ Phase 3 完成标准

**实验性功能验收**:
- ✅ 虚拟桌面功能可用(含降级方案)
- ✅ 时间统计和报告功能
- ✅ 任务排序和优先级管理
- ✅ 高级窗口管理功能

**稳定性验收**:
- ✅ 核心功能不受实验性功能影响
- ✅ 错误处理完善，降级方案有效
- ✅ 性能无明显下降
- ✅ 用户可选择禁用实验性功能

**用户体验验收**:
- ✅ 实验性功能有明确标识
- ✅ 功能开关易于理解和操作
- ✅ 错误信息友好且有指导性

---

## 🚨 风险缓解策略

### 虚拟桌面API风险
1. **功能开关**: 提供明确的开关控制
2. **降级方案**: 确保传统窗口切换始终可用
3. **错误处理**: 完善的异常捕获和用户提示
4. **版本检测**: 启动时检测Windows版本和API可用性

### 性能风险
1. **后台线程**: 合理使用后台线程，避免阻塞UI
2. **资源管理**: 及时释放不需要的资源
3. **数据限制**: 限制历史数据数量，定期清理

### 兼容性风险
1. **API检测**: 运行时检测所需API的可用性
2. **向后兼容**: 保持配置文件格式的向后兼容
3. **优雅降级**: 功能不可用时提供替代方案

---

## 📚 技术参考

**虚拟桌面相关**:
- pyvda文档: https://github.com/mrob95/pyvda
- Windows虚拟桌面API: 官方文档有限，主要依赖社区研究

**时间统计相关**:
- 时间追踪最佳实践
- 生产力分析方法论

**窗口管理相关**:
- Windows API文档: https://docs.microsoft.com/en-us/windows/win32/api/
- 多显示器开发指南

---

## 🔄 后续规划

**Phase 4 可能方向**:
- AI辅助的任务建议
- 团队协作功能
- 云端数据同步
- 插件系统架构
- 移动端伴侣应用