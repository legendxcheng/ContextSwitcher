# Phase 1 开发计划：核心功能实现

**项目**: ContextSwitcher - 开发者多任务切换器  
**阶段**: Phase 1 (v1.0 核心功能)  
**预计时间**: 3-4天 (15-20小时)  
**创建日期**: 2025年7月5日  

---

## 📋 阶段目标

实现ContextSwitcher的核心功能，包括：
- FreeSimpleGUI主界面（Always-on-Top）
- 任务列表管理（Table组件）
- 多窗口绑定功能
- 全局热键集成（Ctrl+Alt+1-9）
- 数据持久化（JSON存储）

---

## 🛠 技术栈

### 依赖包安装
**需要用户先执行以下安装命令**：
```bash
pip install FreeSimpleGUI
pip install pywin32  
pip install pynput
```

### 核心技术
- **GUI框架**: FreeSimpleGUI (免费，LGPL授权)
- **Windows API**: pywin32 (窗口管理)
- **全局热键**: pynput (系统级热键监听)
- **数据存储**: JSON (本地文件持久化)

---

## 📁 项目文件结构

```
ContextSwitcher/
├── main.py              # 主程序入口
├── gui/
│   ├── __init__.py
│   ├── main_window.py   # 主窗口界面
│   ├── task_dialog.py   # 添加/编辑任务对话框
│   └── window_selector.py # 窗口选择组件
├── core/
│   ├── __init__.py
│   ├── task_manager.py  # 任务管理逻辑
│   ├── window_manager.py # Windows API窗口管理
│   └── hotkey_manager.py # 全局热键管理
├── utils/
│   ├── __init__.py
│   ├── data_storage.py  # JSON数据持久化
│   └── config.py        # 配置管理
├── requirements.txt     # 依赖清单
└── README.md           # 使用说明
```

---

## 📝 详细任务清单

### 任务1: 基础项目结构 (1-2小时)
**优先级**: 高  
**依赖**: 无

**子任务**:
- [x] 创建项目目录结构
- [ ] 创建 `requirements.txt`
- [ ] 创建基础的 `__init__.py` 文件
- [ ] 创建 `main.py` 入口文件
- [ ] 创建基础配置文件

**验收标准**:
- 项目目录结构完整
- 能够成功导入各模块
- main.py能够运行（即使功能为空）

---

### 任务2: Windows API窗口管理 (2-3小时)
**优先级**: 高  
**依赖**: 任务1

**子任务**:
- [ ] 实现 `core/window_manager.py`
  - [ ] `enumerate_windows()` - 枚举所有可见窗口
  - [ ] `get_window_info()` - 获取窗口标题和句柄
  - [ ] `activate_window()` - 激活指定窗口到前台
  - [ ] `is_window_valid()` - 检测窗口是否仍然存在
  - [ ] `activate_multiple_windows()` - 批量激活多个窗口

**核心代码模式**:
```python
import win32gui
import win32con

def enumerate_windows():
    windows = []
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():  # 过滤空标题
                windows.append((hwnd, title))
        return True
    
    win32gui.EnumWindows(callback, windows)
    return windows

def activate_window(hwnd):
    try:
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        return False
```

**验收标准**:
- 能够获取当前所有可见窗口列表
- 能够激活指定窗口到前台
- 能够检测窗口是否已关闭
- 支持批量激活多个窗口

---

### 任务3: 任务数据管理 (1-2小时)
**优先级**: 高  
**依赖**: 任务1

**子任务**:
- [ ] 实现 `core/task_manager.py`
  - [ ] `Task` 类定义（名称、绑定窗口列表、时间戳）
  - [ ] `TaskManager` 类实现
  - [ ] `add_task()` - 添加新任务
  - [ ] `remove_task()` - 删除任务
  - [ ] `edit_task()` - 编辑任务
  - [ ] `switch_to_task()` - 切换到指定任务
  - [ ] `update_timestamp()` - 更新任务时间戳

- [ ] 实现 `utils/data_storage.py`
  - [ ] `save_tasks()` - 保存任务到JSON文件
  - [ ] `load_tasks()` - 从JSON文件加载任务
  - [ ] `get_appdata_path()` - 获取%APPDATA%路径
  - [ ] `backup_data()` - 数据备份功能

