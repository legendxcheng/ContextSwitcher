"""
调试 VSCode 进程工作目录获取功能
"""

import win32gui
import win32process
import win32api
import win32con
import ctypes
from ctypes import windll, c_void_p, c_ulong, byref, c_size_t, Structure, sizeof
from ctypes.wintypes import DWORD, HANDLE, ULONG

# 加载 ntdll
ntdll = windll.ntdll


class PROCESS_BASIC_INFORMATION(Structure):
    # 对于 64 位系统:
    # - ExitStatus: 4 bytes (DWORD/ULONG)
    # - PebBaseAddress: 8 bytes (pointer)
    # - AffinityMask: 8 bytes (SIZE_T)
    # - BasePriority: 4 bytes (ULONG)
    # - UniqueProcessId: 8 bytes (ULONG_PTR)
    # - InheritedFromUniqueProcessId: 8 bytes (ULONG_PTR)
    _fields_ = [
        ('ExitStatus', c_ulong),
        ('PebBaseAddress', c_void_p),
        ('AffinityMask', c_size_t),
        ('BasePriority', c_ulong),
        ('UniqueProcessId', c_size_t),
        ('InheritedFromUniqueProcessId', c_size_t),
    ]


def debug_peb_read(hwnd: int):
    """调试 PEB 读取过程"""
    print(f"调试窗口句柄: {hwnd}")

    # 获取进程 ID
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    print(f"进程 PID: {pid}")

    # 打开进程句柄
    process_handle = win32api.OpenProcess(
        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
        False, pid
    )

    if not process_handle:
        print("❌ 无法打开进程句柄")
        return

    # 获取整数句柄值
    process_handle_int = int(process_handle)
    print(f"✓ 进程句柄: {process_handle_int}")

    try:
        # 获取 PEB 地址
        pbi = PROCESS_BASIC_INFORMATION()
        return_length = c_ulong()

        status = ntdll.NtQueryInformationProcess(
            process_handle_int,
            0,  # ProcessBasicInformation
            byref(pbi),
            sizeof(PROCESS_BASIC_INFORMATION),
            byref(return_length)
        )

        print(f"NtQueryInformationProcess status: {status} (0=成功)")
        print(f"PEB 地址: 0x{pbi.PebBaseAddress or 0:X}")

        if status != 0:
            print("❌ NtQueryInformationProcess 失败")
            return

        # 读取 PEB 的前 64 字节
        peb_buffer = (c_ulong * 16)()
        bytes_read = c_size_t()

        result = windll.kernel32.ReadProcessMemory(
            process_handle_int,
            c_void_p(pbi.PebBaseAddress),  # 明确转换为 c_void_p
            peb_buffer,
            64,  # 直接使用整数，不用 c_size_t
            byref(bytes_read)
        )

        print(f"ReadProcessMemory PEB: {result}, 读取字节数: {bytes_read.value}")

        if not result:
            print("❌ 读取 PEB 失败")
            return

        # 打印 PEB 内容
        print("\nPEB 内容 (ULONG 数组):")
        for i in range(16):
            print(f"  [{i:2d}] 0x{peb_buffer[i]:08X} ({peb_buffer[i]})")

        # ProcessParameters 在偏移 0x20 (32 字节) = 8 个 ULONG
        # 在 64 位系统上，需要组合两个 ULONG 来获取完整地址
        process_params_addr = peb_buffer[8] | (peb_buffer[9] << 32)
        print(f"\nProcessParameters 地址: 0x{process_params_addr:X}")

        if process_params_addr == 0:
            print("❌ ProcessParameters 地址为空")
            return

        # 读取 RTL_USER_PROCESS_PARAMETERS
        # 读取更多字节以包含 CurrentDirectoryPath
        # 使用 c_byte 来读取原始字节，避免 ULONG 的字节序问题
        from ctypes import c_byte
        params_buffer_bytes = (c_byte * 128)()  # 128 字节

        result = windll.kernel32.ReadProcessMemory(
            process_handle_int,
            c_void_p(process_params_addr),
            params_buffer_bytes,
            128,
            byref(bytes_read)
        )

        print(f"\nReadProcessMemory Params: {result}, 读取字节数: {bytes_read.value}")

        if not result:
            print("❌ 读取 ProcessParameters 失败")
            return

        # 将字节转换为整数数组（小端序）
        # 直接从 c_byte 数组中读取值
        params_buffer = []
        for i in range(0, 128, 4):
            # 从 c_byte 数组中获取每个字节的整数值
            b0 = params_buffer_bytes[i] if i < len(params_buffer_bytes) else 0
            b1 = params_buffer_bytes[i+1] if i+1 < len(params_buffer_bytes) else 0
            b2 = params_buffer_bytes[i+2] if i+2 < len(params_buffer_bytes) else 0
            b3 = params_buffer_bytes[i+3] if i+3 < len(params_buffer_bytes) else 0
            # 获取整数值（c_byte 可能是负数，需要转换）
            b0 = b0 & 0xFF
            b1 = b1 & 0xFF
            b2 = b2 & 0xFF
            b3 = b3 & 0xFF
            value = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
            params_buffer.append(value)

        # 打印关键位置的字节
        print("\nProcessParameters 关键字节:")
        print(f"  偏移 0x00-0x0F (Reserved1): {params_buffer[0:4]}")
        print(f"  偏移 0x10-0x1F (ConsoleHandle, ConsoleFlags, StdInput): {params_buffer[4:8]}")
        print(f"  偏移 0x20-0x2F (StdOutput, StdError): {params_buffer[8:12]}")
        print(f"  偏移 0x30-0x3F (部分 CurrentDirectoryPath): {params_buffer[12:16]}")
        print(f"  偏移 0x40-0x4F (CurrentDirectoryPath + Handle): {params_buffer[16:20]}")

        # CurrentDirectoryPath.UNICODE_STRING 在偏移 0x38 = 56 字节 = 14 个 ULONG
        # 结构: Length(4), MaximumLength(4), Buffer(8)
        str_length = params_buffer[14]        # ULONG[14] = 偏移 0x38
        str_max_length = params_buffer[15]    # ULONG[15] = 偏移 0x3C
        str_buffer_low = params_buffer[16]    # ULONG[16] = 偏移 0x40
        str_buffer_high = params_buffer[17]   # ULONG[17] = 偏移 0x44

        print(f"\nCurrentDirectoryPath UNICODE_STRING (偏移 0x38 = ULONG[14]):")
        print(f"  Length: 0x{str_length:08X} ({str_length}) 字符")
        print(f"  MaximumLength: 0x{str_max_length:08X} ({str_max_length}) 字符")
        print(f"  Buffer 地址: 0x{str_buffer_low:08X}:{str_buffer_high:08X}")

        # 组合 64 位地址
        str_buffer = str_buffer_low | (str_buffer_high << 32)
        print(f"  Buffer 地址 (完整): 0x{str_buffer:X}")

        # 检查 Length 值是否合理
        if str_length > 0x2000:  # 路径通常不会超过 8KB
            print(f"  ⚠️ Length 值异常: {str_length}")
            # 尝试其他可能的偏移
            print(f"\n  尝试其他偏移...")
            # 检查偏移 0x28-0x30 附近的值
            for offset in range(10, 20):
                test_length = params_buffer[offset]
                test_buffer_low = params_buffer[offset + 2]
                test_buffer_high = params_buffer[offset + 3]
                if test_length > 0 and test_length < 0x2000 and test_buffer_low != 0:
                    print(f"    偏移 [{offset}]: Length={test_length}, Buffer=0x{test_buffer_low:08X}")

        if str_buffer == 0 or str_length == 0 or str_length > 0x2000:
            print("❌ CurrentDirectoryPath 无效")
            return

        # 读取路径字符串
        from ctypes.wintypes import WCHAR
        char_count = (str_length // 2) + 1
        path_buffer = (WCHAR * char_count)()

        result = windll.kernel32.ReadProcessMemory(
            process_handle_int,
            c_void_p(str_buffer),
            byref(path_buffer),
            str_length + 2,
            byref(bytes_read)
        )

        print(f"\nReadProcessMemory Path: {result}, 读取字节数: {bytes_read.value}")

        if not result:
            print("❌ 读取路径字符串失败")
            return

        working_dir = path_buffer[:char_count - 1]
        print(f"\n✓ 成功读取工作目录: {working_dir}")

        import os
        if os.path.isdir(working_dir):
            print(f"✓ 路径有效")
        else:
            print(f"❌ 路径无效")

    finally:
        win32api.CloseHandle(process_handle)


def main():
    print("=" * 60)
    print("调试 VSCode 进程工作目录获取功能")
    print("=" * 60)

    # 查找 VSCode 窗口
    vscode_windows = []

    def enum_callback(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True

            title = win32gui.GetWindowText(hwnd)
            if not title or "Visual Studio Code" not in title:
                return True

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            vscode_windows.append({'hwnd': hwnd, 'title': title, 'pid': pid})
        except Exception:
            pass
        return True

    win32gui.EnumWindows(enum_callback, None)

    if not vscode_windows:
        print("\n未找到 VSCode 窗口")
        return

    print(f"\n找到 {len(vscode_windows)} 个 VSCode 窗口\n")

    for i, win in enumerate(vscode_windows):
        print(f"\n--- 窗口 {i + 1}: {win['title'][:50]}... ---")
        debug_peb_read(win['hwnd'])


if __name__ == "__main__":
    main()
