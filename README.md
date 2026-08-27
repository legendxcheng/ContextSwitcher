# ContextSwitcher — Windows Task & Workspace Switcher

[简体中文](README.zh-CN.md) | English

[![CI](https://github.com/legendxcheng/ContextSwitcher/actions/workflows/ci.yml/badge.svg)](https://github.com/legendxcheng/ContextSwitcher/actions/workflows/ci.yml)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**A Windows task switcher, desktop workspace manager, and window layout restorer for developers.**

ContextSwitcher is an open-source, local-first Windows productivity app for people who work across several tasks at once. Group application windows by task, save their desktop context, and restore the right workspace with a global hotkey instead of finding and arranging every window again.

It is designed for developer workflows that span VS Code, terminals, browsers, File Explorer, documentation, and AI coding agents.

The interface is available in English and Simplified Chinese and can follow the Windows display language.

> ContextSwitcher is an early-stage, Windows-only open-source project. Feedback and contributions are welcome.

## Why ContextSwitcher?

A task is usually more than one application: an editor, a terminal, documentation, File Explorer, and perhaps an AI agent. ContextSwitcher treats those windows as one resumable context.

Common use cases include:

- A **Windows task switcher** for moving between coding projects.
- A **desktop workspace manager** that groups related application windows.
- A **window layout saver and restorer** for resuming work quickly.
- A task-oriented complement to `Alt+Tab` for heavy multitasking.
- An **AI coding context manager** for parallel agent and terminal workflows.

Core capabilities:

- Bind multiple desktop windows to one task.
- Open the task switcher with `Ctrl+Alt+Space`.
- Summon the main window at the pointer by pressing `Alt` twice.
- Restore window positions and remember File Explorer folders.
- Track task status, priority, subtasks, and focused time.
- Rebind a task when a previously bound window has changed.
- Optionally monitor and focus a matching [Herdr](#optional-herdr-integration) workspace.
- Keep task data on your computer; the app has no telemetry or cloud sync.

## Requirements

- 64-bit Windows 10 or later
- Python 3.10 or later when running from source

ContextSwitcher uses Windows APIs and does not currently support macOS or Linux.

## Install

### Run from source

```powershell
git clone https://github.com/legendxcheng/ContextSwitcher.git
cd ContextSwitcher
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

### Install a packaged release

Packaged installers will appear on the [GitHub Releases](https://github.com/legendxcheng/ContextSwitcher/releases) page. If there is no installer there yet, use the source installation above.

## Quick start

1. Start ContextSwitcher and select **Add Task**.
2. Name the task and select the windows that belong to it.
3. Press `Ctrl+Alt+Space` to open the task switcher.
4. Choose a task to restore its windows.

The task-switcher shortcut and its auto-switch delay can be changed in **Settings**.

## Display language

Open **Settings → Language → Display language** and select:

- **Follow system**
- **English (United States)**
- **简体中文**

The interface updates immediately. Existing installations without a language preference continue to use Simplified Chinese.

## Local data and privacy

Configuration, tasks, backups, and time-tracking data are stored under:

```text
%APPDATA%\ContextSwitcher
```

ContextSwitcher does not send that data anywhere. Window titles and local paths may appear in saved task data, so review and redact those files before attaching them to a public issue.

## Optional Herdr integration

Herdr integration is optional. If `herdr.exe` is installed, ContextSwitcher can associate a task with a Herdr workspace, monitor agent state, focus the relevant terminal, and show notifications when an agent is blocked or finishes. All core window-switching features work without Herdr.

## Development

Install the development dependency and run the test suite:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests -q
```

Build a standalone executable:

```powershell
.\build.bat
```

Build the executable and the Inno Setup installer:

```powershell
winget install --id JRSoftware.InnoSetup --exact
.\build_installer.bat
```

Build output is written to `release\`.

## Contributing

Bug reports, feature proposals, translations, and pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change. For security-sensitive reports, follow [SECURITY.md](SECURITY.md).

## License

ContextSwitcher is available under the [MIT License](LICENSE).
