# Phase 2 开发计划：增强功能实现

**项目**: ContextSwitcher - 开发者多任务切换器  
**阶段**: Phase 2 (v1.1 增强功能)  
**前置条件**: Phase 1 (v1.0) 核心功能已完成  
**预计时间**: 4-5天 (20-25小时)  
**创建日期**: 2025年7月5日  

---

## 📋 阶段目标

在Phase 1核心功能基础上，实现用户体验和功能增强：
- 智能重新绑定功能
- 任务状态管理系统
- 高级复制功能(LLM提示模板)
- 窗口分组显示优化
- 系统托盘集成
- 用户体验全面提升

---

## 🎯 Phase 2 功能清单

### 核心增强功能
- **智能重新绑定**: 窗口失效时提示用户重新绑定
- **任务状态管理**: 增加状态列（待办、进行中、已阻塞）
- **高级复制功能**: 任务名称+LLM提示模板复制到剪贴板
- **窗口分组显示**: 更好地展示多窗口绑定信息

### 用户体验优化
- **系统托盘集成**: 最小化到托盘，托盘菜单
- **界面优化**: 更多视觉反馈和状态指示
- **快捷操作**: 右键菜单、快捷键扩展
- **设置面板**: 可配置的选项和偏好设置

---

## 📝 详细任务清单

### 任务1: 智能重新绑定功能 (4-5小时)
**优先级**: 高  
**依赖**: Phase 1 完成

**子任务**:
- [ ] 实现窗口失效智能检测算法
- [ ] 创建重新绑定对话框
- [ ] 实现同名窗口自动匹配
- [ ] 批量重新绑定功能
- [ ] 绑定历史记录功能

**核心功能**:
```python
class SmartRebindManager:
    def __init__(self, task_manager, window_manager):
        self.task_manager = task_manager
        self.window_manager = window_manager
        self.binding_history = []
    
    def detect_invalid_windows(self, task):
        """检测任务中的失效窗口"""
        invalid_windows = []
        for window in task.bound_windows:
            if not self.window_manager.is_window_valid(window.hwnd):
                invalid_windows.append(window)
        return invalid_windows
    
    def suggest_replacements(self, invalid_window):
        """为失效窗口建议替代窗口"""
        current_windows = self.window_manager.enumerate_windows()
        suggestions = []
        
        # 基于窗口标题相似度匹配
        for window in current_windows:
            similarity = self._calculate_similarity(
                invalid_window.title, window.title
            )
            if similarity > 0.7:  # 70%相似度阈值
                suggestions.append((window, similarity))
        
        return sorted(suggestions, key=lambda x: x[1], reverse=True)
    
    def auto_rebind_windows(self, task):
        """自动重新绑定窗口"""
        invalid_windows = self.detect_invalid_windows(task)
        rebind_results = []
        
        for invalid_window in invalid_windows:
            suggestions = self.suggest_replacements(invalid_window)
            if suggestions and suggestions[0][1] > 0.9:  # 90%相似度自动绑定
                new_window = suggestions[0][0]
                task.replace_window(invalid_window, new_window)
                rebind_results.append((invalid_window, new_window, 'auto'))
        
        return rebind_results
```

**验收标准**:
- [ ] 能够检测到失效的窗口绑定
- [ ] 提供智能的替代窗口建议
- [ ] 支持手动和自动重新绑定
- [ ] 保存绑定历史记录

---

### 任务2: 任务状态管理系统 (3-4小时)
**优先级**: 高  
**依赖**: 任务1

**子任务**:
- [ ] 扩展Task数据模型，增加状态字段
- [ ] 实现状态转换逻辑
- [ ] 创建状态选择UI组件
- [ ] 状态图标和颜色方案
- [ ] 状态变更历史记录

