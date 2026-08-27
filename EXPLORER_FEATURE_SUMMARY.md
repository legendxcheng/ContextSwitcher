# Explorer窗口路径获取与恢复功能实现总结

## 功能概述

本功能为ContextSwitcher添加了Explorer窗口路径感知能力，当Explorer窗口失效时能够：

1. **获取并存储Explorer窗口的当前文件夹路径**
2. **重新创建Explorer窗口并定位到原始路径**
3. **将新窗口最大化并显示在原始屏幕上**
4. **提供优雅的降级处理机制**

## 实现内容

### 1. 数据结构扩展
**文件**: `core/task_manager.py`
- 扩展`BoundWindow`类，添加以下字段：
  - `folder_path: Optional[str] = None` - Explorer窗口的文件夹路径
  - `window_rect: Optional[Tuple[int, int, int, int]] = None` - 窗口位置和大小

### 2. Explorer辅助模块
**文件**: `core/explorer_helper.py`
- 实现`ExplorerHelper`类，提供以下功能：
  - `is_explorer_window(hwnd)` - 检测Explorer窗口
  - `get_explorer_folder_path(hwnd)` - 获取Explorer文件夹路径
  - `create_explorer_window(path, rect)` - 创建Explorer窗口
  - `restore_explorer_window(path, rect)` - 恢复Explorer窗口（主要接口）

**技术特点**:
- 使用Shell.Application COM接口获取路径
- 支持多显示器环境下的窗口定位
- 提供完善的错误处理和降级机制
- 集成现有的ScreenHelper功能

### 3. TaskManager集成
**文件**: `core/task_manager.py`
- 在窗口绑定时自动获取Explorer路径信息
- 在窗口验证时尝试恢复失效的Explorer窗口
- 提供完整的错误处理和用户反馈

### 4. UI界面更新
**文件**: `gui/table_data_provider.py`
- 在任务列表中显示Explorer文件夹路径
- 添加工具提示功能显示完整路径信息
- 使用📁图标标识Explorer窗口

### 5. 数据存储升级
**文件**: `utils/data_storage.py`
- 更新数据版本号至1.1.0
- 添加向后兼容性处理
- 支持新字段的序列化和反序列化

### 6. 测试覆盖
**文件**: `tests/test_explorer_helper_simple.py`
- 核心功能单元测试
- 模拟Windows API调用
- 异常情况处理测试

## 技术实现细节

### COM接口使用
```python
# 使用Shell.Application获取Explorer路径
shell = win32com.client.Dispatch("Shell.Application")
for window in shell.Windows():
    if window.HWND == hwnd:
        location_url = window.LocationURL
        folder_path = unquote(location_url[8:])  # 移除"file:///"
```

### 多显示器支持
```python
# 利用现有的ScreenHelper功能
target_monitor = self.screen_helper.get_monitor_from_point(target_point)
work_area = target_monitor.get('rcWork')
win32gui.SetWindowPos(hwnd, 0, work_area[0], work_area[1], ...)
```

### 降级处理机制
1. **路径获取失败** → 记录警告，继续使用基本窗口激活
2. **窗口恢复失败** → 回退到打开默认Explorer位置
3. **多显示器定位失败** → 在主显示器创建窗口

## 用户体验改进

### 任务列表显示
- Explorer窗口优先显示文件夹名称（如：📁Documents）
- 多个Explorer窗口显示为"📁Documents+2"
- 工具提示显示完整路径信息

### 自动恢复流程
1. 用户切换到包含Explorer窗口的任务
2. 系统检测到Explorer窗口失效
3. 自动尝试恢复到原始文件夹路径
4. 将窗口定位到原始屏幕并最大化
5. 提示用户手动重新绑定新窗口

## 向后兼容性

- 旧版本数据文件可以正常加载
- 新字段对旧数据默认为None
- 不影响现有功能的正常运行

## 性能考虑

- COM接口调用有适当的超时控制
- 只在必要时调用Windows API
- 异常情况下快速降级处理

## 使用示例

```python
# 绑定Explorer窗口时自动获取路径
task_manager.add_task("项目开发", window_hwnds=[explorer_hwnd])

# 任务切换时自动恢复Explorer窗口
task_manager.switch_to_task(0)  # 如果Explorer失效会自动恢复
```

## 风险评估

### 低风险
- 使用Windows标准API
- 完善的错误处理
- 向后兼容性保证

### 中风险
- COM接口依赖Windows版本
- 多显示器配置变化

### 缓解措施
- 多层降级处理
- 详细的日志记录
- 用户友好的错误提示

## 测试验证

所有核心功能已通过以下测试：
- ✅ 数据结构扩展
- ✅ 序列化/反序列化
- ✅ Explorer路径获取
- ✅ 窗口恢复功能
- ✅ UI界面更新
- ✅ 向后兼容性

## 结论

本功能成功为ContextSwitcher添加了Explorer窗口路径感知能力，显著提升了开发者在多任务环境下的工作效率。实现过程严格遵循了现有架构设计，确保了系统的稳定性和可维护性。