# Wave.exe 集成调研 - 替代方案

## 问题总结

经过多次测试，以下方法都**无法成功**向 Wave.exe 发送快捷键：

1. ❌ PostMessage - Wave.exe 不响应
2. ❌ pynput 全局按键 - Wave.exe 不响应
3. ❌ SendInput API - Wave.exe 不响应
4. ❌ 激活窗口 + SendInput - Wave.exe 不响应
5. ❌ 设置焦点到 Chrome Render 子窗口 - Wave.exe 不响应

**根本原因分析**：
- Wave Terminal 是基于 Chromium/Electron 的应用
- 可能使用了特殊的输入处理机制或安全限制
- 可能只接受真实的物理键盘输入，拒绝程序化的键盘模拟

---

## 替代方案

### 方案 1: 半自动模式（推荐）

**思路**：ContextSwitcher 负责激活 Wave.exe 窗口，用户手动按快捷键

**实现步骤**：
1. 用户在 ContextSwitcher 中切换任务
2. ContextSwitcher 激活 Wave.exe 窗口
3. 显示一个小提示框（Toast 或浮动窗口），提示用户按 Ctrl+Alt+数字
4. 用户手动按下快捷键完成切换

**优点**：
- 实现简单，可靠性高
- 不需要复杂的键盘模拟
- 用户保持控制权

**缺点**：
- 需要用户手动操作
- 不是完全自动化

**实现示例**：
```python
def switch_to_wave_workspace(wave_hwnd, workspace_index):
    """切换到 Wave.exe 的 workspace（半自动）"""
    # 1. 激活 Wave.exe 窗口
    activate_window(wave_hwnd)

    # 2. 显示提示
    show_toast(
        title="Wave Terminal",
        message=f"请按 Ctrl+Alt+{workspace_index} 切换到 workspace {workspace_index}",
        duration=3
    )
```

---

### 方案 2: 检查 Wave Terminal CLI/API

**思路**：Wave Terminal 可能提供命令行接口或 API

**需要调研**：
1. 查看 Wave Terminal 文档：https://docs.waveterm.dev/
2. 查看 GitHub 仓库：https://github.com/wavetermdev/waveterm
3. 查找 `wsh` (Wave Shell) 命令行工具
4. 查找配置文件或 IPC 接口

**可能的命令**（需要验证）：
```bash
# 假设的命令格式
wsh workspace switch 1
wsh workspace goto 2
wave-cli --workspace 3
```

**如果存在 CLI**：
```python
def switch_wave_workspace_cli(workspace_index):
    """使用 CLI 切换 workspace"""
    import subprocess
    subprocess.run(['wsh', 'workspace', 'switch', str(workspace_index)])
```

---

### 方案 3: 配置文件修改

**思路**：如果 Wave Terminal 使用配置文件存储当前 workspace，可以直接修改

**需要调研**：
1. 查找 Wave Terminal 的配置文件位置
2. 分析配置文件格式（JSON/YAML/TOML）
3. 确定 workspace 相关的配置项

