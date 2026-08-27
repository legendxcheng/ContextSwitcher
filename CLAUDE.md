# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ContextSwitcher is a Windows desktop application designed for developers to manage multiple tasks and their associated window contexts. It allows binding multiple windows to tasks and switching between task contexts using global hotkeys (Ctrl+Alt+1-9).

## Commands

### Build and Development
- **Build executable**: `build.bat` - Creates a standalone executable using PyInstaller
- **Manual build**: `pyinstaller --onefile --windowed --name="ContextSwitcher" --icon=icon.ico main.py`
- **Run application**: `python main.py`
- **Install dependencies**: `pip install -r requirements.txt`

### Testing
- Run individual test files: `python test_*.py` (各种测试脚本)
- Main verification scripts:
  - `python verify_simple.py` - 基本功能验证
  - `python verify_explorer_feature.py` - Explorer窗口功能验证

## Architecture

### Core Components (core/)
- **TaskManager** (`task_manager.py`): 核心任务管理，处理任务的创建、编辑、删除和多窗口绑定
- **WindowManager** (`window_manager.py`): Windows API封装，管理窗口枚举、激活、状态检测
- **HotkeyManager** (`hotkey_manager.py`): 全局热键注册和处理 (Ctrl+Alt+1-9)
- **SmartRebindManager** (`smart_rebind_manager.py`): 智能重新绑定，处理窗口失效后的重新绑定
- **TaskStatusManager** (`task_status_manager.py`): 任务状态管理 (TODO, IN_PROGRESS, BLOCKED, REVIEW, COMPLETED, PAUSED)
- **ExplorerHelper** (`explorer_helper.py`): Explorer窗口的特殊处理，支持路径获取和恢复
- **AppHelpers** (`app_helpers/`): v1.2.0 新增，智能窗口恢复辅助模块
  - `base_app_helper.py`: 抽象基类
  - `terminal_helper.py`: Windows Terminal/PowerShell/CMD 支持
  - `vscode_helper.py`: VS Code 支持
  - `app_helper_registry.py`: 辅助类注册表

### GUI Components (gui/)
- **MainWindow** (`main_window.py`): 主窗口界面，实现多个接口的架构设计
- **TaskSwitcherDialog** (`task_switcher_dialog.py`): 热键触发的任务切换器弹窗
- **TaskDialog** (`task_dialog.py`): 任务创建和编辑对话框
- **SettingsDialog** (`settings_dialog.py`): 应用设置对话框
- **WindowSelector** (`window_selector.py`): 窗口选择器，用于窗口绑定
- GUI架构采用接口分离设计:
  - **EventController**: 事件处理控制器
  - **WindowStateManager**: 窗口状态管理
  - **NotificationController**: 通知控制器
  - **UILayoutManager**: 布局管理器
  - **ActionDispatcher**: 动作分发器

### Utilities (utils/)
- **DataStorage** (`data_storage.py`): JSON数据持久化
- **ScreenHelper** (`screen_helper.py`): 屏幕相关工具函数
- **DialogPositionManager** (`dialog_position_manager.py`): 对话框位置管理
- **Config** (`config.py`): 配置管理
- **ToastManager** (`toast_manager.py`): Windows Toast通知

### Key Features
- **多窗口绑定**: 一个任务可以绑定多个窗口，支持Explorer窗口的路径记忆
- **全局热键**: Ctrl+Alt+1-9 快速切换任务上下文
- **智能重绑定**: 当绑定的窗口失效时，自动提示重新绑定到相似窗口
- **任务状态管理**: 支持多种任务状态跟踪
- **窗口状态恢复**: 记忆并恢复窗口位置和大小
- **Explorer集成**: 特殊支持Explorer窗口的文件夹路径记忆和恢复

## Project Structure Notes

### Main Entry Point
`main.py` 是应用程序入口，创建 ContextSwitcher 类实例，按顺序初始化所有组件：
1. DataStorage (数据存储)
2. TaskManager (任务管理器)
3. HotkeyManager (热键管理器)
4. SmartRebindManager (智能重新绑定管理器)
5. TaskStatusManager (任务状态管理器)
6. MainWindow (主窗口)
7. TaskSwitcherDialog (任务切换器)

### GUI Architecture
主窗口采用接口分离的架构设计，MainWindow类实现多个接口：
- IWindowActions, IWindowProvider: 窗口操作接口
- INotificationProvider: 通知接口  
- ILayoutProvider: 布局接口
- IActionProvider: 动作接口

### Data Model
- **Task**: 任务数据类，包含ID、名称、描述、状态、绑定窗口列表等
- **BoundWindow**: 绑定窗口信息，包含句柄、标题、进程名、绑定时间、Explorer路径等
- **TaskStatus**: 任务状态枚举 (TODO, IN_PROGRESS, BLOCKED, REVIEW, COMPLETED, PAUSED)

### Threading and Safety
- GUI运行在主线程
- 热键监听运行在独立线程
- 使用线程安全的通信机制在热键线程和GUI线程间传递事件
- 窗口操作通过消息队列进行线程安全处理

### Dependencies
- **PySide6**: GUI框架
- **pywin32**: Windows API访问
- **pynput**: 全局热键监听
- **Pillow**: 图像处理（图标转换）
- **win10toast**: Windows Toast通知

## Development Notes

### Windows-Only Application
此应用专为Windows平台设计，大量使用Windows API和平台特定功能。

### Configuration System
使用 `utils/config.py` 进行配置管理，支持窗口配置、热键配置等。

### Testing Strategy
项目包含多个测试和验证脚本：
- 功能验证脚本 (verify_*.py)
- 单元测试脚本 (test_*.py)
- UI修复和线程安全测试

### Build System
使用PyInstaller打包成单文件可执行程序，配置文件为 `ContextSwitcher.spec`。
