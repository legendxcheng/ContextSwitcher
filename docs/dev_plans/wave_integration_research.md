# Wave.exe 集成调研报告

## 调研目标

调研是否可以实现向 Wave.exe 应用发送快捷键组合（Ctrl + Alt + index），以便在 ContextSwitcher 中切换 Wave.exe 的 workspace。

## 调研日期

2026-02-01

---

## 一、Wave.exe 应用背景

- **应用名称**: Wave.exe
- **功能**: 管理一系列 Shell 窗口的工具
- **快捷键**: Ctrl + Alt + index（用于切换 workspace）
- **集成需求**: 在 ContextSwitcher 切换任务时，自动向 Wave.exe 发送对应的快捷键

---

## 二、现有代码库功能分析

### 2.1 按键发送功能

**位置**: `core/window_manager/window_activator.py:106-111`

**现有实现**:
```python
# 方法1: 使用 COM 对象发送按键
import win32com.client
shell = win32com.client.Dispatch("WScript.Shell")
shell.SendKeys('%')  # 发送ALT键

# 方法2: 使用 keybd_event 发送按键
win32api.keybd_event(0x12, 0, 0, 0)  # ALT down
win32api.keybd_event(0x12, 0, win32con.KEYEVENTF_KEYUP, 0)  # ALT up
```

**特点**:
- 仅用于窗口激活过程中发送 ALT 键
- 发送的是全局按键，不针对特定窗口
- 没有实现复杂的快捷键组合发送

### 2.2 窗口管理系统

**架构**: 模块化设计，位于 `core/window_manager/`

**核心模块**:
- **WindowActivator**: 多策略窗口激活
- **WindowEnumerator**: 窗口枚举和信息获取
- **SwitchController**: 批量窗口切换控制
- **WindowFinder**: 窗口查找功能

**可用的 Windows API**:
```python
win32gui.SetForegroundWindow(hwnd)  # 设置前台窗口
win32gui.ShowWindow(hwnd, ...)      # 控制窗口显示
win32gui.SetWindowPos(hwnd, ...)    # 设置窗口位置
win32gui.SetFocus(hwnd)             # 设置焦点
```

### 2.3 应用辅助类扩展机制

**位置**: `core/app_helpers/`

**架构**:
- **BaseAppHelper**: 抽象基类，定义接口规范
- **TerminalHelper**: Windows Terminal/PowerShell/CMD 支持
- **VSCodeHelper**: VS Code 支持
- **AppHelperRegistry**: 辅助类注册表

**接口方法**:
```python
class BaseAppHelper(ABC):
    @property
    def app_type(self) -> str: ...

    @property
    def process_names(self) -> List[str]: ...

    def is_supported_window(self, hwnd, process_name) -> bool: ...
    def extract_context(self, hwnd, title) -> Dict: ...
    def restore_window(self, context, target_rect) -> Optional[int]: ...
```

**扩展模式**: 可以创建新的 Helper 类来支持特定应用

### 2.4 依赖库

**已安装**:
- `pywin32>=306` - Windows API 集成
- `pynput>=1.7.6` - 全局热键支持
- `FreeSimpleGUI>=5.2.0` - GUI 框架

---

## 三、向特定窗口发送快捷键的技术方案

### 方案 A: 使用 PostMessage/SendMessage（推荐）

**原理**: 直接向目标窗口句柄发送 Windows 消息

**优点**:
- 不需要窗口处于前台
- 不会干扰用户当前操作
- 更精确的控制

**缺点**:
- 某些应用可能不响应这些消息
- 需要正确处理修饰键顺序
- 实现相对复杂

**实现示例**:
```python
import win32api
import win32con

def send_hotkey_to_window(hwnd, ctrl=False, alt=False, key_code=0x31):
    """
    向指定窗口发送快捷键

    Args:
        hwnd: 目标窗口句柄
        ctrl: 是否按下 Ctrl
        alt: 是否按下 Alt
        key_code: 按键虚拟码（0x31='1', 0x32='2', ...）
    """
    # 1. 发送修饰键按下
    if ctrl:
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
    if alt:
        win32api.PostMessage(hwnd, win32con.WM_SYSKEYDOWN, win32con.VK_MENU, 0)

    # 2. 发送目标键按下
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key_code, 0)

    # 3. 发送目标键释放
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, key_code, 0)

    # 4. 发送修饰键释放
    if alt:
        win32api.PostMessage(hwnd, win32con.WM_SYSKEYUP, win32con.VK_MENU, 0)
    if ctrl:
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)
```

