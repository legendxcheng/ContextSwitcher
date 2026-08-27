# ContextSwitcher — Windows 任务与工作区切换器

简体中文 | [English](README.md)

[![CI](https://github.com/legendxcheng/ContextSwitcher/actions/workflows/ci.yml/badge.svg)](https://github.com/legendxcheng/ContextSwitcher/actions/workflows/ci.yml)
![平台](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
[![许可证：MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**面向开发者的 Windows 任务切换器、桌面工作区管理器和窗口布局恢复工具。**

ContextSwitcher 是一款开源、本地优先的 Windows 效率工具，适合需要同时推进多个任务的人。你可以按任务组织应用窗口，保存桌面上下文，然后通过全局快捷键恢复对应的工作区，不必再次寻找和排列每个窗口。

它特别适合由 VS Code、终端、浏览器、文件资源管理器、文档和 AI 编程 Agent 共同组成的开发工作流。

界面支持英语和简体中文，也可以跟随 Windows 显示语言。

> ContextSwitcher 目前处于早期开源阶段，仅支持 Windows。欢迎反馈问题和参与贡献。

## 为什么使用 ContextSwitcher？

一个任务通常不只是一个应用，而是由编辑器、终端、文档、文件资源管理器，甚至 AI Agent 共同组成。ContextSwitcher 把这些窗口视为一个可以恢复的任务上下文。

常见使用场景包括：

- 在多个编程项目间切换的 **Windows 任务切换器**。
- 将相关应用窗口分组的 **桌面工作区管理器**。
- 快速继续工作的 **窗口布局保存与恢复工具**。
- 面向重度多任务场景、对 `Alt+Tab` 的任务化补充。
- 管理并行 Agent 与终端工作流的 **AI 编程上下文管理器**。

核心能力：

- 将多个桌面窗口绑定到同一个任务。
- 使用 `Ctrl+Alt+Space` 打开任务切换器。
- 连按两次 `Alt`，在鼠标位置唤出主窗口。
- 恢复窗口位置，并记住文件资源管理器的文件夹。
- 管理任务状态、优先级、子任务和专注时间。
- 原窗口变化后，智能重新绑定相似窗口。
- 可选监控和定位对应的 [Herdr](#可选的-herdr-集成) 工作区。
- 任务数据只保存在本机，不包含遥测或云同步。

## 环境要求

- 64 位 Windows 10 或更高版本
- 从源码运行时需要 Python 3.10 或更高版本

ContextSwitcher 使用 Windows API，目前不支持 macOS 或 Linux。

## 安装

### 从源码运行

```powershell
git clone https://github.com/legendxcheng/ContextSwitcher.git
cd ContextSwitcher
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

### 安装打包版本

正式安装包会发布在 [GitHub Releases](https://github.com/legendxcheng/ContextSwitcher/releases) 页面。如果暂时还没有安装包，请按照上面的步骤从源码运行。

## 快速上手

1. 启动 ContextSwitcher，选择“添加任务”。
2. 输入任务名称，并选择属于该任务的窗口。
3. 按 `Ctrl+Alt+Space` 打开任务切换器。
4. 选择任务，恢复它绑定的窗口。

你可以在“设置”中修改任务切换快捷键和自动切换延迟。

## 显示语言

打开“**设置 → 语言 → 显示语言**”，可选择：

- 跟随系统
- English (United States)
- 简体中文

切换后界面会立即更新。对于没有语言偏好设置的旧版本用户，升级后仍会保持简体中文。

## 本地数据与隐私

配置、任务、备份和时间统计数据保存在：

```text
%APPDATA%\ContextSwitcher
```

ContextSwitcher 不会上传这些数据。保存的任务数据可能包含窗口标题和本地路径，因此在将数据文件附加到公开 Issue 前，请先检查并删除敏感信息。

## 可选的 Herdr 集成

Herdr 集成不是使用 ContextSwitcher 的必要条件。安装 `herdr.exe` 后，ContextSwitcher 可以将任务关联到 Herdr 工作区、监控 Agent 状态、定位对应终端，并在 Agent 阻塞或完成时显示通知。未安装 Herdr 时，核心窗口切换功能仍可正常使用。

## 开发

安装开发依赖并运行测试：

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests -q
```

构建独立可执行文件：

```powershell
.\build.bat
```

构建可执行文件和 Inno Setup 安装包：

```powershell
winget install --id JRSoftware.InnoSetup --exact
.\build_installer.bat
```

构建产物会输出到 `release\`。

## 参与贡献

欢迎提交错误报告、功能建议、翻译和 Pull Request。提交修改前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)；涉及安全问题时，请按照 [SECURITY.md](SECURITY.md) 报告。

## 许可证

ContextSwitcher 使用 [MIT License](LICENSE) 开源。
