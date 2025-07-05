# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ContextSwitcher is a Windows desktop utility designed for developers who work with multiple parallel tasks. It functions as a "second brain" for developers, allowing them to manage task contexts and quickly switch between associated application windows using global hotkeys.

## Core Architecture

This is a Windows-specific Python application that serves as a task and window context manager. The main components include:

- **Task Management**: Users can create, edit, and delete development tasks
- **Multi-Window Binding**: Each task can be bound to multiple application windows (VS Code, browser, etc.)
- **Global Hotkey System**: Ctrl+Alt+[1-9] shortcuts to instantly switch to tasks and their bound windows
- **Data Persistence**: Task lists with window bindings are saved locally in `%APPDATA%/tasks.json`

## Technology Stack

- **Language**: Python 3.11+
- **GUI Framework**: FreeSimpleGUI (free alternative to PySimpleGUI, no licensing restrictions)
- **Windows Integration**: pywin32 for Windows API calls
- **Global Hotkeys**: pynput library (integrates well with FreeSimpleGUI)
- **System Tray**: FreeSimpleGUIWx for system tray functionality (optional)
- **Data Storage**: JSON files in %APPDATA%

## Key Features

### Core Features (v1.0)
1. **Always-on-Top Window**: Main interface stays visible during development
2. **Multi-Window Task Binding**: Link development tasks to multiple application windows
3. **Quick Context Switching**: Global hotkeys update timestamps and activate bound windows
4. **Graceful Degradation**: Handles closed/invalid windows elegantly
5. **Local Data Storage**: Persists task data between sessions

### Experimental Features (Future)
- **Virtual Desktop Integration**: Create dedicated virtual desktops for tasks (HIGH RISK - depends on undocumented Windows APIs)

## Development Context

- **Target Platform**: Windows 10/11 (version 1903+ for virtual desktop features)
- **UI Requirements**: Minimal, high information density interface
- **Performance Goals**: <5s startup (Python), <2% CPU, <150MB RAM, <100ms hotkey response
- **User Experience**: Zero learning curve, hotkey-driven workflow

## Project Requirements (from PRD)

The application must implement a table-based interface showing:
- Task names
- Bound window information (multiple windows per task)
- Last accessed timestamps

Core functionality includes adding/editing/deleting tasks, binding them to multiple windows, and using Ctrl+Alt+[1-9] shortcuts for instant context switching.

## API Risk Assessment

### High Risk Components
- **Virtual Desktop APIs**: pyvda library depends on undocumented Windows COM interfaces that frequently break with Windows updates
- **global-hotkeys**: Limited maintenance, keyboard layout compatibility issues

### Low Risk Components  
- **pywin32**: Mature, stable library with active maintenance
- **FreeSimpleGUI**: Open-source fork of PySimpleGUI with LGPL license, actively maintained
- **pynput**: Stable library for global hotkey handling

## Development Strategy

1. **Phase 1**: Implement core window management without virtual desktop dependency
2. **Phase 2**: Add virtual desktop support as optional experimental feature
3. **Phase 3**: Implement comprehensive error handling and fallback mechanisms

## Common Development Commands

### Installation
```bash
pip install FreeSimpleGUI
pip install pywin32
pip install pynput
pip install FreeSimpleGUIWx  # Optional, for system tray
```

### Development
- `python main.py` - Run application
- `python -m pytest tests/` - Run tests (when implemented)

### Package for Distribution
```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

## Development Notes

- **GUI Framework**: Use FreeSimpleGUI instead of PySimpleGUI (avoids licensing issues)
- **Global Hotkeys**: Use pynput library for system-wide hotkey detection
- **Always-on-Top**: Use `keep_on_top=True` parameter in FreeSimpleGUI windows
- **System Tray**: Optional FreeSimpleGUIWx for system tray integration
- **Prioritize stability** over advanced features
- **Implement comprehensive error handling** for Windows API calls
- **Consider virtual desktop functionality** as experimental/optional
- **Test thoroughly** across different Windows versions and updates

## FreeSimpleGUI Specific Notes

- FreeSimpleGUI is the recommended replacement for PySimpleGUI (no licensing restrictions)
- Same API as PySimpleGUI 4.x, so existing tutorials apply
- Table component works well for task list display
- Built-in file dialogs for multi-window selection
- Easy integration with global hotkey libraries

## 执行规程：引导式执行

### 元规则
1. 每个回复都必须以 [模式：当前模式] 开头
2. 仅在收到用户明确指令（"进入 X 模式"）时才可更改模式。每一次回复，只能处于1个模式，不能自动切换模式

### 可用模式

**调研 (RESEARCH)**：收集信息并提问。禁止提出建议、计划或代码。

**创新 (INNOVATE)**：进行头脑风暴，探讨各种选项及权衡利弊。禁止制定具体计划或编写代码。

**计划 (PLAN)**：为执行创建详细的、带编号的检查清单。禁止编写代码。允许写.md文档（开发计划文档）。等待用户批准。大多数情况，计划模式，都需要产出一个开发计划文档(markdown)

**执行 (EXECUTE)**：仅执行已批准的检查清单。禁止偏离。若发现问题 -> 则回到计划模式。需要用户输入"进入执行模式"。

**审查 (REVIEW)**：核对执行情况与检查清单。报告所有偏差 (:warning:）。结论：匹配 (:white_check_mark:) / 偏差 (:cross_mark:)。