**关键常量**:
```python
# 消息类型
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104  # 用于 Alt 键
WM_SYSKEYUP = 0x0105

# 虚拟键码
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt 键
VK_SHIFT = 0x10

# 数字键
VK_1 = 0x31
VK_2 = 0x32
# ... VK_9 = 0x39
```

### 方案 B: 激活窗口后发送全局按键

**原理**: 先激活目标窗口，再发送全局按键

**优点**:
- 实现简单，使用现有的 WindowActivator
- 兼容性好，几乎所有应用都能响应
- 可以使用 pynput.keyboard.Controller

**缺点**:
- 会切换用户焦点
- 可能干扰用户当前操作
- 需要等待窗口激活完成

**实现示例**:
```python
from pynput.keyboard import Controller, Key

def send_hotkey_after_activation(hwnd, index):
    """
    激活窗口后发送快捷键

    Args:
        hwnd: 目标窗口句柄
        index: 数字索引 (1-9)
    """
    # 1. 激活窗口
    window_activator = WindowActivator()
    if not window_activator.activate_window(hwnd):
        return False

    # 2. 等待窗口激活
    time.sleep(0.1)

    # 3. 发送快捷键
    keyboard = Controller()
    with keyboard.pressed(Key.ctrl):
        with keyboard.pressed(Key.alt):
            keyboard.press(str(index))
            keyboard.release(str(index))

    return True
```

### 方案 C: 创建 WaveHelper 应用辅助类

**原理**: 继承 BaseAppHelper，实现 Wave.exe 的专用辅助类

**优点**:
- 集成到现有的应用辅助系统
- 可以提取和恢复 workspace 上下文
- 符合项目架构设计

**缺点**:
- 需要了解 Wave.exe 的内部机制
- 可能需要额外的 API 或命令行接口
- 实现工作量较大

**实现框架**:
```python
class WaveHelper(BaseAppHelper):
    @property
    def app_type(self) -> str:
        return 'wave'

    @property
    def process_names(self) -> List[str]:
        return ['wave.exe']

    def is_supported_window(self, hwnd, process_name) -> bool:
        return process_name.lower() == 'wave.exe'

    def extract_context(self, hwnd, title) -> Dict:
        """提取当前 workspace 信息"""
        # 需要研究如何获取当前 workspace
        return {
            'app_type': 'wave',
            'workspace_index': self._get_current_workspace(hwnd),
        }

    def restore_window(self, context, target_rect) -> Optional[int]:
        """恢复到指定 workspace"""
        workspace_index = context.get('workspace_index')
        if workspace_index:
            self._switch_workspace(hwnd, workspace_index)
        return hwnd

    def _switch_workspace(self, hwnd, index):
        """发送 Ctrl+Alt+数字 切换 workspace"""
        # 使用方案 A 或 B 实现
        pass
```

---

## 四、技术可行性评估

### 4.1 方案对比

| 特性 | 方案 A (PostMessage) | 方案 B (激活+全局按键) | 方案 C (WaveHelper) |
|------|---------------------|----------------------|-------------------|
| 实现难度 | 中等 | 简单 | 较高 |
| 用户体验 | 优秀（无焦点切换） | 一般（会切换焦点） | 优秀 |
| 兼容性 | 取决于应用 | 很好 | 取决于 Wave.exe API |
| 维护成本 | 低 | 低 | 中等 |
| 扩展性 | 中等 | 低 | 高 |

### 4.2 推荐方案

**短期方案（快速实现）**: 方案 B - 激活窗口后发送全局按键
- 实现简单，可以快速验证功能
- 使用现有的 WindowActivator 和 pynput 库
- 适合作为 MVP（最小可行产品）

**长期方案（最佳体验）**: 方案 A + 方案 C 结合
- 创建 WaveHelper 辅助类
- 使用 PostMessage 发送快捷键（无焦点切换）
- 集成到应用辅助系统，支持 workspace 上下文管理

### 4.3 潜在问题

1. **热键冲突**:
   - Wave.exe 使用 Ctrl+Alt+数字
   - ContextSwitcher 也使用 Ctrl+Alt+数字（任务切换器）
   - **解决方案**: 修改 ContextSwitcher 的热键配置，避免冲突