**核心代码模式**:
```python
from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class Task:
    name: str
    window_handles: List[int]
    window_titles: List[str]
    last_accessed: str
    created_at: str

class TaskManager:
    def __init__(self):
        self.tasks: List[Task] = []
        self.current_task_index = -1
    
    def add_task(self, name: str, windows: List[tuple]) -> bool:
        # windows: [(hwnd, title), ...]
        pass
    
    def switch_to_task(self, index: int) -> bool:
        # 切换到指定任务并激活所有窗口
        pass
```

**验收标准**:
- 能够创建、编辑、删除任务
- 支持多窗口绑定
- 时间戳自动更新
- 数据能够保存到%APPDATA%并恢复

---

### 任务4: 主界面GUI (3-4小时)
**优先级**: 高  
**依赖**: 任务2, 任务3

**子任务**:
- [ ] 实现 `gui/main_window.py`
  - [ ] Always-on-Top主窗口设计
  - [ ] 任务列表Table组件
  - [ ] 添加/删除/编辑按钮
  - [ ] 窗口大小位置记忆
  - [ ] 事件处理循环
  - [ ] 实时数据更新

**界面设计**:
```python
import FreeSimpleGUI as sg

def create_main_layout():
    return [
        [sg.Text("ContextSwitcher v1.0", font=("Arial", 16))],
        [sg.Table(values=[], 
                  headings=["任务名称", "绑定窗口", "上次处理"],
                  key="-TASK_TABLE-",
                  enable_events=True,
                  justification="left",
                  alternating_row_color="lightgray",
                  selected_row_colors="red on yellow")],
        [sg.Button("添加任务", key="-ADD-"),
         sg.Button("编辑任务", key="-EDIT-"),
         sg.Button("删除任务", key="-DELETE-"),
         sg.Button("刷新", key="-REFRESH-")],
        [sg.Text("快捷键: Ctrl+Alt+1-9 切换任务")]
    ]

def create_main_window():
    window = sg.Window("ContextSwitcher", 
                       create_main_layout(),
                       keep_on_top=True,
                       finalize=True,
                       resizable=True,
                       grab_anywhere=True)
    return window
```

**验收标准**:
- 主窗口始终保持在最前
- 表格能够显示任务列表
- 按钮功能正常响应
- 窗口大小位置能够记忆

---

### 任务5: 窗口选择器 (2-3小时)
**优先级**: 高  
**依赖**: 任务2, 任务4

**子任务**:
- [ ] 实现 `gui/window_selector.py`
  - [ ] 获取当前所有窗口列表
  - [ ] 多选CheckBox界面
  - [ ] 窗口图标显示（可选）
  - [ ] 实时刷新窗口列表
  - [ ] 过滤系统窗口

- [ ] 实现 `gui/task_dialog.py`
  - [ ] 任务名称输入框
  - [ ] 窗口选择器集成
  - [ ] 确认/取消按钮
  - [ ] 数据验证

**界面设计**:
```python
def create_window_selector_layout(windows):
    layout = [
        [sg.Text("选择要绑定的窗口:")],
        [sg.Button("刷新窗口列表", key="-REFRESH_WINDOWS-")],
        [sg.Frame("可用窗口", [
            [sg.Checkbox(title, key=f"-WINDOW_{hwnd}-", 
                        metadata={"hwnd": hwnd, "title": title})]
            for hwnd, title in windows
        ], size=(400, 300), scrollable=True, vertical_scroll_only=True)],
        [sg.Button("确认", key="-OK-"), sg.Button("取消", key="-CANCEL-")]
    ]
    return layout
```

**验收标准**:
- 能够显示所有可见窗口
- 支持多选窗口
- 能够实时刷新窗口列表
- 过滤掉系统和隐藏窗口

---

### 任务6: 全局热键集成 (2-3小时)
**优先级**: 高  
**依赖**: 任务3

**子任务**:
- [ ] 实现 `core/hotkey_manager.py`
  - [ ] 注册Ctrl+Alt+1-9热键
  - [ ] 热键事件处理
  - [ ] 与任务管理器集成
  - [ ] 错误处理和冲突检测
  - [ ] 热键注销功能

**核心代码模式**:
```python
from pynput import keyboard
import threading

class HotkeyManager:
    def __init__(self, task_manager):
        self.task_manager = task_manager
        self.hotkeys = []
        self.listener = None
    
    def register_hotkeys(self):
        # 注册Ctrl+Alt+1-9
        for i in range(1, 10):
            hotkey = f'ctrl+alt+{i}'
            try:
                keyboard.add_hotkey(hotkey, 
                                  lambda idx=i-1: self.on_hotkey(idx))
                self.hotkeys.append(hotkey)
            except Exception as e:
                print(f"Failed to register {hotkey}: {e}")
    
    def on_hotkey(self, task_index):
        # 切换到指定任务
        self.task_manager.switch_to_task(task_index)
    
    def start_listener(self):
        self.listener = keyboard.Listener()
        self.listener.start()
    
    def stop_listener(self):
        if self.listener:
            self.listener.stop()
```

