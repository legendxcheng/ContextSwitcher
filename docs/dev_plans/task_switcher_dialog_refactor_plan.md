# TaskSwitcherDialog 重构计划

## 一、现状分析

### 1.1 文件信息
- **文件**: `gui\task_switcher_dialog.py`
- **行数**: 730行
- **主要类**: `TaskSwitcherDialog`

### 1.2 当前职责分析
| 职责 | 方法数 | 代码行数范围 | 占比 |
|------|--------|-------------|------|
| 配置管理 | 2 | 40-82 | ~6% |
| 布局创建 | 4 | 272-407 | ~19% |
| 显示控制 | 3 | 89-162, 163-270 | ~25% |
| 事件处理 | 3 | 517-618 | ~15% |
| UI更新 | 2 | 441-497 | ~8% |
| 定时器管理 | 3 | 498-515 | ~3% |
| 任务执行 | 3 | 620-686, 687-696 | ~10% |
| 资源清理 | 1 | 697-730 | ~5% |

### 1.3 代码复杂度问题
1. **单一类承担过多职责**：违反单一职责原则
2. **事件循环过长**：`_run_event_loop` 方法100+行，包含多个事件判断
3. **布局创建逻辑复杂**：多个 `_create_*` 方法散落在类中
4. **配置和UI逻辑耦合**：字体、颜色配置与业务逻辑混在一起

---

## 二、重构目标

1. 将730行拆分为多个模块，每个模块不超过300行
2. 职责清晰分离，便于维护和测试
3. 保持原有功能和对外接口不变
4. 提高代码可读性和可复用性

---

## 三、重构方案

### 3.1 新模块结构

```
gui/
├── task_switcher_dialog.py          # 主对话框类 (精简后 ~150行)
├── switcher/
│   ├── __init__.py                  # 包初始化
│   ├── switcher_config.py           # 配置管理 (~100行)
│   ├── switcher_layout.py           # 布局创建 (~200行)
│   ├── switcher_event_handler.py    # 事件处理 (~200行)
│   └── switcher_ui_updater.py       # UI更新 (~150行)
```

### 3.2 模块职责划分

#### 3.2.1 `switcher_config.py` - 配置管理
**职责**：
- 加载和管���任务切换器配置
- 字体配置管理
- 颜色配置管理
- 窗口尺寸计算

**包含内容**：
```python
class SwitcherConfig:
    """任务切换器配置管理"""
    - load_config()
    - get_window_size(task_count)
    - get_fonts()
    - get_colors()
    - get_auto_close_delay()
```

**迁移方法**：
- `__init__` 中的配置加载部分
- `_calculate_window_size()`
- 字体配置 `self.fonts`
- 颜色配置 `self.colors`

---

#### 3.2.2 `switcher_layout.py` - 布局创建
**职责**：
- 创建窗口主布局
- 创建任务行
- 创建空任务行
- 状态颜色计算
- 时间显示格式化

**包含内容**：
```python
class SwitcherLayout:
    """任务切换器布局创建"""
    - create_layout(tasks, selected_index, config)
    - create_task_row(index, task, selected_index, config)
    - create_empty_task_row(index, config)
    - get_status_color(status, colors)
    - get_time_display(timestamp)
```

**迁移方法**：
- `_create_layout()`
- `_create_task_row()`
- `_create_empty_task_row()`
- `_get_status_color()`
- `_get_time_display()`

---

#### 3.2.3 `switcher_event_handler.py` - 事件处理
**职责**：
- 事件循环管理
- 键盘事件处理
- 鼠标滚轮事件处理
- 定时器管理

**包含内容**：
```python
class SwitcherEventHandler:
    """任务切换器事件处理"""
    - run_event_loop(window, tasks, auto_close_delay)
    - handle_keyboard_event(event, tasks)
    - handle_mouse_event(event)
    - handle_timeout()
```

**迁移方法**：
- `_run_event_loop()` 的核心逻辑
- 键盘事件判断（上、下、数字键、回车、ESC）
- 鼠标滚轮事件处理

---

