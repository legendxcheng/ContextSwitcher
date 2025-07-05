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
        self.version = "1.0.0"
        self.app_name = "ContextSwitcher"
        
        # 核心组件 - 稍后导入
        self.task_manager = None
        self.hotkey_manager = None
        self.main_window = None
        self.data_storage = None
        
        # 运行状态
        self.running = False
        
        print(f"{self.app_name} v{self.version} 启动中...")
    
    def initialize_components(self):
        """初始化各个组件"""
        try:
            from core.task_manager import TaskManager
            from core.hotkey_manager import HotkeyManager
            from gui.main_window import MainWindow
            from utils.data_storage import DataStorage
            
            print("正在初始化组件...")
            
            # 初始化数据存储
            self.data_storage = DataStorage()
            print("  ✓ 数据存储模块")
            
            # 初始化任务管理器
            self.task_manager = TaskManager()
            print("  ✓ 任务管理器")
            
            # 初始化热键管理器
            self.hotkey_manager = HotkeyManager(self.task_manager)
            print("  ✓ 热键管理器")
            
            # 初始化主窗口
            self.main_window = MainWindow(self.task_manager)
            self.main_window.on_window_closed = self.cleanup
            print("  ✓ 主窗口")
            
            print("✓ 组件初始化完成")
            return True
            
        except Exception as e:
            print(f"✗ 组件初始化失败: {e}")
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
                
                print(f"✓ 已加载 {len(self.task_manager.tasks)} 个任务")
            else:
                print("✓ 无历史任务数据，从空白开始")
            
            return True
            
        except Exception as e:
            print(f"✗ 数据加载失败: {e}")
            return False
    
    def register_hotkeys(self):
        """注册全局热键"""
        try:
            # 启动热键监听器
            success = self.hotkey_manager.start()
            
            if success:
                print("✓ 热键注册完成")
                return True
            else:
                print("✗ 热键注册失败")
                return False
            
        except Exception as e:
            print(f"✗ 热键注册失败: {e}")
            return False
    
    def run(self):
        """运行主程序"""
        try:
            # 初始化组件
            if not self.initialize_components():
                return False
            
            # 加载数据
            if not self.load_data():
                print("警告: 数据加载失败，将使用空数据启动")
            
            # 注册热键
            if not self.register_hotkeys():
                print("警告: 热键注册失败，只能使用GUI操作")
            
            # 启动主GUI
            print("启动主界面...")
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
                "✓ 项目目录结构已创建\n"
                "✓ requirements.txt已生成\n"
                "✓ __init__.py文件已创建\n"
                "✓ main.py入口文件已创建\n"
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
            
            # 注销热键
            if self.hotkey_manager:
                self.hotkey_manager.cleanup()
                print("✓ 热键已注销")
            
            # 保存数据
            if self.data_storage and self.task_manager:
                tasks = self.task_manager.get_all_tasks()
                if self.data_storage.save_tasks(tasks):
                    print("✓ 数据已保存")
                else:
                    print("✗ 数据保存失败")
            
            print("✓ 资源清理完成")
            
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