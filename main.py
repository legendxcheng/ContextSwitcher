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

from utils.localization import get_localizer, tr


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
        self.herdr_monitor = None  # Herdr CLI 后台适配层
        self.qt_app = None
        self.qt_hotkey_proxy = None
        self._wired_hotkey_proxy = None
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
            from core.herdr_integration import HerdrIntegrationCoordinator
            from core.herdr_terminal import HerdrTerminalController
            from core.herdr_workspace import HerdrWorkspaceClient
            from gui.qt.herdr_runtime_monitor import HerdrRuntimeMonitor
            from utils.config import get_config

            print("正在初始化组件 (PySide6)...")

            # 初始化数据存储
            self.data_storage = DataStorage()
            print("  [OK] 数据存储模块")

            # 初始化任务管理器
            self.task_manager = TaskManager()
            print("  [OK] 任务管理器")

            # Herdr CLI 是同步接口；通过单线程适配层避免阻塞 Qt 主线程。
            herdr_config = get_config().get("integrations.herdr", {}) or {}
            configured_path = str(herdr_config.get("exe_path", "") or "")
            resolved_herdr_executable = HerdrWorkspaceClient.resolve_executable(
                configured_path
            )
            herdr_executable = resolved_herdr_executable or configured_path or "herdr"
            if resolved_herdr_executable:
                herdr_unavailable_message = ""
            elif configured_path:
                herdr_unavailable_message = tr(
                    "herdr.invalid_path", path=configured_path
                )
            else:
                herdr_unavailable_message = tr("herdr.not_found")
            herdr_client = HerdrWorkspaceClient(herdr_executable)
            self.herdr_monitor = HerdrRuntimeMonitor(
                HerdrIntegrationCoordinator(herdr_client),
                terminal_controller=HerdrTerminalController(
                    herdr_client,
                    herdr_executable=herdr_executable,
                    unavailable_message=herdr_unavailable_message,
                ),
            )
            print("  [OK] Herdr Agent 状态监控")

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

            # 所有对外信号已就绪后再启动首次 Herdr 快照。
            self.main_window.set_herdr_monitor(self.herdr_monitor)

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
            self.main_window.herdr_transition.connect(self._on_herdr_transition)
        except Exception as e:
            print(f"连接主窗口信号失败: {e}")

    def _setup_qt_task_callbacks(self):
        """设置任务管理器回调 (PySide6)"""
        if not self.task_manager:
            return

        def on_task_changed(task):
            if self.main_window:
                self.main_window.update_display()
                self.main_window.sync_active_task_metadata()
            self._auto_save_tasks()

        def on_task_switched(task, index):
            if self.main_window:
                self.main_window.update_display()
                self.main_window.set_status(
                    tr("main.messages.switched", task=task.name)
                )
                self.main_window.sync_active_task_metadata()

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
                tr("main.delete_dialog.title"),
                tr("main.delete_dialog.message", task=task.name),
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

    def _on_herdr_transition(self, transition):
        """将后台 workspace 的 blocked/done 转换显示为系统通知。"""
        if not self.tray_icon or not self.task_manager:
            return
        try:
            from core.herdr_integration import HerdrTaskState
            from utils.config import get_config

            config = get_config().get("integrations.herdr", {}) or {}
            if not config.get("monitoring_enabled", True):
                return
            if (
                transition.state is HerdrTaskState.BLOCKED
                and not config.get("notify_on_blocked", True)
            ):
                return
            if (
                transition.state is HerdrTaskState.DONE
                and not config.get("notify_on_done", True)
            ):
                return

            task = next(
                (
                    item for item in self.task_manager.tasks
                    if str(getattr(item, "id", "")) == transition.task_id
                ),
                None,
            )
            if task is None:
                return
            if transition.state is HerdrTaskState.BLOCKED:
                title = tr("notifications.herdr_blocked_title")
                detail = tr("notifications.herdr_blocked_detail")
            elif transition.state is HerdrTaskState.DONE:
                title = tr("notifications.herdr_done_title")
                detail = tr("notifications.herdr_done_detail")
            else:
                return
            self.tray_icon.show_message(
                title,
                tr("notifications.task_detail", task=task.name, detail=detail),
            )
        except Exception as exc:
            print(f"Herdr 通知失败: {exc}")
    
    def register_hotkeys(self):
        """注册全局热键"""
        try:
            self._wire_qt_hotkey_proxy()

            # 所有监听器线程事件都必须经过 Qt 信号边界。
            if self.qt_hotkey_proxy:
                self.hotkey_manager.set_event_sink(self.qt_hotkey_proxy)
                print("[OK] 热键管理器已连接到 Qt 代理")
            else:
                print("[ERROR] Qt 热键代理未初始化")
                return False
            
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

    def _wire_qt_hotkey_proxy(self):
        """Connect listener-thread events to GUI-thread application actions."""
        if not self.qt_hotkey_proxy or self._wired_hotkey_proxy is self.qt_hotkey_proxy:
            return

        self.qt_hotkey_proxy.task_switcher_requested.connect(
            lambda _name: self.show_task_switcher()
        )
        self.qt_hotkey_proxy.main_window_summon_requested.connect(
            self.summon_main_window
        )
        self.qt_hotkey_proxy.hotkey_error.connect(
            lambda message: print(f"热键错误: {message}")
        )
        self._wired_hotkey_proxy = self.qt_hotkey_proxy

    def summon_main_window(self):
        """Show the management window at the current cursor position."""
        if self.main_window:
            self.main_window.summon_at_cursor()
    
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

    def _enter_hidden_background_mode(self) -> bool:
        """Complete startup with the window hidden and controls available."""
        self._show_welcome_if_needed()

        print("主界面默认隐藏，双击 Alt 可在鼠标位置唤出")
        if self.main_window:
            self.main_window.hide()

        if self.tray_icon:
            self.tray_icon.show()

        if not self.register_hotkeys():
            print("警告: 热键注册失败，只能使用GUI操作")
            return False
        return True

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
                from PySide6.QtCore import QLocale
                from PySide6.QtWidgets import QApplication
                from gui.qt.app_style import APPLICATION_STYLE, configure_application_style
                from gui.qt.hotkey_proxy import QtHotkeyProxy
                from utils.config import get_config
            except ImportError:
                print("错误: 请先安装 PySide6")
                print("运行: pip install PySide6")
                return False

            # 固定平台无关样式，避免 Win10/Win11 自动选择不同的原生 QStyle
            QApplication.setStyle(APPLICATION_STYLE)

            # 创建 QApplication，并在任何窗口创建前应用全局主题
            self.qt_app = QApplication(sys.argv)
            configure_application_style(self.qt_app)
            self.qt_app.setQuitOnLastWindowClosed(False)

            localizer = get_localizer()
            localizer.set_language(
                get_config().get("app.language", "system"),
                QLocale.system().name(),
            )
            localizer.subscribe(self._on_language_changed)
            self._on_language_changed(localizer.language)

            # Qt 热键代理
            self.qt_hotkey_proxy = QtHotkeyProxy()
            self._wire_qt_hotkey_proxy()

            # 初始化组件
            if not self.initialize_components():
                return False

            # 加载数据
            if not self.load_data():
                print("警告: 数据加载失败，将使用空数据启动")
            if self.main_window:
                self.main_window.update_display()

            if not self._enter_hidden_background_mode():
                print("警告: 后台模式初始化不完整")

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

    def _on_language_changed(self, _language: str) -> None:
        """Apply locale metadata that belongs to the Qt application."""
        if not self.qt_app:
            return
        from PySide6.QtCore import Qt

        direction = get_localizer().text_direction
        self.qt_app.setLayoutDirection(
            Qt.RightToLeft if direction == "rtl" else Qt.LeftToRight
        )

        terminal_controller = getattr(self.herdr_monitor, "terminal_controller", None)
        if terminal_controller is not None and terminal_controller.unavailable_message:
            from utils.config import get_config

            configured_path = str(
                get_config().get("integrations.herdr.exe_path", "") or ""
            )
            terminal_controller.unavailable_message = (
                tr("herdr.invalid_path", path=configured_path)
                if configured_path
                else tr("herdr.not_found")
            )

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

            if self.main_window:
                self.main_window.cleanup()

            if self.herdr_monitor:
                self.herdr_monitor.shutdown(wait=False)
                print("[OK] Herdr Agent 状态监控已停止")

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