**可能的位置**：
- `%APPDATA%\Wave\config.json`
- `%USERPROFILE%\.wave\settings.json`
- `%LOCALAPPDATA%\Wave\User Data\`

**如果可行**：
```python
def switch_wave_workspace_config(workspace_index):
    """通过修改配置文件切换 workspace"""
    import json

    config_path = os.path.expandvars(r'%APPDATA%\Wave\config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    config['currentWorkspace'] = workspace_index

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    # 可能需要重启或重新加载 Wave.exe
```

---

### 方案 4: UI Automation

**思路**：使用 Windows UI Automation 来模拟用户操作

**实现方式**：
```python
import pywinauto

def switch_wave_workspace_ui(wave_hwnd, workspace_index):
    """使用 UI Automation 切换 workspace"""
    app = pywinauto.Application().connect(handle=wave_hwnd)

    # 发送快捷键（可能比 SendInput 更有效）
    app.top_window().type_keys(f'^%{workspace_index}')  # Ctrl+Alt+数字
```

**优点**：
- pywinauto 可能比 SendInput 更有效
- 专门为 UI 自动化设计

**缺点**：
- 需要额外依赖
- 可能仍然无法绕过 Wave.exe 的输入限制

---

### 方案 5: AutoHotkey 中间层

**思路**：使用 AutoHotkey 作为中间层来发送快捷键

**实现步骤**：
1. 创建一个 AutoHotkey 脚本
2. ContextSwitcher 调用 AutoHotkey 脚本
3. AutoHotkey 发送快捷键到 Wave.exe

**AutoHotkey 脚本示例**：
```ahk
; wave_switch.ahk
; 用法: AutoHotkey.exe wave_switch.ahk <workspace_index>

workspace := A_Args[1]

; 激活 Wave.exe
WinActivate, ahk_exe Wave.exe
Sleep, 200

; 发送快捷键
Send, ^!%workspace%
```

**Python 调用**：
```python
def switch_wave_workspace_ahk(workspace_index):
    """使用 AutoHotkey 切换 workspace"""
    import subprocess

    ahk_script = r'C:\path\to\wave_switch.ahk'
    subprocess.run(['AutoHotkey.exe', ahk_script, str(workspace_index)])
```

**优点**：
- AutoHotkey 专门为键盘自动化设计
- 可能比 Python 的方法更有效

**缺点**：
- 需要安装 AutoHotkey
- 增加了依赖复杂度

---

### 方案 6: 智能提示 + 快速访问

**思路**：不尝试自动切换，而是提供快速访问和提示

**实现**：
1. 在任务数据中记录对应的 Wave workspace 编号
2. 切换任务时：
   - 激活 Wave.exe 窗口
   - 在屏幕上显示大号提示："按 Ctrl+Alt+3"
   - 提示 2-3 秒后自动消失
3. 用户看到提示后手动按键

**增强版**：
- 使用半透明浮动窗口显示提示
- 提示窗口显示在 Wave.exe 窗口上方
- 使用大字体和醒目颜色

---

## 推荐实施顺序

### 第一步：调研 Wave Terminal CLI/API（优先级最高）
1. 查看 Wave Terminal 文档和 GitHub
2. 查找 `wsh` 命令行工具
3. 测试是否可以通过 CLI 切换 workspace

**如果存在 CLI**：这是最佳方案，直接实现

### 第二步：实现半自动模式（快速可行）
1. 实现窗口激活 + Toast 提示
2. 用户体验良好，实现简单
3. 可以作为临时方案或最终方案

### 第三步：尝试 UI Automation（如果需要）
1. 安装 pywinauto
2. 测试是否能成功发送快捷键
3. 如果成功，替换半自动模式

### 第四步：考虑 AutoHotkey（最后手段）
1. 只在其他方案都失败时考虑
2. 需要用户安装额外软件

---

## 下一步行动

### 立即可做：
1. **查看 Wave Terminal 文档**
   - 访问：https://docs.waveterm.dev/
   - 查找：CLI、API、wsh 命令
   - 确认：是否有程序化切换 workspace 的方法

2. **检查 Wave Terminal 安装目录**
   - 查找是否有 `wsh.exe` 或类似的 CLI 工具
   - 运行 `wsh --help` 查看可用命令

3. **查看配置文件**
   - 检查 `%APPDATA%\Wave\` 目录
   - 查看是否有配置文件

### 需要用户决策：
1. **如果没有 CLI/API**，是否接受半自动模式？
2. **是否愿意安装 AutoHotkey**（如果需要）？
3. **是否愿意尝试 pywinauto**（需要额外依赖）？

---

## 参考资料

- [Wave Terminal GitHub](https://github.com/wavetermdev/waveterm)
- [Wave Terminal Documentation](https://docs.waveterm.dev/)
- [Wave Terminal Workspaces](https://docs.waveterm.dev/workspaces)
- [Wave Shell (wsh)](https://docs.waveterm.dev/wsh)

---

**调研状态**: 🟡 部分完成，需要进一步调研 CLI/API
**推荐方案**: 优先调研 CLI/API，备选半自动模式