**状态定义**:
```python
from enum import Enum

class TaskStatus(Enum):
    TODO = "待办"
    IN_PROGRESS = "进行中"
    BLOCKED = "已阻塞"
    REVIEW = "待审查"
    COMPLETED = "已完成"
    PAUSED = "已暂停"

class TaskStatusManager:
    STATUS_COLORS = {
        TaskStatus.TODO: "#808080",        # 灰色
        TaskStatus.IN_PROGRESS: "#0078D4", # 蓝色
        TaskStatus.BLOCKED: "#D13438",     # 红色
        TaskStatus.REVIEW: "#FF8C00",      # 橙色
        TaskStatus.COMPLETED: "#107C10",   # 绿色
        TaskStatus.PAUSED: "#5C2D91"       # 紫色
    }
    
    STATUS_ICONS = {
        TaskStatus.TODO: "○",
        TaskStatus.IN_PROGRESS: "▶",
        TaskStatus.BLOCKED: "⚠",
        TaskStatus.REVIEW: "👁",
        TaskStatus.COMPLETED: "✓",
        TaskStatus.PAUSED: "⏸"
    }
    
    def __init__(self):
        self.status_history = {}
    
    def change_status(self, task_id, new_status, reason=""):
        """改变任务状态"""
        timestamp = datetime.now().isoformat()
        
        if task_id not in self.status_history:
            self.status_history[task_id] = []
        
        self.status_history[task_id].append({
            'timestamp': timestamp,
            'status': new_status,
            'reason': reason
        })
        
        return True
    
    def get_status_icon(self, status):
        """获取状态图标"""
        return self.STATUS_ICONS.get(status, "○")
    
    def get_status_color(self, status):
        """获取状态颜色"""
        return self.STATUS_COLORS.get(status, "#808080")
```

**验收标准**:
- [ ] 支持6种基本任务状态
- [ ] 状态变更有视觉反馈
- [ ] 保存状态变更历史
- [ ] 界面显示状态图标和颜色

---

### 任务3: 高级复制功能 (2-3小时)
**优先级**: 中  
**依赖**: 任务2

**子任务**:
- [ ] 设计LLM提示模板系统
- [ ] 实现任务信息格式化
- [ ] 剪贴板操作功能
- [ ] 模板自定义界面
- [ ] 预设模板库

**核心功能**:
```python
class LLMPromptGenerator:
    DEFAULT_TEMPLATES = {
        'context_switch': """
当前任务: {task_name}
状态: {status}
绑定窗口: {windows}
最后处理: {last_accessed}
        
请帮我快速回到这个任务的工作状态，我需要：
1. 回顾当前进度
2. 确定下一步操作
3. 重新聚焦在这个任务上
        """,
        
        'debug_help': """
我在处理任务: {task_name}
当前状态: {status}
相关工具: {windows}
        
遇到了问题需要调试帮助，请协助我：
1. 分析可能的问题原因
2. 提供调试思路
3. 建议解决方案
        """,
        
        'task_summary': """
任务: {task_name}
状态: {status}
工作环境: {windows}
处理时间: {last_accessed}
        
请帮我总结这个任务的当前状态和后续计划。
        """
    }
    
    def __init__(self):
        self.custom_templates = {}
    
    def generate_prompt(self, task, template_name='context_switch'):
        """生成LLM提示"""
        template = self.DEFAULT_TEMPLATES.get(template_name) or \
                  self.custom_templates.get(template_name)
        
        if not template:
            return f"任务: {task.name}\n状态: {task.status}"
        
        # 格式化窗口信息
        windows_info = ", ".join([w.title for w in task.bound_windows])
        
        return template.format(
            task_name=task.name,
            status=task.status.value,
            windows=windows_info,
            last_accessed=task.last_accessed
        )
    
    def copy_to_clipboard(self, text):
        """复制到剪贴板"""
        import pyperclip
        pyperclip.copy(text)
        return True
```

**验收标准**:
- [ ] 支持多种预设LLM提示模板
- [ ] 能够自定义模板
- [ ] 一键复制任务信息到剪贴板
- [ ] 模板变量自动替换

---

### 任务4: 窗口分组显示优化 (3-4小时)
**优先级**: 中  
**依赖**: 任务1

