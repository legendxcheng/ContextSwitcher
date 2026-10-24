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

---

## Herdr Kanban 子项目 (`kanban/`)

### 项目概述
`kanban/` 是一个独立的 Tauri 2 + React 19 + TypeScript 桌面应用，作为 ContextSwitcher 的可视化看板前端。核心设计理念：**ContextSwitcher 的一个 Task = 一个 Workspace = 一个 Kanban Project**。

### Tech Stack
- **前端**: React 19 + TypeScript + Vite, CSS custom properties token system (dark theme)
- **后端**: Tauri 2 (Rust), SQLite via rusqlite (bundled), rfd (native folder picker)
- **富文本编辑**: Tiptap 3，支持 `@file` 和 `$skill` mention
- **数据存储**: `%APPDATA%\herdr-kanban\kanban.db`

### Build and Development
- **开发模式**: `npm run tauri dev` (在 `kanban/` 目录)
- **类型检查**: `npx tsc --noEmit`
- **Rust检查**: `cd src-tauri && cargo check`
- **构建**: `npm run tauri build`

### 数据模型

#### Project (看板项目 = CS任务 = Workspace)
- `id`, `name`, `root_path`, `herdr_workspace`, `cs_task_id` (关联 ContextSwitcher 任务), `created_at`

#### Task (看板卡片)
- `id`, `project_id`, `name`, `status` (todo/in_progress/done), `prompt_json` (Tiptap JSON), `prompt_snapshot`, `dispatched_at`, `dispatched_to`, `created_at`, `updated_at`

### 前端组件结构 (`kanban/src/`)
- **`App.tsx`**: 根组件，挂载 `ToastContainer`，管理项目列表和选中状态
- **`ProjectSidebar.tsx`**: 左侧项目列表，新建/编辑通过 `ProjectFormDialog` 弹窗
- **`ProjectFormDialog.tsx`**: 新建/编辑项目对话框，含浏览按钮选择本地目录、CS任务关联选择器
- **`KanbanBoard.tsx`**: 三列看板 (Todo/In Progress/Done)，支持拖拽、键盘快捷键 `N` 新建任务
- **`TaskCard.tsx`**: 只读卡片视图，点击编辑打开 `TaskEditPanel`
- **`TaskEditPanel.tsx`**: 右侧 slide-over 面板，编辑任务名称和 Tiptap prompt
- **`PromptEditor.tsx`**: Tiptap 富文本编辑器，`@` 触发文件搜索，`$` 触发 skill 搜索
- **`Toast.tsx`**: 全局 toast 通知，`notify(message, kind)` 函数可在任意组件调用
- **`api.ts`**: 所有 Tauri invoke 调用的封装
- **`types.ts`**: TypeScript 接口定义

### Rust 命令 (`kanban/src-tauri/src/`)
- `commands.rs`: 所有 `#[tauri::command]` 实现
  - `list/create/update/delete_project`: 项目 CRUD，含 `cs_task_id` 字段
  - `list/create/update/update_status/delete_task`: 任务 CRUD
  - `search_files`, `search_skills`, `read_file_content`, `read_skill_content`: 文件/Skill发现
  - `herdr_list_agents`, `dispatch_to_herdr`: Herdr CLI 集成
  - `pick_folder`: rfd 原生文件夹选择对话框
  - `read_cs_tasks`: 读取 `%APPDATA%\ContextSwitcher\tasks.json` 返回 CS 任务列表
- `db.rs`: SQLite 初始化，含 `ALTER TABLE` 迁移（幂等）
- `models.rs`: `Project`, `Task`, `TaskStatus`, `CsTask`, `DispatchRecord` 数据结构

### ContextSwitcher 集成
- `cs_task_id` 字段关联 Project 和 CS Task
- `read_cs_tasks` 命令解析 CS tasks.json (v1.4.0格式)，提取 `herdr_binding.label` 作为 herdr workspace
- `ProjectFormDialog` 展示 CS 任务列表供用户关联

### UI/UX 设计
- **Dark theme**: OKLCH-inspired 中性色阶 (--n0~--n9) + 蓝色 accent (#5a8fd4)
- **字体**: base 15px，body measure 45-75字符
- **Slide-over 面板**: 任务编辑不再展开卡片，从右侧滑入
- **空状态**: 每列有图标和提示文字
- **拖拽**: 拖拽时卡片半透明，目标列高亮
- **Toast通知**: 操作成功/失败的全局反馈
