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

try:
    import FreeSimpleGUI as sg
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    print("运行: pip install FreeSimpleGUI")
    sys.exit(1)

try:
    import win32gui
    import win32con
except ImportError:
    print("错误: 请先安装pywin32")
    print("运行: pip install pywin32")
    sys.exit(1)

try:
    from pynput import keyboard
except ImportError:
    print("错误: 请先安装pynput")
    print("运行: pip install pynput")
    sys.exit(1)


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
        self.tray_manager = None  # 新增：系统托盘管理器

        # 运行状态
        self.running = False
        self.should_exit = False  # 标记是否应该退出程序（托盘退出菜单）
        
        print(f"{self.app_name} v{self.version} 启动中...")
    
    def initialize_components(self):
        """初始化各个组件"""
        try:
            from core.task_manager import TaskManager
            from core.hotkey_manager import HotkeyManager
            from core.smart_rebind_manager import SmartRebindManager
            from core.task_status_manager import TaskStatusManager
            from gui.main_window import MainWindow
            from utils.data_storage import DataStorage
            
            print("正在初始化组件...")
            
            # 初始化数据存储
            self.data_storage = DataStorage()
            print("  [OK] 数据存储模块")
            
            # 初始化任务管理器
            self.task_manager = TaskManager()
            print("  [OK] 任务管理器")
            
            # 初始化热键管理器
            self.hotkey_manager = HotkeyManager(self.task_manager)
            print("  [OK] 热键管理器")
            
            # 初始化智能重新绑定管理器
            self.smart_rebind_manager = SmartRebindManager(
                self.task_manager, self.task_manager.window_manager
            )
            print("  [OK] 智能重新绑定管理器")
            
            # 初始化任务状态管理器
            self.task_status_manager = TaskStatusManager(self.task_manager)
            print("  [OK] 任务状态管理器")
            
            # 初始化主窗口（传递 data_storage 以支持自动保存）
            self.main_window = MainWindow(self.task_manager, self.data_storage)
            self.main_window.smart_rebind_manager = self.smart_rebind_manager
            self.main_window.task_status_manager = self.task_status_manager
            self.main_window.on_window_closed = self.cleanup
            print("  [OK] 主窗口")
            
            # 初始化任务切换器
            from gui.task_switcher_dialog import TaskSwitcherDialog
            self.task_switcher = TaskSwitcherDialog(self.task_manager)
            print("  [OK] 任务切换器")

            # 初始化系统托盘
            try:
                from utils.tray_manager import create_tray_manager
                self.tray_manager = create_tray_manager(self.app_name)
                if self.tray_manager:
                    # 设置托盘回调
                    self.tray_manager.on_show = self._on_tray_show
                    self.tray_manager.on_hide = self._on_tray_hide
                    self.tray_manager.on_exit = self._on_tray_exit
                    print("  [OK] 系统托盘")
                else:
                    print("  [INFO] 系统托盘不可用（pystray未安装）")
            except Exception as e:
                print(f"  [WARNING] 系统托盘初始化失败: {e}")

            print("[OK] 组件初始化完成")
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
    
    def register_hotkeys(self):
        """注册全局热键"""
        try:
            # 设置主窗口引用到热键管理器（用于线程安全通信）
            if self.main_window and self.main_window.window:
                self.hotkey_manager.set_main_window(self.main_window.window)
                print("[OK] 热键管理器已连接到主窗口")
            else:
                print("⚠️ 主窗口未创建，使用备用回调方案")
                # 设置切换器回调作为备用方案
                self.hotkey_manager.on_switcher_triggered = self.show_task_switcher
            
            # 设置主窗口的热键回调
            if self.main_window:
                self.main_window.on_hotkey_switcher_triggered = self.show_task_switcher
            
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
                        main_window_position = self.main_window.window_state_manager.get_current_window_position()
                    except:
                        pass

                result = self.task_switcher.show(main_window_position)
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
            from gui.welcome_dialog import WelcomeDialog
            welcome = WelcomeDialog()
            if welcome.should_show():
                print("显示首次运行欢迎引导...")
                welcome.show()
                print("[OK] 欢迎引导完成")
        except Exception as e:
            print(f"显示欢迎引导失败: {e}")

    # ========== 系统托盘回调方法 ==========

    def _on_tray_show(self):
        """托盘菜单：显示窗口"""
        if self.main_window:
            self.main_window.bring_to_front()

    def _on_tray_hide(self):
        """托盘菜单：隐藏窗口"""
        if self.main_window:
            self.main_window.hide()

    def _on_tray_exit(self):
        """托盘菜单：退出程序"""
        # 设置退出标志
        self.should_exit = True
        # 停止主窗口事件循环
        if self.main_window:
            self.main_window.running = False
    
    def run(self):
        """运行主程序"""
        try:
            # 初始化组件
            if not self.initialize_components():
                return False

            # 加载数据
            if not self.load_data():
                print("警告: 数据加载失败，将使用空数据启动")

            # 首次运行显示欢迎引导
            self._show_welcome_if_needed()

            # 启动系统托盘（在主窗口之前启动）
            if self.tray_manager:
                self.tray_manager.start()

            # 显示主窗口（创建窗口实例）
            print("启动主界面...")
            self.main_window.show()

            # 在主窗口创建后注册热键（确保window对象存在）
            if not self.register_hotkeys():
                print("警告: 热键注册失败，只能使用GUI操作")

            # 运行主GUI事件循环
            self.running = True
            self.main_window.run()

            print("程序正常退出")
            return True

        except KeyboardInterrupt:
            print("用户中断程序")
            return True
        except Exception as e:
            print(f"程序运行时错误: {e}")
            traceback.print_exc()
            return False
        finally:
            self.cleanup()
    
    def run_temp_gui(self):
        """临时GUI测试 - 验证FreeSimpleGUI是否正常工作"""
        sg.theme('DefaultNoMoreNagging')
        
        layout = [
            [sg.Text(f"{self.app_name} v{self.version}", font=("Arial", 16))],
            [sg.Text("项目结构创建完成!")],
            [sg.Text("状态: 等待功能模块开发...")],
            [sg.Multiline(
                "[OK] 项目目录结构已创建\n"
                "[OK] requirements.txt已生成\n"
                "[OK] __init__.py文件已创建\n"
                "[OK] main.py入口文件已创建\n"
                "\n下一步:\n"
                "- 实现window_manager.py\n"
                "- 实现task_manager.py\n"
                "- 实现主界面GUI",
                size=(50, 10),
                disabled=True
            )],
            [sg.Button("确定", key="-OK-"), sg.Button("退出", key="-EXIT-")]
        ]
        
        window = sg.Window(self.app_name, layout, 
                          keep_on_top=True,
                          finalize=True)
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, "-EXIT-", "-OK-"):
                break
        
        window.close()
    
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
                self.task_switcher._cleanup()
                print("[OK] 任务切换器已清理")

            # 注销热键
            if self.hotkey_manager:
                self.hotkey_manager.cleanup()
                print("[OK] 热键已注销")

            # 停止系统托盘
            if self.tray_manager:
                self.tray_manager.stop()
                print("[OK] 系统托盘已停止")

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