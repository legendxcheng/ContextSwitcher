# ContextSwitcher PySide6 迁移计划

## 项目概述

将 ContextSwitcher 从 FreeSimpleGUI 迁移到 PySide6 (Qt for Python)，解决 Windows 11 兼容性问题，提升界面现代化程度和长期维护性。

---

## 当前 GUI 组件清单

| 组件 | 文件 | 功能描述 | 优先级 |
|------|------|----------|--------|
| 主窗口 | `main_window.py` | 主界面、任务列表、操作按钮 | P0 |
| 任务切换器 | `task_switcher_dialog.py` | 热键触发的快速切换弹窗 | P0 |
| 任务编辑对话框 | `task_dialog/` | 添加/编辑任务的对话框 | P0 |
| 设置对话框 | `settings_dialog.py` | 应用设置界面 | P1 |
| 系统托盘 | `utils/tray_manager.py` | 系统托盘图标和菜单 | P0 |
| 窗口选择器 | `window_selector.py` | 选择要绑定的窗口 | P0 |
| 欢迎对话框 | `welcome_dialog.py` | 首次运行引导 | P2 |
| 重新绑定对话框 | `rebind_dialog.py` | 窗口失效后的重新绑定 | P1 |

---

## 新项目结构设计

```
gui/
├── __init__.py
├── qt_main_window.py          # [新建] PySide6 主窗口
├── qt_task_switcher.py        # [新建] PySide6 任务切换器
├── qt_task_dialog.py          # [新建] PySide6 任务编辑对话框
├── qt_settings_dialog.py      # [新建] PySide6 设置对话框
├── qt_window_selector.py      # [新建] PySide6 窗口选择器
├── qt_system_tray.py          # [新建] PySide6 系统托盘
│
├── widgets/                    # [新建] 自定义组件
│   ├── __init__.py
│   ├── frameless_window.py    # 无边框窗口基类
│   ├── custom_title_bar.py    # 自定义标题栏
│   ├── task_table.py          # 任务列表表格
│   └── modern_button.py       # 现代化按钮
│
├── styles/                     # [新建] 样式表
│   ├── __init__.py
│   ├── dark_theme.qss         # 暗色主题
│   └── fluent_style.qss       # Fluent Design 风格
│
├── [保留] 原有文件（向后兼容）
│   ├── event_controller.py    # 事件控制器（保留业务逻辑）
│   ├── action_dispatcher.py   # 动作调度器
│   └── interfaces/            # 接口定义
```

---

## 分阶段实施计划

### 阶段 0：准备工作（1-2天）

**目标**：建立开发环境，验证 PySide6 可行性

#### 任务清单
- [ ] **0.1** 安装 PySide6 及相关依赖
  ```bash
  pip install PySide6 PySide6-Addons
  # 或使用 PySide6-Addons-Qt6（可选，包含额外 Qt 模块）
  ```
- [ ] **0.2** 创建测试项目结构
  - 创建 `gui/qt/` 目录
  - 创建 `gui/qt/widgets/` 目录
  - 创建 `gui/qt/styles/` 目录
- [ ] **0.3** 验证关键功能可行性
  - 创建无边框窗口原型
  - 测试系统托盘功能
  - 测试全局热键与 Qt 事件循环的兼容性
- [ ] **0.4** 确定无边框窗口方案
  - 评估 `PySideSix-Frameless-Window` 库
  - 或自行实现无边框窗口 + 自定义标题栏

**验收标准**：
- 能创建并显示一个无边框窗口
- 系统托盘图标和菜单正常工作
- pynput 全局热键能正常触发

---

### 阶段 1：核心框架搭建（3-5天）

**目标**：建立 PySide6 基础架构，实现主窗口

#### 任务清单

- [ ] **1.1** 创建无边框窗口基类
  - 文件：`gui/qt/widgets/frameless_window.py`
  - 功能：
    - `Qt.FramelessWindowHint` 窗口标志
    - 窗口拖拽支持
    - 窗口阴影效果
    - Windows 11 圆角效果
    - 动画过渡

- [ ] **1.2** 创建自定义标题栏
  - 文件：`gui/qt/widgets/custom_title_bar.py`
  - 功能：
    - 最小化/关闭按钮
    - 窗口拖拽区域
    - 应用图标和标题
    - 右键菜单

- [ ] **1.3** 创建主窗口框架
  - 文件：`gui/qt/qt_main_window.py`
  - 功能：
    - 继承无边框窗口基类
    - 设置窗口属性（keep_on_top, alpha_channel）
    - 连接 TaskManager
    - 实现主布局框架