#### 3.2.4 `switcher_ui_updater.py` - UI更新
**职责**：
- 更新选中状态显示
- 更新倒计时显示
- 选中位置移动

**包含内容**：
```python
class SwitcherUIUpdater:
    """任务切换器UI更新"""
    - update_selection_display(window, tasks, selected_index)
    - update_countdown_display(window, remaining_time, colors)
    - move_selection(direction, task_count, selected_index)
```

**迁移方法**：
- `_update_selection_display()`
- `_update_countdown_display()`
- `_move_selection()`

---

#### 3.2.5 `task_switcher_dialog.py` - 主对话框（精简后）
**职责**：
- 协调各模块完成显示和交互
- 管理窗口生命周期
- 处理回调
- 任务切换执行

**保留内容**：
- `__init__()` - 初始化（简化版）
- `show()` - 显示对话框（协调方法）
- `_show_no_tasks_message()` - 无任务提示
- `_execute_task_switch()` - 执行任务切换
- `_start_auto_close_timer()` - 定时器启动
- `_reset_auto_close_timer()` - 定时器重置
- `_cleanup()` - 资源清理
- `_force_close()` - 强制关闭

---

## 四、实施步骤

### 步骤1：创建 `switcher/` 包结构
- [ ] 创建 `gui/switcher/` 目录
- [ ] 创建 `__init__.py` 文件

### 步骤2：实现 `switcher_config.py`
- [ ] 创建 `SwitcherConfig` 类
- [ ] 迁移配置加载逻辑
- [ ] 迁移 `_calculate_window_size()`
- [ ] 迁移字体和颜色配置
- [ ] 编写测试验证配置加载

### 步骤3：实现 `switcher_layout.py`
- [ ] 创建 `SwitcherLayout` 类
- [ ] 迁移 `_create_layout()`
- [ ] 迁移 `_create_task_row()`
- [ ] 迁移 `_create_empty_task_row()`
- [ ] 迁移 `_get_status_color()`
- [ ] 迁移 `_get_time_display()`
- [ ] 修改主类使用新布局模块

### 步骤4：实现 `switcher_ui_updater.py`
- [ ] 创建 `SwitcherUIUpdater` 类
- [ ] 迁移 `_update_selection_display()`
- [ ] 迁移 `_update_countdown_display()`
- [ ] 迁移 `_move_selection()`
- [ ] 修改主类使用新UI更新模块

### 步骤5：实现 `switcher_event_handler.py`
- [ ] 创建 `SwitcherEventHandler` 类
- [ ] 迁移 `_run_event_loop()` 核心逻辑
- [ ] 迁移键盘事件处理
- [ ] 迁移鼠标事件处理
- [ ] 修改主类使用新事件处理模块

### 步骤6：精简主类 `task_switcher_dialog.py`
- [ ] 删除已迁移的方法
- [ ] 更新导入语句
- [ ] 更新方法调用
- [ ] 确保对外接口不变

### 步骤7：测试验证
- [ ] 运行 `verify_simple.py` 验证基本功能
- [ ] 测试任务切换对话框显示
- [ ] 测试键盘导航（上下箭头）
- [ ] 测试数字键快速选择
- [ ] 测试倒计时功能
- [ ] 测试无任务提示

---

## 五、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 循环依赖 | 高 | 明确模块依赖关系，配置→布局→UI更新→事件处理→主类 |
| 事件处理逻辑复杂 | 中 | 逐步迁移，保持原有逻辑结构 |
| 破坏现有功能 | 中 | 充分测试，保持对外接口不变 |
| 性能下降 | 低 | 模块化不应影响性能 |

---

## 六、重构后预期效果

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 主文件行数 | 730行 | ~150行 |
| 文件数量 | 1个 | 5个 |
| 最大文件行数 | 730行 | ~250行 |
| 单一职责符合度 | 低 | 高 |
| 可测试性 | 低 | 中 |

---

## 七、后续优化建议

1. 为事件处理器添加单元测试
2. 考虑将键盘事件映射配置化
3. 添加更多UI主题支持
4. 考虑异步加载任务列表
