#!/usr/bin/env python3
"""
ContextSwitcher - 开发者多任务切换器
主程序入口文件

功能:
- 启动GUI界面
- 初始化任务管理器
- 注册全局热键
- 管理程序生命周期

作者: ContextSwitcher Team
版本: 1.0.0
"""

import sys
import os
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class ContextSwitcher:
    """ContextSwitcher主应用类"""
    
    def __init__(self):
        """初始化应用"""
        self.version = "1.2.0"  # v1.2.0: 智能窗口恢复 (Terminal/VS Code支持)
        self.app_name = "ContextSwitcher"
        
        # 核心组件 - 稍后导入
        self.task_manager = None
        self.hotkey_manager = None
        self.main_window = None
        self.data_storage = None
        self.smart_rebind_manager = None
        self.task_status_manager = None
        self.task_switcher = None  # 新增：任务切换器
        self.tray_icon = None  # PySide6 系统托盘
        self.qt_app = None
        self.qt_hotkey_proxy = None
        self.task_dialog = None
        self.settings_dialog = None

        # 运行状态
        self.running = False
        self.should_exit = False  # 标记是否应该退出程序（托盘退出菜单）
        
        print(f"{self.app_name} v{self.version} 启动中...")
    
    def initialize_components(self):
        """初始化各个组件"""
        return self._initialize_qt_components()

    def _initialize_qt_components(self):
        """初始化 PySide6 组件"""
        try:
            from core.task_manager import TaskManager
            from core.hotkey_manager import HotkeyManager
            from core.smart_rebind_manager import SmartRebindManager
            from core.task_status_manager import TaskStatusManager
            from utils.data_storage import DataStorage
            from gui.qt.qt_main_window import QtMainWindow
            from gui.qt.qt_task_dialog import QtTaskDialog
            from gui.qt.qt_settings_dialog import QtSettingsDialog
            from gui.qt.qt_task_switcher import QtTaskSwitcher
            from gui.qt.widgets.system_tray import SystemTrayIcon

            print("正在初始化组件 (PySide6)...")

            # 初始化数据存储
            self.data_storage = DataStorage()
            print("  [OK] 数据存储模块")

            # 初始化任务管理器
            self.task_manager = TaskManager()
            print("  [OK] 任务管理器")

            # 初始化热键管理器
            self.hotkey_manager = HotkeyManager(self.task_manager)
            globals()["hotkey_manager"] = self.hotkey_manager
            print("  [OK] 热键管理器")

            # 初始化智能重新绑定管理器
            self.smart_rebind_manager = SmartRebindManager(
                self.task_manager, self.task_manager.window_manager
            )
            print("  [OK] 智能重新绑定管理器")

            # 初始化任务状态管理器
            self.task_status_manager = TaskStatusManager(self.task_manager)
            print("  [OK] 任务状态管理器")

            # 初始化主窗口
            self.main_window = QtMainWindow(self.task_manager, self.data_storage)
            self.main_window.smart_rebind_manager = self.smart_rebind_manager
            self.main_window.task_status_manager = self.task_status_manager
            print("  [OK] 主窗口")

            # 对话框
            self.task_dialog = QtTaskDialog(self.main_window, self.task_manager)
            self.settings_dialog = QtSettingsDialog(self.main_window, self.task_manager)
            print("  [OK] 对话框")

            # 初始化任务切换器
            self.task_switcher = QtTaskSwitcher(self.task_manager)
            print("  [OK] 任务切换器")

            # 初始化系统托盘
            try:
                icon_path = project_root / "icon.ico"
                self.tray_icon = SystemTrayIcon(icon_path if icon_path.exists() else None)
                self.tray_icon.show_requested.connect(self._on_tray_show)
                self.tray_icon.hide_requested.connect(self._on_tray_hide)
                self.tray_icon.quit_requested.connect(self._on_tray_exit)
                print("  [OK] 系统托盘")
            except Exception as e:
                print(f"  [WARNING] 系统托盘初始化失败: {e}")
                self.tray_icon = None

            # 连接主窗口信号
            self._setup_qt_window_signals()

            # 设置任务管理器回调
            self._setup_qt_task_callbacks()

            print("[OK] 组件初始化完成 (PySide6)")
            return True

        except Exception as e:
            print(f"[ERROR] 组件初始化失败: {e}")
            traceback.print_exc()
            return False
    
    def load_data(self):
        """加载用户数据"""
        try:
            # 从JSON文件加载任务数据
            tasks_data = self.data_storage.load_tasks()

            if tasks_data:
                # 重建任务对象
                from core.task_manager import Task
                for task_data in tasks_data:
                    try:
                        task = Task.from_dict(task_data)
                        self.task_manager.tasks.append(task)
                    except Exception as e:
                        print(f"加载任务失败 {task_data.get('name', 'Unknown')}: {e}")

                print(f"[OK] 已加载 {len(self.task_manager.tasks)} 个任务")
            else:
                print("[OK] 无历史任务数据，从空白开始")

            # 加载时间追踪数据
            from core.time_tracker import get_time_tracker
            time_tracker = get_time_tracker()
            self.data_storage.load_time_tracking(time_tracker)

            # 更新任务名称映射
            for task in self.task_manager.tasks:
                time_tracker.task_names[task.id] = task.name

            return True

        except Exception as e:
            print(f"[ERROR] 数据加载失败: {e}")
            return False

    def _setup_qt_window_signals(self):
        """连接 PySide6 主窗口信号"""
        if not self.main_window:
            return

        try:
            self.main_window.add_task_requested.connect(self._on_qt_add_task)
            self.main_window.edit_task_requested.connect(self._on_qt_edit_task)
            self.main_window.delete_task_requested.connect(self._on_qt_delete_task)
            self.main_window.settings_requested.connect(self._on_qt_settings)
        except Exception as e:
            print(f"连接主窗口信号失败: {e}")

    def _setup_qt_task_callbacks(self):
        """设置任务管理器回调 (PySide6)"""
        if not self.task_manager:
            return

        def on_task_changed(task):
            if self.main_window:
                self.main_window.update_display()
            self._auto_save_tasks()

        def on_task_switched(task, index):
            if self.main_window:
                self.main_window.update_display()
                self.main_window.set_status(f"已切换到: {task.name}")

        self.task_manager.on_task_added = on_task_changed
        self.task_manager.on_task_removed = on_task_changed
        self.task_manager.on_task_updated = on_task_changed
        self.task_manager.on_task_switched = on_task_switched

    def _auto_save_tasks(self):
        """自动保存任务数据"""
        try:
            if not self.data_storage or not self.task_manager:
                return
            tasks = self.task_manager.get_all_tasks()
            self.data_storage.save_tasks(tasks)
        except Exception as e:
            print(f"自动保存失败: {e}")

    def _on_qt_add_task(self):
        """PySide6 添加任务"""
        if not self.task_dialog:
            return
        result = self.task_dialog.show_add_dialog()
        if result and self.main_window:
            self.main_window.update_display()

    def _on_qt_edit_task(self, task):
        """PySide6 编辑任务"""
        if not self.task_dialog or not task:
            return
        result = self.task_dialog.show_edit_dialog(task)
        if result and self.main_window:
            self.main_window.update_display()

    def _on_qt_delete_task(self, task):
        """PySide6 删除任务"""
        if not self.task_manager or not task:
            return

        try:
            from PySide6.QtWidgets import QMessageBox
            confirm = QMessageBox.question(
                self.main_window,
                "删除任务",
                f"确定要删除任务 \"{task.name}\" 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return
        except Exception:
            pass

        self.task_manager.remove_task(task.id)
        if self.main_window:
            self.main_window.update_display()

    def _on_qt_settings(self):
        """PySide6 设置对话框"""
        if not self.settings_dialog:
            return
        result = self.settings_dialog.show_settings_dialog()
        if result and self.main_window:
            self.main_window.update_display()
    
    def register_hotkeys(self):
        """注册全局热键"""
        try:
            # 设置主窗口引用到热键管理器（用于线程安全通信）
            if self.qt_hotkey_proxy:
                self.hotkey_manager.set_main_window(self.qt_hotkey_proxy)
                print("[OK] 热键管理器已连接到 Qt 代理")
            else:
                print("⚠️ Qt 热键代理未初始化，使用备用回调方案")
                self.hotkey_manager.on_switcher_triggered = self.show_task_switcher

            # 备用回调（用于异常兜底）
            self.hotkey_manager.on_switcher_triggered = self.show_task_switcher
            
            # 启动热键监听器
            success = self.hotkey_manager.start()
            
            if success:
                print("[OK] 热键注册完成")
                return True
            else:
                print("[ERROR] 热键注册失败")
                return False
            
        except Exception as e:
            print(f"[ERROR] 热键注册失败: {e}")
            return False
    
    def show_task_switcher(self):
        """显示任务切换器"""
        try:
            if self.task_switcher:
                print("🎯 热键触发任务切换器...")
                # 获取主窗口位置
                main_window_position = None
                if self.main_window:
                    try:
                        pos = self.main_window.pos()
                        main_window_position = (pos.x(), pos.y())
                    except Exception:
                        pass

                result = self.task_switcher.show_switcher(main_window_position)
                if result:
                    print("✅ 任务切换器执行成功")
                else:
                    print("🔄 任务切换器已显示或用户取消")
            else:
                print("⚠️ 任务切换器未初始化")
        except Exception as e:
            print(f"显示任务切换器失败: {e}")
            import traceback
            traceback.print_exc()

    def _show_welcome_if_needed(self):
        """如果是首次运行，显示欢迎引导"""
        try:
            from gui.qt.qt_welcome_dialog import show_welcome_if_first_run
            if show_welcome_if_first_run(self.main_window):
                print("[OK] 欢迎引导完成")
        except Exception as e:
            print(f"显示欢迎引导失败: {e}")

    # ========== 系统托盘回调方法 ==========

    def _on_tray_show(self):
        """托盘菜单：显示窗口"""
        if self.main_window:
            self.main_window.show_from_tray()

    def _on_tray_hide(self):
        """托盘菜单：隐藏窗口"""
        if self.main_window:
            self.main_window.hide_to_tray()

    def _on_tray_exit(self):
        """托盘菜单：退出程序"""
        # 设置退出标志
        self.should_exit = True
        if self.qt_app:
            self.qt_app.quit()
    
    def run(self):
        """运行主程序"""
        return self._run_qt()
    
    def _run_qt(self):
        """运行 PySide6 版本"""
        try:
            try:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtCore import QObject, Signal
            except ImportError:
                print("错误: 请先安装 PySide6")
                print("运行: pip install PySide6")
                return False

            # 创建 QApplication
            self.qt_app = QApplication(sys.argv)
            self.qt_app.setQuitOnLastWindowClosed(False)

            # Qt 热键代理
            class _QtHotkeyProxy(QObject):
                hotkey_triggered = Signal(str)
                hotkey_error = Signal(str)

                def write_event_value(self, event, value):
                    if event == "-HOTKEY_TRIGGERED-":
                        self.hotkey_triggered.emit(value)
                    elif event == "-HOTKEY_ERROR-":
                        self.hotkey_error.emit(value)

            self.qt_hotkey_proxy = _QtHotkeyProxy()
            self.qt_hotkey_proxy.hotkey_triggered.connect(lambda _name: self.show_task_switcher())
            self.qt_hotkey_proxy.hotkey_error.connect(lambda msg: print(f"热键错误: {msg}"))

            # 初始化组件
            if not self.initialize_components():
                return False

            # 加载数据
            if not self.load_data():
                print("警告: 数据加载失败，将使用空数据启动")
            if self.main_window:
                self.main_window.update_display()

            # 首次运行显示欢迎引导
            self._show_welcome_if_needed()

            # 显示主窗口
            print("启动主界面 (PySide6)...")
            self.main_window.show()

            # 启动系统托盘
            if self.tray_icon:
                self.tray_icon.show()

            # 注册热键
            if not self.register_hotkeys():
                print("警告: 热键注册失败，只能使用GUI操作")

            self.running = True
            exit_code = self.qt_app.exec()
            print("程序正常退出")
            return exit_code == 0

        except KeyboardInterrupt:
            print("用户中断程序")
            return True
        except Exception as e:
            print(f"程序运行时错误: {e}")
            traceback.print_exc()
            return False
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        try:
            self.running = False

            # 结束当前任务的时间追踪会话
            from core.time_tracker import get_time_tracker
            time_tracker = get_time_tracker()
            if time_tracker.current_session:
                ended_session = time_tracker.end_session()
                if ended_session and self.task_manager:
                    # 更新任务的累计时间
                    task = self.task_manager.get_task_by_id(ended_session.task_id)
                    if task:
                        task.total_time_seconds += ended_session.duration_seconds
                print("[OK] 时间追踪会话已结束")

            # 清理任务切换器
            if self.task_switcher:
                if hasattr(self.task_switcher, "_cleanup"):
                    self.task_switcher._cleanup()
                    print("[OK] 任务切换器已清理")

            # 注销热键
            if self.hotkey_manager:
                self.hotkey_manager.cleanup()
                print("[OK] 热键已注销")

            # 停止系统托盘
            if self.tray_icon:
                try:
                    self.tray_icon.hide()
                    print("[OK] 系统托盘已停止")
                except Exception:
                    pass

            # 保存数据（最终保存，作为双重保险）
            if self.data_storage and self.task_manager:
                print("[INFO] 执行退出时的最终保存（双重保险）...")
                tasks = self.task_manager.get_all_tasks()
                if self.data_storage.save_tasks(tasks):
                    print("[OK] 任务数据已保存")
                else:
                    print("[ERROR] 任务数据保存失败")

                # 保存时间追��数据
                if self.data_storage.save_time_tracking(time_tracker):
                    print("[OK] 时间追踪数据已保存")
                else:
                    print("[ERROR] 时间追踪数据保存失败")

            print("[OK] 资源清理完成")

        except Exception as e:
            print(f"清理资源时出错: {e}")


def main():
    """主函数"""
    print("=" * 50)
    print("ContextSwitcher - 开发者多任务切换器")
    print("Phase 1: 核心功能开发")
    print("=" * 50)
    
    # 检查操作系统
    if os.name != 'nt':
        print("错误: 此程序仅支持Windows系统")
        return 1
    
    # 创建并运行应用
    app = ContextSwitcher()
    success = app.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
