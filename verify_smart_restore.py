#!/usr/bin/env python3
"""
智能窗口恢复功能验证脚本

测试 v1.2.0 新增的 Terminal 和 VS Code 窗口恢复功能：
1. 上下文提取
2. 窗口恢复命令生成
3. 数据持久化
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime


def test_module_imports():
    """测试模块导入"""
    print("\n[1] 测试模块导入...")

    try:
        from core.app_helpers import (
            BaseAppHelper,
            TerminalHelper,
            VSCodeHelper,
            AppHelperRegistry,
            get_app_helper_registry
        )
        print("  ✓ app_helpers 模块导入成功")

        from core.task_manager import TaskManager, BoundWindow, Task
        print("  ✓ task_manager 模块导入成功")

        return True
    except Exception as e:
        print(f"  ✗ 导入失败: {e}")
        return False


def test_terminal_title_parsing():
    """测试 Terminal 标题解析"""
    print("\n[2] 测试 Terminal 标题解析...")

    from core.app_helpers import TerminalHelper
    helper = TerminalHelper()

    test_cases = [
        (r"C:\Users\Dev - PowerShell", r"C:\Users\Dev", "PowerShell"),
        (r"D:\Projects\MyApp - Windows PowerShell", r"D:\Projects\MyApp", "Windows PowerShell"),
        ("MINGW64:/c/Users/Dev", r"C:\Users\Dev", "Git Bash"),
        (r"管理员: C:\Windows\System32 - cmd", r"C:\Windows\System32", "Command Prompt"),
        ("Windows PowerShell", None, "Windows PowerShell"),  # 无路径
    ]

    all_passed = True
    for title, expected_dir, expected_profile in test_cases:
        ctx = helper.extract_context(0, title)
        dir_match = ctx.get('working_directory') == expected_dir
        profile_match = ctx.get('terminal_profile') == expected_profile

        if dir_match and profile_match:
            print(f"  ✓ '{title[:40]}...' -> dir={ctx.get('working_directory')}, profile={ctx.get('terminal_profile')}")
        else:
            print(f"  ✗ '{title[:40]}...'")
            print(f"      期望: dir={expected_dir}, profile={expected_profile}")
            print(f"      实际: dir={ctx.get('working_directory')}, profile={ctx.get('terminal_profile')}")
            all_passed = False

    return all_passed


def test_vscode_title_parsing():
    """测试 VS Code 标题解析"""
    print("\n[3] 测试 VS Code 标题解析...")

    from core.app_helpers import VSCodeHelper
    helper = VSCodeHelper()

    test_cases = [
        ("main.py - MyProject - Visual Studio Code", "MyProject"),
        ("MyProject - Visual Studio Code", "MyProject"),
        (r"C:\Projects\test.py - Visual Studio Code", r"C:\Projects"),
        ("Visual Studio Code", None),  # 无项目
    ]

    all_passed = True
    for title, expected_dir in test_cases:
        ctx = helper.extract_context(0, title)
        if ctx.get('working_directory') == expected_dir:
            print(f"  ✓ '{title[:50]}' -> {ctx.get('working_directory')}")
        else:
            print(f"  ✗ '{title[:50]}'")
            print(f"      期望: {expected_dir}")
            print(f"      实际: {ctx.get('working_directory')}")
            all_passed = False

    return all_passed


def test_app_type_detection():
    """测试应用类型检测"""
    print("\n[4] 测试应用类型检测...")

    from core.app_helpers import get_app_helper_registry
    registry = get_app_helper_registry()

    test_cases = [
        ("WindowsTerminal.exe", "terminal"),
        ("powershell.exe", "terminal"),
        ("pwsh.exe", "terminal"),
        ("cmd.exe", "terminal"),
        ("Code.exe", "vscode"),
        ("explorer.exe", "explorer"),
        ("notepad.exe", "generic"),
        ("chrome.exe", "generic"),
    ]

    all_passed = True
    for process, expected in test_cases:
        result = registry.detect_app_type(process)
        if result == expected:
            print(f"  ✓ {process} -> {result}")
        else:
            print(f"  ✗ {process} -> {result} (期望: {expected})")
            all_passed = False

    return all_passed


def test_bound_window_context():
    """测试 BoundWindow 上下文功能"""
    print("\n[5] 测试 BoundWindow 上下文功能...")

    from core.task_manager import BoundWindow

    # 创建一个带完整上下文的 BoundWindow
    window = BoundWindow(
        hwnd=12345,
        title="Test - PowerShell",
        process_name="WindowsTerminal.exe",
        binding_time=datetime.now().isoformat(),
        app_type="terminal",
        working_directory=r"C:\Projects\Test",
        terminal_profile="PowerShell",
        window_rect=(0, 0, 1920, 1080)
    )

    # 测试 get_restore_context
    ctx = window.get_restore_context()

    checks = [
        ("app_type", ctx.get('app_type') == 'terminal'),
        ("working_directory", ctx.get('working_directory') == r"C:\Projects\Test"),
        ("terminal_profile", ctx.get('terminal_profile') == "PowerShell"),
        ("window_rect", ctx.get('window_rect') == (0, 0, 1920, 1080)),
    ]

    all_passed = True
    for name, passed in checks:
        if passed:
            print(f"  ✓ {name}: {ctx.get(name)}")
        else:
            print(f"  ✗ {name}: {ctx.get(name)}")
            all_passed = False

    return all_passed


def test_task_serialization():
    """测试任务序列化和反序列化"""
    print("\n[6] 测试任务序列化/反序列化...")

    from core.task_manager import Task, BoundWindow

    # 创建一个带新字段的任务
    task = Task(
        id="test_task_001",
        name="测试任务",
        description="智能窗口恢复测试",
        bound_windows=[
            BoundWindow(
                hwnd=111,
                title="Terminal Window",
                process_name="WindowsTerminal.exe",
                binding_time=datetime.now().isoformat(),
                app_type="terminal",
                working_directory=r"C:\Dev",
                terminal_profile="PowerShell"
            ),
            BoundWindow(
                hwnd=222,
                title="VS Code Window",
                process_name="Code.exe",
                binding_time=datetime.now().isoformat(),
                app_type="vscode",
                working_directory=r"C:\Projects\MyApp",
            )
        ]
    )

    # 序列化
    data = task.to_dict()
    print(f"  ✓ 序列化成功: {len(data['bound_windows'])} 个窗口")

    # 反序列化
    restored = Task.from_dict(data)
    print(f"  ✓ 反序列化成功: {restored.name}")

    # 验证新字段
    w1 = restored.bound_windows[0]
    w2 = restored.bound_windows[1]

    checks = [
        ("Terminal app_type", w1.app_type == "terminal"),
        ("Terminal working_directory", w1.working_directory == r"C:\Dev"),
        ("Terminal terminal_profile", w1.terminal_profile == "PowerShell"),
        ("VSCode app_type", w2.app_type == "vscode"),
        ("VSCode working_directory", w2.working_directory == r"C:\Projects\MyApp"),
    ]

    all_passed = True
    for name, passed in checks:
        if passed:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            all_passed = False

    return all_passed


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n[7] 测试向后兼容性...")

    from core.task_manager import Task, BoundWindow

    # 模拟旧版本数据（没有新字段）
    old_data = {
        "id": "old_task_001",
        "name": "旧版本任务",
        "description": "测试向后兼容",
        "status": "todo",
        "bound_windows": [
            {
                "hwnd": 333,
                "title": "Old Window",
                "process_name": "explorer.exe",
                "binding_time": "2024-01-01T00:00:00",
                "is_valid": True,
                # 注意：没有 folder_path, window_rect, app_type, working_directory, terminal_profile
            }
        ],
        "created_at": "2024-01-01T00:00:00",
        "last_accessed": "2024-01-01T00:00:00",
        "access_count": 0,
        "tags": [],
        "priority": 0,
        "notes": "",
        "total_time_seconds": 0
    }

    # 尝试加载旧数据
    try:
        task = Task.from_dict(old_data)
        window = task.bound_windows[0]

        checks = [
            ("加载成功", True),
            ("folder_path 默认为 None", window.folder_path is None),
            ("window_rect 默认为 None", window.window_rect is None),
            ("app_type 自动推断", window.app_type == "explorer"),
            ("working_directory 默认为 None", window.working_directory is None),
            ("terminal_profile 默认为 None", window.terminal_profile is None),
        ]

        all_passed = True
        for name, passed in checks:
            if passed:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"  ✗ 加载旧数据失败: {e}")
        return False


def test_restore_capability():
    """测试恢复能力检测"""
    print("\n[8] 测试恢复能力检测...")

    from core.app_helpers import get_app_helper_registry
    registry = get_app_helper_registry()

    test_cases = [
        # (app_type, context, expected_can_restore)
        ("terminal", {"working_directory": r"C:\Dev"}, True),
        ("terminal", {}, True),  # Terminal 可以无工作目录恢复
        ("vscode", {"working_directory": r"C:\Projects"}, True),
        ("vscode", {}, False),  # VS Code 需要项目路径
        ("generic", {"working_directory": r"C:\Dev"}, False),  # 不支持的类型
    ]

    all_passed = True
    for app_type, context, expected in test_cases:
        result = registry.can_restore(app_type, context)
        if result == expected:
            print(f"  ✓ {app_type} + {context} -> can_restore={result}")
        else:
            print(f"  ✗ {app_type} + {context} -> can_restore={result} (期望: {expected})")
            all_passed = False

    return all_passed


def main():
    """运行所有测试"""
    print("=" * 60)
    print("ContextSwitcher v1.2.0 智能窗口恢复功能验证")
    print("=" * 60)

    tests = [
        ("模块导入", test_module_imports),
        ("Terminal 标题解析", test_terminal_title_parsing),
        ("VS Code 标题解析", test_vscode_title_parsing),
        ("应用类型检测", test_app_type_detection),
        ("BoundWindow 上下文", test_bound_window_context),
        ("任务序列化", test_task_serialization),
        ("向后兼容性", test_backward_compatibility),
        ("恢复能力检测", test_restore_capability),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ 测试异常: {e}")
            results.append((name, False))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    print()
    print(f"通过: {passed_count}/{total_count}")

    if passed_count == total_count:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️ {total_count - passed_count} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