- [ ] **1.4** 创建现代化主题样式
  - 文件：`gui/qt/styles/dark_theme.qss`
  - 功能：
    - Windows 11 风格配色
    - Fluent Design 效果
    - 支持亮色/暗色主题切换

- [ ] **1.5** 创建任务表格组件
  - 文件：`gui/qt/widgets/task_table.py`
  - 功能：
    - `QTableWidget` 封装
    - 自定义行高和列宽
    - 状态图标显示
    - 双击编辑事件

**验收标准**：
- 能显示一个无边框主窗口
- 窗口可拖拽移动
- 能显示任务列表（空列表或测试数据）
- 主题样式正确加载

---

### 阶段 2：主窗口功能迁移（5-7天）

**目标**：实现主窗口的完整功能

#### 任务清单

- [ ] **2.1** 实现任务列表显示
  - 数据绑定：TaskManager → QTableWidget
  - 定时刷新机制（2秒间隔）
  - 状态列图标显示
  - 时间列格式化

- [ ] **2.2** 实现搜索和筛选
  - 搜索框：`QComboBox` 历史记录
  - 状态筛选下拉框
  - 排序选项下拉框
  - 实时搜索过滤

- [ ] **2.3** 实现操作按钮
  - 添加任务按钮
  - 编辑任务按钮
  - 删除任务按钮
  - 番茄钟按钮
  - 统计按钮
  - 设置按钮

- [ ] **2.4** 实现底部状态栏
  - 今日专注时间显示
  - 每日目标进度
  - 番茄钟计时器
  - 快捷键提示

- [ ] **2.5** 实现事件处理
  - 迁移 `EventController` 业务逻辑
  - 连接按钮信号到槽
  - 键盘快捷键处理
  - 表格选择事件

- [ ] **2.6** 实现番茄钟功能
  - 计时器显示
  - 开始/暂停控制
  - 完成提示
  - 与 TimeTracker 集成

**验收标准**：
- 任务列表正确显示所有任务
- 搜索和筛选功能正常
- 所有按钮功能正常
- 番茄钟功能完整

---

### 阶段 3：对话框迁移（5-7天）

**目标**：实现所有对话框功能

#### 任务清单

- [ ] **3.1** 任务编辑对话框
  - 文件：`gui/qt/qt_task_dialog.py`
  - 功能：
    - 任务名称输入
    - 描述输入
    - 状态选择
    - 优先级选择
    - 窗口绑定（复用 WindowSelector）
    - 保存/取消按钮

- [ ] **3.2** 窗口选择器
  - 文件：`gui/qt/qt_window_selector.py`
  - 功能：
    - 窗口列表刷新
    - 多选支持
    - 实时预览
    - Explorer 路径显示

- [ ] **3.3** 设置对话框
  - 文件：`gui/qt/qt_settings_dialog.py`
  - 功能：
    - 热键配置
    - 窗口行为设置
    - 通知设置
    - 每日目标设置

- [ ] **3.4** 任务切换器
  - 文件：`gui/qt/qt_task_switcher.py`
  - 功能：
    - 大尺寸弹窗（800x700）
    - 键盘导航
    - 2秒自动超时
    - 数字键快速选择

- [ ] **3.5** 系统托盘
  - 文件：`gui/qt/qt_system_tray.py`
  - 功能：
    - `QSystemTrayIcon` 封装
    - 右键菜单（显示/隐藏/退出）
    - 双击显示主窗口
    - 托盘图标

**验收标准**：
- 所有对话框能正常打开和关闭
- 表单数据正确保存
- 系统托盘功能完整

---

### 阶段 4：集成与优化（3-5天）

**目标**：集成所有组件，优化用户体验

#### 任务清单

- [ ] **4.1** 主程序入口改造
  - 文件：`main.py`
  - 改造点：
    - QApplication 创建
    - 选择 Qt 或 FreeSimpleGUI（环境变量控制）
    - 事件循环替换

- [ ] **4.2** 窗口状态管理
  - 窗口位置保存/恢复
  - 最小化到托盘
  - 窗口显示/隐藏逻辑

- [ ] **4.3** 热键管理集成
  - pynput 与 Qt 事件循环兼容
  - 热键触发时显示任务切换器
  - 线程安全处理

- [ ] **4.4** 数据持久化
  - 配置文件兼容
  - 数据迁移脚本（如需要）

- [ ] **4.5** 性能优化
  - 减少刷新频率
  - 懒加载优化
  - 内存占用优化

**验收标准**：
- 应用能完整启动和运行
- 所有功能正常
- 性能无明显下降

---

### 阶段 5：测试与打包（2-3天）

**目标**：确保质量和可分发性

