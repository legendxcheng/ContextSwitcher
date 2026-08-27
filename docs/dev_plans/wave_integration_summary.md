# Wave.exe 集成调研总结

## 调研结论

✅ **高度可行** - 向 Wave.exe 发送快捷键组合在技术上完全可行

---

## 核心发现

### 1. 现有代码库已具备基础能力

- ✅ 已有窗口管理系统 (`core/window_manager/`)
- ✅ 已有按键发送功能 (`keybd_event`, `SendKeys`)
- ✅ 已有应用辅助类扩展机制 (`core/app_helpers/`)
- ✅ 已依赖必要的库 (`pywin32`, `pynput`)

### 2. 三种实现方案

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **A. PostMessage** | 不切换焦点，用户体验好 | 某些应用可能不响应 | ⭐⭐⭐⭐ |
| **B. 激活+全局按键** | 实现简单，兼容性好 | 会切换焦点 | ⭐⭐⭐⭐⭐ |
| **C. WaveHelper 类** | 集成度高，可扩展 | 实现复杂 | ⭐⭐⭐ |

### 3. 推荐实施路径

**阶段 1: 快速验证（1-2天）**
```
1. 运行测试脚本验证可行性
   python test_wave_hotkey.py post_message 1
   python test_wave_hotkey.py activate_first 2

2. 确定最适合 Wave.exe 的方案
```

**阶段 2: 基础集成（3-5天）**
```
1. 创建 core/wave_controller.py 模块
2. 实现 send_hotkey_to_wave(hwnd, index) 函数
3. 在任务切换逻辑中调用
4. 添加配置选项
```

**阶段 3: 完善功能（可选）**
```
1. 创建 WaveHelper 辅助类
2. 实现 workspace 上下文管理
3. 添加自动检测和智能绑定
```

---

## 关键技术点

### PostMessage 方案（推荐优先尝试）

```python
import win32api
import win32con

def send_ctrl_alt_number(hwnd, number):
    """向窗口发送 Ctrl+Alt+数字"""
    VK_CONTROL = 0x11
    VK_MENU = 0x12  # Alt
    key_code = 0x30 + number  # 0x31='1', 0x32='2', ...

    # 按下修饰键
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_CONTROL, 0)
    win32api.PostMessage(hwnd, win32con.WM_SYSKEYDOWN, VK_MENU, 0)

    # 按下并释放数字键
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key_code, 0)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, key_code, 0)

    # 释放修饰键
    win32api.PostMessage(hwnd, win32con.WM_SYSKEYUP, VK_MENU, 0)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, VK_CONTROL, 0)
```

### 激活窗口方案（备选）

```python
from pynput.keyboard import Controller, Key

def send_hotkey_after_activation(hwnd, number):
    """激活窗口后发送快捷键"""
    # 1. 激活窗口
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.1)

    # 2. 发送快捷键
    keyboard = Controller()
    with keyboard.pressed(Key.ctrl):
        with keyboard.pressed(Key.alt):
            keyboard.press(str(number))
            keyboard.release(str(number))
```

---

## 潜在问题与解决方案

### 问题 1: 热键冲突

**问题**: Wave.exe 和 ContextSwitcher 都使用 Ctrl+Alt+数字

**解决方案**:
- 修改 ContextSwitcher 的任务切换器热键（如改为 Ctrl+Alt+Space）
- 在配置中添加热键冲突检测和警告

### 问题 2: Wave.exe 不响应 PostMessage

**问题**: 某些应用可能不响应 PostMessage 发送的按键

**解决方案**:
- 先测试 PostMessage 方案
- 如果不响应，回退到激活窗口方案
- 在配置中允许用户选择方案

### 问题 3: 多个 Wave.exe 实例

**问题**: 用户可能运行多个 Wave.exe 实例

**解决方案**:
- 使用 WindowFinder 根据窗口标题精确匹配
- 允许用户在任务绑定时选择特定的 Wave.exe 窗口
- 在任务数据中保存窗口标识信息

---

## 下一步行动

### 立即可做

1. ✅ **运行测试脚本**
   ```bash
   python test_wave_hotkey.py post_message 1
   python test_wave_hotkey.py activate_first 2
   ```

2. ✅ **验证 Wave.exe 响应**
   - 观察 Wave.exe 是否切换 workspace
   - 记录哪种方案有效

3. ✅ **检查热键冲突**
   - 确认 ContextSwitcher 当前的热键配置
   - 规划热键调整方案

### 需要用户决策

1. **热键配置**
   - 是否修改 ContextSwitcher 的热键以避免冲突？
   - 建议: 任务切换器改为 Ctrl+Alt+Space

2. **实现优先级**
   - 是否需要立即实现？
   - 是否需要完整的 WaveHelper 类？

3. **用户体验**
   - 是否接受激活窗口方案（会切换焦点）？
   - 还是必须使用 PostMessage 方案（不切换焦点）？

---

## 相关文件

### 调研文档
- `docs/dev_plans/wave_integration_research.md` - 完整调研报告

### 测试脚本
- `test_wave_hotkey.py` - 快捷键发送测试脚本

### 相关代码
- `core/window_manager/window_activator.py:106-111` - 现有按键发送实现
- `core/app_helpers/base_app_helper.py` - 应用辅助类基类
- `core/app_helpers/terminal_helper.py` - Terminal 辅助类示例
- `core/hotkey_manager.py` - 热键管理器

---

## 技术参考

### Windows API
- `win32api.PostMessage()` - 向窗口发送消息
- `win32gui.SetForegroundWindow()` - 激活窗口
- `win32gui.EnumWindows()` - 枚举窗口

### 虚拟键码
```python
VK_CONTROL = 0x11  # Ctrl
VK_MENU = 0x12     # Alt
VK_SHIFT = 0x10    # Shift
VK_1 = 0x31        # 数字 1
VK_2 = 0x32        # 数字 2
# ... VK_9 = 0x39
```

### 消息类型
```python
WM_KEYDOWN = 0x0100      # 按键按下
WM_KEYUP = 0x0101        # 按键释放
WM_SYSKEYDOWN = 0x0104   # 系统键按下（Alt）
WM_SYSKEYUP = 0x0105     # 系统键释放（Alt）
```

---

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 热键冲突 | 中 | 修改配置，添加冲突检测 |
| Wave.exe 不响应 PostMessage | 低 | 回退到激活窗口方案 |
| 实现复杂度 | 低 | 使用现有架构，渐进式开发 |
| 用户体验影响 | 低 | 提供配置选项，允许用户选择 |

**总体风险**: 🟢 低

---

## 预期收益

- ✅ 提升 ContextSwitcher 的实用性
- ✅ 为未来支持更多应用铺路
- ✅ 展示应用集成的典型案例
- ✅ 增强用户工作流程的连贯性

---

**调研完成日期**: 2026-02-01
**调研人员**: Claude Code
**状态**: ✅ 调研完成，等待用户决策
