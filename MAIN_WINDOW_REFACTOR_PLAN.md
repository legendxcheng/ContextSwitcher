# MainWindow 重构计划

## 1. 现状分析

### 当前MainWindow类职责过载问题：

**核心职责混杂 (793行代码)**：
- GUI布局创建与管理 (方法: `_create_layout`, `create_window`)
- 事件循环处理 (方法: `run`, 76行代码)
- 表格数据渲染 (方法: `_get_table_data`, `_get_row_colors`, 共92行)
- 窗口状态管理 (拖拽检测、位置保存)
- Toast通知管理 (初始化、回调处理)
- 热键事件处理 (跨线程通信)
- 业务逻辑处理 (任务CRUD操作)

### 依赖关系复杂：
```
MainWindow 直接依赖:
├── TaskManager (业务核心)
├── ModernUIConfig (UI配置)  
├── ToastManager (通知系统)
├── SmartRebindManager (智能重绑)
├── TaskStatusManager (状态管理)
├── Config (配置管理)
└── Multiple Dialog classes (对话框)
```

## 2. 重构目标

### 设计原则：
1. **单一职责原则** - 每个类只负责一个明确的功能域
2. **依赖倒置原则** - 通过接口解耦，便于测试和扩展
3. **组合优于继承** - 使用组合模式组织功能组件
4. **渐进式重构** - 确保每步重构后代码仍可运行

### 性能目标：
- 主窗口初始化时间 < 500ms
- 事件响应时间 < 50ms  
- 内存占用降低 20%

## 3. 新架构设计

### 3.1 核心架构

```
MainWindow (协调器/容器, ~200行)
├── UILayoutManager (布局管理, ~150行)
├── EventController (事件分发, ~200行)  
├── TableDataProvider (数据提供, ~120行)
├── WindowStateManager (窗口状态, ~100行)
├── NotificationController (通知控制, ~80行)
└── ActionDispatcher (业务动作, ~150行)
```

### 3.2 接口定义

```python
# 核心接口
class IEventHandler:
    def handle_event(self, event: str, values: dict) -> bool

class IDataProvider:
    def get_table_data(self) -> List[List[str]]
    def get_row_colors(self) -> List[tuple]

class IWindowManager:
    def save_position(self) -> None
    def restore_position(self) -> None
    def detect_drag(self) -> bool

class INotificationHandler:
    def handle_toast_click(self, task_id: str) -> None
    def check_idle_tasks(self) -> None
```

### 3.3 组件职责分工

| 组件 | 主要职责 | 代码量估计 |
|------|----------|------------|
| **MainWindow** | 组件协调、生命周期管理 | ~200行 |
| **UILayoutManager** | 布局创建、UI组件管理 | ~150行 |  
| **EventController** | 事件分发、业务动作路由 | ~200行 |
| **TableDataProvider** | 表格数据转换、颜色计算 | ~120行 |
| **WindowStateManager** | 窗口位置、拖拽检测 | ~100行 |
| **NotificationController** | Toast管理、空闲检测 | ~80行 |
| **ActionDispatcher** | 任务CRUD操作调度 | ~150行 |

## 4. 分步重构策略

### Phase 1: 数据层提取 (风险: 低)
**目标**: 分离表格数据逻辑
**步骤**:
1. 创建 `TableDataProvider` 类
2. 迁移 `_get_table_data()` 和 `_get_row_colors()` 方法
3. 在MainWindow中集成新组件
4. 测试数据显示功能

**验证标准**: 表格显示正常，颜色渲染正确

### Phase 2: 事件处理分离 (风险: 中)
**目标**: 提取事件处理逻辑
**步骤**:
1. 创建 `EventController` 类和相关接口
2. 迁移所有 `_handle_*` 方法
3. 实现事件路由机制
4. 重构主事件循环

**验证标准**: 所有按钮和交互功能正常