**验收标准**:
- Ctrl+Alt+1-9热键能够正常注册
- 热键触发能够切换到对应任务
- 支持热键冲突检测
- 程序退出时能够正确注销热键

---

### 任务7: 核心功能集成 (2-3小时)
**优先级**: 高  
**依赖**: 任务4, 任务5, 任务6

**子任务**:
- [ ] 主程序逻辑整合
- [ ] 热键触发任务切换
- [ ] 时间戳自动更新
- [ ] 窗口失效检测和处理
- [ ] 错误处理和用户提示
- [ ] 程序优雅退出

**主程序结构**:
```python
# main.py
import FreeSimpleGUI as sg
from gui.main_window import MainWindow
from core.task_manager import TaskManager
from core.hotkey_manager import HotkeyManager
from utils.data_storage import DataStorage

class ContextSwitcher:
    def __init__(self):
        self.task_manager = TaskManager()
        self.hotkey_manager = HotkeyManager(self.task_manager)
        self.data_storage = DataStorage()
        self.main_window = None
    
    def run(self):
        # 加载数据
        # 启动GUI
        # 注册热键
        # 主事件循环
        pass

if __name__ == "__main__":
    app = ContextSwitcher()
    app.run()
```

**验收标准**:
- 所有模块正确集成
- 热键和GUI能够同时工作
- 数据能够正确加载和保存
- 错误能够妥善处理

---

### 任务8: 基础测试和调试 (1-2小时)
**优先级**: 中  
**依赖**: 任务7

**子任务**:
- [ ] 功能完整性测试
- [ ] 边界条件测试
- [ ] 错误处理完善
- [ ] 性能优化
- [ ] 用户体验改进

**测试清单**:
- [ ] 添加任务功能
- [ ] 多窗口绑定功能
- [ ] 热键切换功能
- [ ] 数据持久化功能
- [ ] 窗口失效处理
- [ ] 程序启动和退出

**验收标准**:
- 所有核心功能正常工作
- 无严重崩溃或错误
- 用户界面响应流畅
- 数据不会丢失

---

## ⏰ 开发时间安排

### 第1天 (6-8小时)
- **上午**: 任务1 (项目结构) + 任务2 (Windows API)
- **下午**: 任务3 (数据管理) + 开始任务4 (主界面)

### 第2天 (6-8小时)  
- **上午**: 完成任务4 (主界面) + 任务5 (窗口选择器)
- **下午**: 任务6 (全局热键) + 开始任务7 (功能集成)

### 第3天 (3-4小时)
- **上午**: 完成任务7 (功能集成) + 任务8 (测试调试)

---

## ✅ Phase 1 完成标准

**功能性验收**:
- ✅ 能够添加任务并绑定多个窗口
- ✅ Ctrl+Alt+1-9热键正常工作
- ✅ 窗口切换功能正常
- ✅ 数据能够持久化保存
- ✅ 主界面Always-on-Top正常显示
- ✅ 基本的错误处理

**技术性验收**:
- ✅ 代码结构清晰，模块化良好
- ✅ 无内存泄漏或资源未释放
- ✅ 启动时间 < 5秒
- ✅ 运行时内存占用 < 150MB
- ✅ 热键响应时间 < 100ms

**用户体验验收**:
- ✅ 界面简洁直观，无需学习成本
- ✅ 操作流程顺畅，无卡顿
- ✅ 错误提示友好，有指导性

---

## 🔄 下一阶段预览

**Phase 2 增强功能**:
- 智能重新绑定
- 任务状态管理  
- 高级复制功能
- 系统托盘集成

**Phase 3 实验性功能**:
- 虚拟桌面集成（可选）
- 任务时间统计
- 高级窗口管理

---

## 📞 开发支持

**技术问题**:
- FreeSimpleGUI文档: https://freesimplegui.readthedocs.io/
- pywin32文档: https://pywin32.readthedocs.io/
- pynput文档: https://pynput.readthedocs.io/

**注意事项**:
- 在沙盒环境中开发，需要用户协助安装依赖
- 测试时需要实际的Windows环境
- 热键注册可能与其他软件冲突，需要错误处理