**子任务**:
- [ ] 重新设计任务列表显示
- [ ] 实现窗口分组展示
- [ ] 添加窗口缩略图预览(可选)
- [ ] 分组折叠/展开功能
- [ ] 窗口状态实时更新

**界面设计**:
```python
def create_enhanced_task_row(task):
    """创建增强的任务行显示"""
    # 主任务行
    main_row = [
        sg.Text(f"▶ {task.name}" if task.is_current else f"  {task.name}",
               font=('Segoe UI', 10, 'bold' if task.is_current else 'normal')),
        sg.Text(task.status.value, text_color=get_status_color(task.status)),
        sg.Text(task.last_accessed, font=('Segoe UI', 8)),
        sg.Button("⋯", key=f"-TASK_MENU_{task.id}-", size=(2, 1))
    ]
    
    # 窗口分组行
    window_rows = []
    for i, window in enumerate(task.bound_windows):
        status_icon = "✓" if window.is_valid else "✗"
        status_color = "#107C10" if window.is_valid else "#D13438"
        
        window_row = [
            sg.Text("    ├─", font=('Consolas', 8)),
            sg.Text(status_icon, text_color=status_color),
            sg.Text(window.title[:40] + "..." if len(window.title) > 40 else window.title,
                   font=('Segoe UI', 9)),
            sg.Text(window.process_name, font=('Segoe UI', 8), text_color="#666666")
        ]
        window_rows.append(window_row)
    
    return [main_row] + window_rows

class EnhancedTaskDisplay:
    def __init__(self):
        self.collapsed_tasks = set()
    
    def create_task_list_layout(self, tasks):
        """创建增强的任务列表布局"""
        layout = []
        
        for task in tasks:
            # 任务标题行
            title_row = self.create_task_title_row(task)
            layout.append(title_row)
            
            # 窗口详情行(可折叠)
            if task.id not in self.collapsed_tasks:
                window_rows = self.create_window_detail_rows(task)
                layout.extend(window_rows)
        
        return layout
    
    def toggle_task_collapse(self, task_id):
        """切换任务折叠状态"""
        if task_id in self.collapsed_tasks:
            self.collapsed_tasks.remove(task_id)
        else:
            self.collapsed_tasks.add(task_id)
```

**验收标准**:
- [ ] 清晰展示任务和绑定窗口的层级关系
- [ ] 支持折叠/展开窗口详情
- [ ] 实时显示窗口有效性状态
- [ ] 窗口信息显示优化(标题截断、进程名等)

---

### 任务5: 系统托盘集成 (2-3小时)
**优先级**: 中  
**依赖**: 无

**子任务**:
- [ ] 实现系统托盘图标
- [ ] 创建托盘右键菜单
- [ ] 最小化到托盘功能
- [ ] 托盘图标状态指示
- [ ] 托盘气泡通知

**核心功能**:
```python
import pystray
from PIL import Image
import threading

class SystemTrayManager:
    def __init__(self, main_window, task_manager):
        self.main_window = main_window
        self.task_manager = task_manager
        self.tray_icon = None
        self.is_visible = True
    
    def create_tray_icon(self):
        """创建托盘图标"""
        # 创建简单的图标
        image = Image.new('RGB', (64, 64), color='blue')
        
        # 创建菜单
        menu = pystray.Menu(
            pystray.MenuItem("显示/隐藏", self.toggle_window),
            pystray.MenuItem("添加任务", self.add_task),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self.quit_application)
        )
        
        self.tray_icon = pystray.Icon("ContextSwitcher", image, menu=menu)
        return self.tray_icon
    
    def start_tray(self):
        """启动托盘"""
        def run_tray():
            self.tray_icon = self.create_tray_icon()
            self.tray_icon.run()
        
        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()
    
    def toggle_window(self, icon, item):
        """切换窗口显示/隐藏"""
        if self.is_visible:
            self.main_window.hide()
        else:
            self.main_window.show()
        self.is_visible = not self.is_visible
    
    def show_notification(self, title, message):
        """显示托盘通知"""
        if self.tray_icon:
            self.tray_icon.notify(message, title)
    
    def update_icon_status(self, status):
        """更新托盘图标状态"""
        # 根据当前任务状态更新图标
        pass
```