2. **Wave.exe 消息响应**:
   - 需要测试 Wave.exe 是否响应 PostMessage 发送的按键
   - 某些应用可能只响应真实的键盘输入
   - **解决方案**: 如果不响应，回退到方案 B

3. **窗口识别**:
   - 需要准确识别 Wave.exe 的窗口句柄
   - 可能有多个 Wave.exe 实例
   - **解决方案**: 使用 WindowFinder 根据进程名和窗口标题查找

---

## 五、实现建议

### 5.1 开发步骤

**阶段 1: 基础功能验证**
1. 创建测试脚本，验证向 Wave.exe 发送按键的可行性
2. 测试方案 A (PostMessage) 和方案 B (激活+全局按键)
3. 确定最适合 Wave.exe 的方案

**阶段 2: 集成到 ContextSwitcher**
1. 在 `core/` 下创建 `wave_controller.py` 模块
2. 实现 `send_hotkey_to_wave(hwnd, index)` 函数
3. 在任务切换逻辑中调用该函数

**阶段 3: 创建 WaveHelper（可选）**
1. 在 `core/app_helpers/` 下创建 `wave_helper.py`
2. 实现 workspace 上下文提取和恢复
3. 注册到 AppHelperRegistry

### 5.2 测试计划

1. **单元测试**:
   - 测试按键发送函数
   - 测试窗口查找功能
   - 测试热键冲突检测

2. **集成测试**:
   - 测试与 Wave.exe 的实际交互
   - 测试多个 Wave.exe 实例的情况
   - 测试热键冲突场景

3. **用户测试**:
   - 验证用户体验（焦点切换、响应速度）
   - 收集反馈并优化

### 5.3 配置选项

建议在 `utils/config.py` 中添加配置项:

```python
WAVE_INTEGRATION = {
    'enabled': True,
    'method': 'post_message',  # 'post_message' 或 'activate_first'
    'delay_ms': 50,  # 按键间隔
    'auto_detect': True,  # 自动检测 Wave.exe 窗口
}
```

---

## 六、参考资料

### 6.1 Windows API 文档
- [PostMessage function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessage)
- [SendMessage function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessage)
- [Virtual-Key Codes](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)
- [Keyboard Input](https://learn.microsoft.com/en-us/windows/win32/inputdev/keyboard-input)

### 6.2 相关讨论
- [Send keys to a inactive window in Python](https://stackoverflow.com/questions/21917965/send-keys-to-a-inactive-window-in-python)
- [How to send key strokes to a window without activating it](https://stackoverflow.com/questions/1220820/how-do-i-send-key-strokes-to-a-window-without-having-to-activate-it-using-window)
- [Python pywin32 PostMessage SendMessage](https://stackoverflow.com/questions/73593350/unable-to-send-keys-to-inactive-window-using-win32api-postmessage)

### 6.3 项目内部文档
- `docs/AUTO_SAVE_FEATURE.md` - 自动保存功能文档
- `CLAUDE.md` - 项目架构说明
- `core/app_helpers/base_app_helper.py` - 应用辅助类接口

---

## 七、结论

**可行性**: ✅ 高度可行

向 Wave.exe 发送快捷键组合在技术上完全可行，有多种实现方案可选。推荐采用**渐进式开发策略**:

1. **第一步**: 使用方案 B（激活+全局按键）快速实现基础功能
2. **第二步**: 测试 Wave.exe 对 PostMessage 的响应，如果支持则升级到方案 A
3. **第三步**: 根据需求决定是否实现完整的 WaveHelper 辅助类

**风险评估**: 低
- 主要风险是热键冲突，可通过配置解决
- Wave.exe 可能不响应 PostMessage，但可回退到方案 B
- 实现难度适中，不涉及复杂的系统级操作

**建议优先级**: 高
- 该功能可以显著提升 ContextSwitcher 的实用性
- 与项目现有架构兼容性好
- 可以作为应用集成的典型案例，为未来支持更多应用铺路

---

## 附录: 虚拟键码参考

```python
# 修饰键
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt

# 数字键（主键盘）
VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_5 = 0x35
VK_6 = 0x36
VK_7 = 0x37
VK_8 = 0x38
VK_9 = 0x39

# 数字键（小键盘）
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
# ... VK_NUMPAD9 = 0x69

# 功能键
VK_F1 = 0x70
# ... VK_F12 = 0x7B
```