#### 任务清单

- [ ] **5.1** 功能测试
  - 手动测试所有功能
  - 边界条件测试
  - 多显示器测试

- [ ] **5.2** 兼容性测试
  - Windows 10 测试
  - Windows 11 测试
  - 不同 DPI 设置测试

- [ ] **5.3** 打包配置
  - PyInstaller 配置更新
  - 或使用 `pyside6-deploy`
  - 图标和元数据设置

- [ ] **5.4** 发布准备
  - 更新 README
  - 更新依赖说明
  - 创建迁移文档

**验收标准**：
- 所有测试通过
- 能生成独立可执行文件
- 文档完整

---

## 技术细节

### 无边框窗口实现

```python
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt

class FramelessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 无边框 + 置顶
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        # 透明度（可选）
        self.setWindowOpacity(0.95)
        # Windows 11 圆角
        self.setAttribute(Qt.WA_TranslucentBackground)
```

### 系统托盘实现

```python
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon

tray = QSystemTrayIcon()
tray.setIcon(QIcon("icon.ico"))
tray.setVisible(True)

menu = QMenu()
menu.addAction("显示", self.show)
menu.addAction("退出", self.exit)
tray.setContextMenu(menu)
```

### 与 pynput 兼容

```python
from pynput import keyboard
from PySide6.QtCore import QThread, Signal

class HotkeyThread(QThread):
    trigger = Signal()

    def run(self):
        def on_activate():
            self.trigger.emit()
        with keyboard.GlobalHotKeys({
            '<ctrl>+<alt>+<space>': on_activate
        }):
            self.hotkey_listener.join()

# 在主窗口中连接
hotkey_thread.trigger.connect(self.show_task_switcher)
```

---

## 依赖更新

### requirements.txt 变更

```diff
- FreeSimpleGUI>=5.2.0
+ PySide6>=6.6.0
- pystray>=0.19.5  # 移除，使用 Qt 内置托盘
```

### 新增依赖

```txt
PySide6>=6.6.0
PySide6-Addons>=6.6.0  # 可选，包含额外模块
```

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Qt 与 pynput 冲突 | 高 | 阶段 0 验证兼容性，备选方案：使用 Qt 的 QHotkey 或 keyboard 库 |
| 无边框窗口兼容问题 | 中 | 优先使用成熟库（PySideSix-Frameless-Window），备选方案：保留标题栏 |
| 打包体积增大 | 低 | 使用 `pyside6-deploy` 优化，排除未使用的 Qt 模块 |
| 学习曲线 | 中 | 参考现有项目，逐步迁移 |

---

## 时间估算

| 阶段 | 预估时间 | 累计时间 |
|------|----------|----------|
| 阶段 0：准备工作 | 1-2 天 | 2 天 |
| 阶段 1：核心框架 | 3-5 天 | 7 天 |
| 阶段 2：主窗口功能 | 5-7 天 | 14 天 |
| 阶段 3：对话框迁移 | 5-7 天 | 21 天 |
| 阶段 4：集成优化 | 3-5 天 | 26 天 |
| 阶段 5：测试打包 | 2-3 天 | 29 天 |

**总计：约 4-6 周**

---

## 向后兼容策略

### 并行运行期

在迁移期间，保留 FreeSimpleGUI 版本，通过环境变量选择：

```python
# main.py
import os

USE_QT = os.environ.get('CONTEXT_SWITCHER_USE_QT', 'false').lower() == 'true'

if USE_QT:
    from gui.qt.qt_main_window import QtMainWindow as MainWindow
else:
    from gui.main_window import MainWindow  # 原有版本
```

### 数据兼容

- 配置文件格式不变
- 数据文件格式不变
- 窗口位置数据共享

---

## 回滚方案

如果迁移遇到重大问题：

1. **代码回滚**：Git 分支管理，保留 FreeSimpleGUI 主分支
2. **配置回滚**：卸载 PySide6，重装 FreeSimpleGUI
3. **数据回滚**：数据格式完全兼容，无需处理

---

## 参考资料

- [PySide6 官方文档](https://doc.qt.io/qtforpython/)
- [PySide6 System Tray](https://www.pythonguis.com/tutorials/pyside6-system-tray-mac-menu-bar-applications/)
- [PySideSix-Frameless-Window](https://pypi.org/project/PySideSix-Frameless-Window-Fix/)
- [具有现代GUI风格的PySide6参考项目](https://www.mr-wu.cn/modern-gui-style-pyside6-pyqt6-reference-project/)

---

## 下一步

请审阅此计划，确认后我们将进入**执行模式**，从**阶段 0**开始实施。