**验收标准**:
- [ ] 能够最小化到系统托盘
- [ ] 托盘右键菜单功能正常
- [ ] 双击托盘图标显示/隐藏窗口
- [ ] 支持托盘通知功能

---

### 任务6: 设置面板和配置管理 (2-3小时)
**优先级**: 低  
**依赖**: 任务5

**子任务**:
- [ ] 创建设置对话框界面
- [ ] 实现配置文件管理
- [ ] 热键自定义功能
- [ ] 主题和外观设置
- [ ] 行为偏好配置

**设置项目**:
```python
class SettingsManager:
    DEFAULT_SETTINGS = {
        'appearance': {
            'theme': 'DarkGrey13',
            'always_on_top': True,
            'window_opacity': 0.95,
            'compact_mode': False
        },
        'behavior': {
            'minimize_to_tray': True,
            'start_with_system': False,
            'auto_save_interval': 30,
            'confirm_delete': True
        },
        'hotkeys': {
            'task_1': 'ctrl+alt+1',
            'task_2': 'ctrl+alt+2',
            # ... 其他热键
            'show_hide': 'ctrl+alt+space'
        },
        'advanced': {
            'debug_mode': False,
            'log_level': 'INFO',
            'max_recent_tasks': 10
        }
    }
    
    def __init__(self, config_file_path):
        self.config_file = config_file_path
        self.settings = self.load_settings()
    
    def load_settings(self):
        """加载设置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
            
            # 合并默认设置和用户设置
            settings = self.DEFAULT_SETTINGS.copy()
            settings.update(user_settings)
            return settings
        except FileNotFoundError:
            return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        """保存设置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
    
    def get(self, category, key, default=None):
        """获取设置值"""
        return self.settings.get(category, {}).get(key, default)
    
    def set(self, category, key, value):
        """设置值"""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
```

**验收标准**:
- [ ] 设置对话框界面友好
- [ ] 支持热键自定义
- [ ] 外观和行为可配置
- [ ] 设置能够持久化保存

---

## ⏰ 开发时间安排

### 第1天 (5-6小时)
- **上午**: 任务1 (智能重新绑定功能)
- **下午**: 任务2 (任务状态管理系统)

### 第2天 (5-6小时)  
- **上午**: 任务3 (高级复制功能) + 开始任务4 (窗口分组显示)
- **下午**: 完成任务4 + 任务5 (系统托盘集成)

### 第3天 (4-5小时)
- **上午**: 任务6 (设置面板) 
- **下午**: 集成测试和用户体验优化

### 第4天 (3-4小时) - 可选
- **全天**: 功能完善、性能优化、文档更新

---

## ✅ Phase 2 完成标准

**功能性验收**:
- ✅ 智能重新绑定功能正常工作
- ✅ 任务状态管理完整实现
- ✅ LLM提示模板复制功能
- ✅ 窗口分组显示优化
- ✅ 系统托盘功能正常
- ✅ 设置面板可用

**用户体验验收**:
- ✅ 界面更加直观和现代化
- ✅ 操作更加便捷和高效
- ✅ 状态反馈清晰及时
- ✅ 配置选项丰富合理

**技术质量验收**:
- ✅ 代码质量保持高标准
- ✅ 性能没有明显下降
- ✅ 错误处理完善
- ✅ 向后兼容性良好

---

## 🔄 下一阶段预览

**Phase 3 实验性功能**:
- 虚拟桌面集成 (高风险)
- 简易计时器功能
- 任务排序和优先级
- 高级窗口管理
- 工作流自动化

---

## 📚 参考资料

**技术文档**:
- pystray文档: https://pystray.readthedocs.io/
- pyperclip文档: https://pyperclip.readthedocs.io/
- PIL/Pillow文档: https://pillow.readthedocs.io/

**设计参考**:
- Windows 11 设计语言
- 现代化桌面应用UI模式
- 任务管理工具最佳实践