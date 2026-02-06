"""
Wave.exe 窗口结构分析工具

分析 Wave.exe 的窗口层次结构，找出所有子窗口
这可以帮助我们确定是否需要将焦点设置到特定的子窗口
"""

import win32gui
import win32api
import win32con
import win32process


def find_wave_window():
    """查找 Wave.exe 窗口"""
    wave_windows = []

    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, pid
            )
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)

            exe_name = exe_path.split('\\')[-1].lower()
            if exe_name == 'wave.exe':
                title = win32gui.GetWindowText(hwnd)
                wave_windows.append((hwnd, title))
        except Exception:
            pass

        return True

    win32gui.EnumWindows(enum_callback, None)
    return wave_windows


def get_window_info(hwnd, indent=0):
    """获取窗口详细信息"""
    try:
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        is_visible = win32gui.IsWindowVisible(hwnd)
        is_enabled = win32gui.IsWindowEnabled(hwnd)

        info = {
            'hwnd': hwnd,
            'title': title,
            'class': class_name,
            'rect': rect,
            'visible': is_visible,
            'enabled': is_enabled,
            'indent': indent
        }
        return info
    except Exception as e:
        return None


def enum_child_windows(parent_hwnd, indent=0):
    """枚举所有子窗口"""
    children = []

    def enum_callback(hwnd, _):
        info = get_window_info(hwnd, indent)
        if info:
            children.append(info)
            # 递归枚举子窗口的子窗口
            sub_children = enum_child_windows(hwnd, indent + 1)
            children.extend(sub_children)
        return True

    try:
        win32gui.EnumChildWindows(parent_hwnd, enum_callback, None)
    except Exception:
        pass

    return children


def print_window_tree(window_info_list):
    """打印窗口树结构"""
    for info in window_info_list:
        indent = "  " * info['indent']
        visible = "✓" if info['visible'] else "✗"
        enabled = "✓" if info['enabled'] else "✗"

        print(f"{indent}[{info['hwnd']}]")
        print(f"{indent}  标题: {info['title'] or '(无标题)'}")
        print(f"{indent}  类名: {info['class']}")
        print(f"{indent}  可见: {visible}  启用: {enabled}")
        print(f"{indent}  位置: {info['rect']}")
        print()


def analyze_wave_window():
    """分析 Wave.exe 窗口结构"""
    print("=" * 70)
    print("Wave.exe 窗口结构分析")
    print("=" * 70)

    # 查找 Wave.exe 窗口
    print("\n1. 查找 Wave.exe 主窗口...")
    wave_windows = find_wave_window()

    if not wave_windows:
        print("✗ 未找到 Wave.exe 窗口")
        return

    print(f"✓ 找到 {len(wave_windows)} 个 Wave.exe 窗口\n")

    # 分析每个窗口
    for i, (hwnd, title) in enumerate(wave_windows, 1):
        print(f"\n{'=' * 70}")
        print(f"窗口 {i}: [{hwnd}] {title}")
        print(f"{'=' * 70}\n")

        # 获取主窗口信息
        main_info = get_window_info(hwnd, 0)
        if main_info:
            print("主窗口信息:")
            print(f"  句柄: {main_info['hwnd']}")
            print(f"  标题: {main_info['title']}")
            print(f"  类名: {main_info['class']}")
            print(f"  可见: {'✓' if main_info['visible'] else '✗'}")
            print(f"  启用: {'✓' if main_info['enabled'] else '✗'}")
            print(f"  位置: {main_info['rect']}")
            print()

        # 枚举子窗口
        print("子窗口树结构:")
        print("-" * 70)
        children = enum_child_windows(hwnd, 1)

        if children:
            print(f"找到 {len(children)} 个子窗口:\n")
            print_window_tree(children)

            # 找出可能需要焦点的窗口
            print("\n" + "=" * 70)
            print("可能需要焦点的窗口（可见且启用）:")
            print("=" * 70)

            focusable = [c for c in children if c['visible'] and c['enabled']]
            if focusable:
                for info in focusable:
                    indent = "  " * info['indent']
                    print(f"{indent}[{info['hwnd']}] {info['class']}")
                    if info['title']:
                        print(f"{indent}  标题: {info['title']}")
            else:
                print("未找到可见且启用的子窗口")
        else:
            print("未找到子窗口")

        print()

    print("\n" + "=" * 70)
    print("分析建议:")
    print("=" * 70)
    print("1. 如果有多个可见且启用的子窗口，尝试将焦点设置到这些窗口")
    print("2. 特别关注类名包含 'Edit', 'Chrome', 'WebView' 等的窗口")
    print("3. 如果 Wave.exe 是 Electron 应用，可能需要特殊处理")
    print("=" * 70)


if __name__ == '__main__':
    analyze_wave_window()