### Phase 3: 窗口状态管理 (风险: 中)
**目标**: 独立窗口状态逻辑
**步骤**:
1. 创建 `WindowStateManager` 类
2. 迁移拖拽检测和位置保存逻辑
3. 集成到主窗口生命周期

**验证标准**: 窗口拖拽和位置记忆功能正常

### Phase 4: 通知系统重构 (风险: 低)
**目标**: 封装通知相关功能
**步骤**:
1. 创建 `NotificationController` 类
2. 迁移Toast相关逻辑
3. 优化空闲任务检测

**验证标准**: Toast通知和空闲提醒功能正常

### Phase 5: 布局管理分离 (风险: 低)
**目标**: 提取UI布局逻辑
**步骤**:
1. 创建 `UILayoutManager` 类
2. 迁移 `_create_layout()` 方法
3. 优化布局代码结构

**验证标准**: UI界面显示和布局正常

### Phase 6: 业务动作分离 (风险: 中)
**目标**: 分离业务逻辑调用
**步骤**:
1. 创建 `ActionDispatcher` 类
2. 封装任务管理操作
3. 实现统一的业务动作接口

**验证标准**: 任务增删改查功能正常

## 5. 实施细节

### 5.1 关键技术决策

**依赖注入策略**:
```python
class MainWindow:
    def __init__(self, task_manager: TaskManager, 
                 data_provider: IDataProvider = None,
                 event_controller: IEventHandler = None):
        # 支持依赖注入，便于测试
        self.data_provider = data_provider or TableDataProvider(task_manager)
        self.event_controller = event_controller or EventController(task_manager)
```

**事件通信机制**:
- 使用观察者模式处理组件间通信
- 避免循环依赖
- 支持异步事件处理

**错误处理策略**:
- 每个组件独立的异常处理
- 统一的错误日志记录
- 失败时的优雅降级

### 5.2 测试策略

**单元测试覆盖**:
- 每个新组件编写对应测试
- Mock外部依赖进行隔离测试
- 重构前后功能一致性验证

**集成测试**:
- 主要用户场景端到端测试
- 性能基准测试
- 内存泄漏检测

### 5.3 风险控制

**回滚机制**:
- 每个Phase完成后创建Git标签
- 保留原有代码作为备份分支
- 问题发现时快速回滚到稳定版本

**验收标准**:
- 所有现有功能保持不变
- 启动时间不增加
- 内存使用不增加超过10%
- 无新增的异常或错误

## 6. 预期收益

### 代码质量提升:
- **可维护性**: 平均类大小从793行降至150行
- **可测试性**: 组件独立，便于单元测试
- **可扩展性**: 通过接口支持新功能扩展

### 开发效率提升:
- **并行开发**: 不同组件可独立开发
- **错误定位**: 职责明确，问题快速定位  
- **功能迭代**: 单个功能修改影响范围小

### 系统性能优化:
- **启动速度**: 延迟加载非关键组件
- **内存占用**: 按需创建和销毁组件
- **响应时间**: 事件处理流程优化

## 7. 时间估算

| Phase | 预估工时 | 风险等级 | 验收周期 |
|-------|----------|----------|----------|
| Phase 1 | 4小时 | 低 | 1天 |
| Phase 2 | 8小时 | 中 | 2天 |  
| Phase 3 | 6小时 | 中 | 1天 |
| Phase 4 | 4小时 | 低 | 1天 |
| Phase 5 | 3小时 | 低 | 1天 |
| Phase 6 | 6小时 | 中 | 2天 |
| **总计** | **31小时** | - | **8天** |

**建议执行周期**: 2-3周，保证充分测试时间

## 8. 下一步行动

1. **获得确认**: 确认重构方案和实施计划
2. **环境准备**: 创建feature分支，配置测试环境
3. **开始Phase 1**: 从最低风险的数据层提取开始
4. **持续集成**: 每个Phase完成后进行充分验证

---

**重构原则**: "小步快跑，持续验证，确保稳定"