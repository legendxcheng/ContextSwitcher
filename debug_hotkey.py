#!/usr/bin/env python3
"""
热键调试脚本 - 快速诊断热键问题
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def simple_hotkey_test():
    """简单的热键测试"""
    print("🔧 简单热键测试...")
    
    try:
        from pynput import keyboard
        from pynput.keyboard import Key, KeyCode
        
        print("✅ pynput已成功导入")
        
        # 跟踪按键状态
        pressed_keys = set()
        hotkey_detected = False
        
        def on_press(key):
            pressed_keys.add(key)
            print(f"按下: {key}")
            
            # 检查Ctrl+Alt+1组合
            ctrl_pressed = Key.ctrl_l in pressed_keys or Key.ctrl_r in pressed_keys
            alt_pressed = Key.alt_l in pressed_keys or Key.alt_r in pressed_keys
            key_1_pressed = KeyCode.from_char('1') in pressed_keys
            
            if ctrl_pressed and alt_pressed and key_1_pressed:
                print("🎉 检测到Ctrl+Alt+1组合键！")
                nonlocal hotkey_detected
                hotkey_detected = True
                return False  # 停止监听
        
        def on_release(key):
            pressed_keys.discard(key)
            print(f"释放: {key}")
        
        print("💡 请按Ctrl+Alt+1测试热键...")
        print("💡 按ESC键退出测试")
        
        # 创建监听器
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
        
        if hotkey_detected:
            print("✅ 热键检测成功！")
            return True
        else:
            print("⚠️ 未检测到热键")
            return False
            
    except Exception as e:
        print(f"❌ 热键测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_task_switching():
    """测试任务切换逻辑"""
    print("\n🔧 测试任务切换逻辑...")
    
    try:
        # 导入必要模块
        from core.window_manager import WindowManager
        from core.task_manager import TaskManager
        from utils.data_storage import DataStore
        
        # 创建组件
        data_store = DataStore()
        window_manager = WindowManager()
        task_manager = TaskManager(data_store, window_manager)
        
        # 创建测试任务
        print("📝 创建测试任务...")
        task1 = task_manager.add_task("测试任务1", "描述1", [])
        task2 = task_manager.add_task("测试任务2", "描述2", [])
        
        if task1 and task2:
            print("✅ 测试任务创建成功")
            
            # 测试切换
            print("🔄 测试任务切换...")
            result1 = task_manager.switch_to_task(0)
            print(f"  切换到任务1: {'✅' if result1 else '❌'}")
            
            result2 = task_manager.switch_to_task(1)
            print(f"  切换到任务2: {'✅' if result2 else '❌'}")
            
            # 测试无效索引
            result3 = task_manager.switch_to_task(5)
            print(f"  切换到无效任务: {'❌' if not result3 else '✅ (应该失败)'}")
            
            return True
        else:
            print("❌ 测试任务创建失败")
            return False
            
    except Exception as e:
        print(f"❌ 任务切换测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_permissions():
    """检查权限和环境"""
    print("\n🔧 检查权限和环境...")
    
    issues = []
    
    # 检查Python环境
    print(f"🐍 Python版本: {sys.version}")
    
    # 检查必要的库
    try:
        import pynput
        print(f"✅ pynput版本: {pynput.__version__}")
    except Exception as e:
        issues.append(f"pynput问题: {e}")
    
    try:
        import win32gui
        print("✅ pywin32可用")
    except Exception as e:
        issues.append(f"pywin32问题: {e}")
    
    # 检查管理员权限
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if is_admin:
            print("✅ 以管理员权限运行")
        else:
            print("⚠️ 非管理员权限运行，可能影响全局热键")
    except Exception as e:
        issues.append(f"权限检查失败: {e}")
    
    if issues:
        print("\n⚠️ 发现问题:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("✅ 环境检查通过")
        return True

def main():
    """主函数"""
    print("🚀 热键问题调试脚本")
    print("=" * 40)
    
    # 环境检查
    env_ok = check_permissions()
    
    if not env_ok:
        print("\n❌ 环境检查失败，请先解决上述问题")
        return
    
    # 任务切换测试
    task_ok = test_task_switching()
    
    if not task_ok:
        print("\n❌ 任务切换逻辑有问题")
        return
    
    # 热键测试
    print("\n" + "=" * 40)
    print("开始热键测试...")
    print("请确保没有其他程序占用Ctrl+Alt+1热键")
    input("按回车键继续...")
    
    hotkey_ok = simple_hotkey_test()
    
    if hotkey_ok:
        print("\n✅ 热键功能正常！")
        print("🔧 如果主程序中热键仍不工作，可能的原因:")
        print("  1. 热键管理器启动时机问题")
        print("  2. 任务列表为空")
        print("  3. GUI事件循环冲突")
        print("  4. 其他程序占用了热键")
    else:
        print("\n❌ 热键功能异常！")
        print("🔧 可能的解决方案:")
        print("  1. 以管理员权限运行")
        print("  2. 关闭其他可能冲突的程序")
        print("  3. 尝试不同的热键组合")
        print("  4. 检查Windows安全设置")

if __name__ == "__main__":
    main()