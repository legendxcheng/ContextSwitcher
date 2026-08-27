"""
全局热键管理模块

负责注册和处理全局热键:
- Ctrl+Alt+1-9 热键注册
- 热键事件处理
- 热键冲突检测
- 热键生命周期管理
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional, Protocol

try:
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode, Listener
except ImportError:
    print("错误: 请先安装pynput库")
    print("运行: pip install pynput")
    raise

from core.task_manager import TaskManager
from core.windows_alt_monitor import WindowsAltMonitor
from utils.config import get_config


class HotkeyEventSink(Protocol):
    """Thread-safe boundary used by the listener to request UI work."""

    def request_task_switcher(self, hotkey_name: str) -> None: ...

    def request_main_window_summon(self) -> None: ...

    def report_hotkey_error(self, message: str) -> None: ...


class HotkeyManager:
    """全局热键管理器"""
    
    ALT_KEYS = frozenset((Key.alt, Key.alt_l, Key.alt_r))

    def __init__(
        self,
        task_manager: TaskManager,
        listener_factory=Listener,
        monotonic_clock=time.monotonic,
        config=None,
    ):
        """初始化热键管理器
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.config = config or get_config()
        self._listener_factory = listener_factory
        self._monotonic_clock = monotonic_clock
        
        # 热键配置
        self.hotkey_config = self.config.get_hotkeys_config()
        self.enabled = self.hotkey_config.get("enabled", True)
        
        # 热键监听器
        self.listener: Optional[Listener] = None
        self.running = False
        self._native_alt_monitor = (
            WindowsAltMonitor(self._emit_main_window_summon)
            if os.name == "nt" and listener_factory is Listener
            else None
        )
        
        # 热键状态跟踪（线程安全：只在pynput子线程中访问）
        self.pressed_keys: set[Any] = set()
        self.hotkey_combinations: Dict[str, Dict[str, Any]] = {}
        self.last_hotkey_time = 0
        self.hotkey_debounce = 0.5  # 防抖间隔（秒）- 增加到0.5秒
        self.alt_double_tap_interval = 0.35
        self.alt_tap_max_duration = 0.5
        self._active_alt_key = None
        self._alt_press_started_at = None
        self._alt_tap_invalidated = False
        self._last_alt_tap_released_at = None
        self._summon_emit_lock = threading.Lock()
        self._last_summon_emitted_at = None
        self._summon_emit_debounce = 0.25
        
        # 线程安全通信
        self.event_sink: Optional[HotkeyEventSink] = None
        
        # 初始化热键组合
        self._initialize_hotkey_combinations()
        
        print("[OK] 热键管理器初始化完成")
    
    def set_event_sink(self, event_sink: HotkeyEventSink):
        """Set the listener-to-GUI event boundary.
        
        Args:
            event_sink: Thread-safe sink that queues work for the GUI thread.
        """
        self.event_sink = event_sink
        print("[OK] 热键管理器已设置线程安全事件代理")
    
    def _initialize_hotkey_combinations(self):
        """初始化热键组合 - 仅支持任务切换器热键"""
        # 仅初始化任务切换器热键（移除数字键支持）
        switcher_modifiers = self.hotkey_config.get("switcher_modifiers", ["ctrl", "alt"])
        switcher_key = self.hotkey_config.get("switcher_key", "space")
        
        if self.hotkey_config.get("switcher_enabled", True):
            switcher_modifier_keys = set()
            for mod in switcher_modifiers:
                if mod.lower() == "ctrl":
                    switcher_modifier_keys.add(Key.ctrl_l)
                    switcher_modifier_keys.add(Key.ctrl_r)
                elif mod.lower() == "alt":
                    switcher_modifier_keys.add(Key.alt_l)
                    switcher_modifier_keys.add(Key.alt_r)
                elif mod.lower() == "shift":
                    switcher_modifier_keys.add(Key.shift_l)
                    switcher_modifier_keys.add(Key.shift_r)
                elif mod.lower() == "win":
                    switcher_modifier_keys.add(Key.cmd)
            
            # 创建切换器热键组合
            switcher_hotkey_name = "+".join(switcher_modifiers + [switcher_key])
            
            self.hotkey_combinations[switcher_hotkey_name] = {
                "modifiers": switcher_modifier_keys,
                "key": Key.space if switcher_key.lower() == "space" else KeyCode.from_char(switcher_key),
                "description": "打开任务切换器",
                "type": "switcher"
            }
            
            print(f"[OK] 已配置任务切换器热键: {switcher_hotkey_name}")
        else:
            print("[WARN] 任务切换器热键已禁用")
        
        print(f"[OK] 热键配置完成，共 {len(self.hotkey_combinations)} 个热键组合")
    
    def start(self) -> bool:
        """启动热键监听
        
        Returns:
            是否成功启动
        """
        if not self.enabled:
            print("热键功能已禁用")
            return False
        
        if self.running:
            print("热键监听器已在运行")
            return True
        
        try:
            # 创建键盘监听器
            self.listener = self._listener_factory(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            
            # 启动监听器
            self.listener.start()
            if self._native_alt_monitor:
                self._native_alt_monitor.start()
            self.running = True
            
            print("[OK] 热键监听器已启动")
            
            # 显示注册的热键
            for hotkey_name, hotkey_info in self.hotkey_combinations.items():
                print(f"  {hotkey_name}: {hotkey_info['description']}")
            
            return True
            
        except Exception as e:
            print(f"启动热键监听器失败: {e}")
            self._report_hotkey_error(f"启动失败: {e}")
            return False
    
    def stop(self):
        """停止热键监听"""
        if not self.running and not (
            self._native_alt_monitor and self._native_alt_monitor.is_running
        ):
            return
        
        self.running = False

        if self._native_alt_monitor:
            self._native_alt_monitor.stop()
        
        if self.listener:
            try:
                self.listener.stop()
                self.listener = None
                print("[OK] 热键监听器已停止")
            except Exception as e:
                print(f"停止热键监听器时出错: {e}")
        
        # 清除按键状态
        self.pressed_keys.clear()
    
    def is_running(self) -> bool:
        """检查热键监听器是否运行"""
        listener_running = bool(
            self.running
            and self.listener
            and self.listener.running
            and getattr(self.listener, "is_alive", lambda: True)()
        )
        native_monitor_running = bool(
            not self._native_alt_monitor or self._native_alt_monitor.is_running
        )
        return listener_running and native_monitor_running
    
    def _on_key_press(self, key):
        """按键按下事件处理"""
        if not self.running:
            return
        
        try:
            was_pressed = key in self.pressed_keys
            # 添加到按下的按键集合
            self.pressed_keys.add(key)

            self._track_alt_press(key, was_pressed)
            
            # 检查是否匹配热键组合
            self._check_hotkey_combination()
            
        except Exception as e:
            print(f"处理按键按下事件失败: {e}")
    
    def _on_key_release(self, key):
        """按键释放事件处理"""
        if not self.running:
            return
        
        try:
            if key in self.ALT_KEYS:
                self._track_alt_release(key)

            # 从按下的按键集合中移除
            self.pressed_keys.discard(key)
            
        except Exception as e:
            print(f"处理按键释放事件失败: {e}")

    def _track_alt_press(self, key, was_pressed: bool):
        """Track the start of a standalone Alt tap."""
        if key not in self.ALT_KEYS:
            self._invalidate_alt_tap_sequence()
            return

        if was_pressed:
            return

        other_pressed_keys = self.pressed_keys - self.ALT_KEYS
        if other_pressed_keys or self._active_alt_key is not None:
            self._invalidate_alt_tap_sequence()
            return

        self._active_alt_key = key
        self._alt_press_started_at = self._monotonic_clock()
        self._alt_tap_invalidated = False

    def _track_alt_release(self, key):
        """Recognize a complete standalone Alt tap on key release."""
        now = self._monotonic_clock()
        duration = (
            now - self._alt_press_started_at
            if self._alt_press_started_at is not None
            else None
        )
        other_pressed_keys = self.pressed_keys - self.ALT_KEYS
        is_valid_tap = (
            key == self._active_alt_key
            and not self._alt_tap_invalidated
            and not other_pressed_keys
            and duration is not None
            and 0 <= duration <= self.alt_tap_max_duration
        )

        self._active_alt_key = None
        self._alt_press_started_at = None
        self._alt_tap_invalidated = False

        if not is_valid_tap:
            self._last_alt_tap_released_at = None
            return

        if (
            self._last_alt_tap_released_at is not None
            and 0 <= now - self._last_alt_tap_released_at <= self.alt_double_tap_interval
        ):
            self._last_alt_tap_released_at = None
            self._emit_main_window_summon()
            return

        self._last_alt_tap_released_at = now

    def _invalidate_alt_tap_sequence(self):
        self._alt_tap_invalidated = True
        self._last_alt_tap_released_at = None

    def _emit_main_window_summon(self):
        """Send the summon request across the configured GUI boundary."""
        now = self._monotonic_clock()
        with self._summon_emit_lock:
            if (
                self._last_summon_emitted_at is not None
                and now - self._last_summon_emitted_at < self._summon_emit_debounce
            ):
                return
            self._last_summon_emitted_at = now

        if self.event_sink:
            self.event_sink.request_main_window_summon()
        else:
            print("[WARN] 热键事件代理未设置，忽略主窗口唤出请求")

    def _report_hotkey_error(self, message: str):
        if self.event_sink:
            self.event_sink.report_hotkey_error(message)
        else:
            print(f"热键错误: {message}")
    
    def _check_hotkey_combination(self):
        """检查当前按键组合是否匹配热键"""
        current_time = self._monotonic_clock()
        
        # 防抖处理
        if current_time - self.last_hotkey_time < self.hotkey_debounce:
            return
        
        
        for hotkey_name, hotkey_info in self.hotkey_combinations.items():
            if self._is_hotkey_pressed(hotkey_info):
                # 记录热键触发时间
                self.last_hotkey_time = current_time
                
                print(f"🔑 热键触发: {hotkey_name} (防抖: {self.hotkey_debounce}s)")
                
                # 处理热键
                self._handle_hotkey(hotkey_name, hotkey_info)
                break  # 找到匹配的热键后立即退出
    
    def _is_hotkey_pressed(self, hotkey_info: Dict[str, Any]) -> bool:
        """检查指定热键是否被按下"""
        required_modifiers = hotkey_info["modifiers"]
        required_key = hotkey_info["key"]
        hotkey_type = hotkey_info.get("type", "task_switch")
        
        # 检查修饰键是否匹配
        modifiers_matched = self._check_modifiers(required_modifiers)
        if not modifiers_matched:
            return False
        
        # 检查目标键匹配
        return self._check_target_key(required_key, hotkey_type)
    
    def _check_modifiers(self, required_modifiers: set) -> bool:
        """检查修饰键是否匹配"""
        # 检查Ctrl键
        ctrl_required = Key.ctrl_l in required_modifiers or Key.ctrl_r in required_modifiers
        ctrl_pressed = Key.ctrl_l in self.pressed_keys or Key.ctrl_r in self.pressed_keys
        
        # 检查Alt键
        alt_required = Key.alt_l in required_modifiers or Key.alt_r in required_modifiers
        alt_pressed = any(key in self.pressed_keys for key in self.ALT_KEYS)
        
        # 检查Shift键
        shift_required = Key.shift_l in required_modifiers or Key.shift_r in required_modifiers
        shift_pressed = Key.shift_l in self.pressed_keys or Key.shift_r in self.pressed_keys
        
        # 检查Win键
        win_required = Key.cmd in required_modifiers
        win_pressed = Key.cmd in self.pressed_keys
        
        # 所有需要的修饰键必须被按下
        if ctrl_required and not ctrl_pressed:
            return False
        if alt_required and not alt_pressed:
            return False
        if shift_required and not shift_pressed:
            return False
        if win_required and not win_pressed:
            return False
        
        return True
    
    def _check_target_key(self, required_key, hotkey_type: str) -> bool:
        """检查目标键是否匹配"""
        # 处理空格键
        if required_key == Key.space:
            return Key.space in self.pressed_keys
        
        # 处理字符键（数字键等）
        if hasattr(required_key, 'char') and required_key.char:
            target_char = required_key.char
            target_ascii = ord(target_char)
            
            # 检查当前按下的键中是否有匹配的键
            for pressed_key in self.pressed_keys:
                # 方法1: 直接字符匹配
                if hasattr(pressed_key, 'char') and pressed_key.char == target_char:
                    return True
                # 方法2: ASCII码匹配 (处理 <49>, <50> 等情况)
                elif hasattr(pressed_key, 'vk') and pressed_key.vk == target_ascii:
                    return True
                # 方法3: 字符串表示匹配 (处理 KeyCode 对象)
                elif str(pressed_key) == str(required_key):
                    return True
        
        # 处理特殊键
        return required_key in self.pressed_keys
    
    def _handle_hotkey(self, hotkey_name: str, hotkey_info: Dict[str, Any]):
        """处理热键触发 - 使用线程安全的事件通信"""
        try:
            hotkey_type = hotkey_info.get("type", "switcher")
            
            if hotkey_type == "switcher":
                # 处理任务切换器热键
                print(f"✨ 任务切换器热键触发: {hotkey_name}")

                if self.event_sink:
                    self.event_sink.request_task_switcher(hotkey_name)
                    print("[OK] 热键事件已发送到主线程")
                else:
                    print("[WARN] 热键事件代理未设置，忽略任务切换请求")
            else:
                print(f"[WARN] 未知的热键类型: {hotkey_type}")
                
        except Exception as e:
            print(f"处理热键失败: {e}")
            self._report_hotkey_error(f"处理热键失败: {e}")
    
    def get_hotkey_status(self) -> Dict[str, Any]:
        """获取热键状态信息"""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "listener_active": self.listener.running if self.listener else False,
            "registered_hotkeys": len(self.hotkey_combinations),
            "hotkey_combinations": {
                name: {
                    "description": info["description"],
                    "task_index": info["task_index"]
                }
                for name, info in self.hotkey_combinations.items()
            },
            "pressed_keys": [str(key) for key in self.pressed_keys],
            "last_hotkey_time": self.last_hotkey_time,
            "debounce_interval": self.hotkey_debounce
        }
    
    def test_hotkey(self, task_index: int) -> bool:
        """测试指定任务的热键功能
        
        Args:
            task_index: 任务索引 (0-8)
            
        Returns:
            是否成功执行
        """
        try:
            if not (0 <= task_index < 9):
                print(f"无效的任务索引: {task_index}")
                return False
            
            print(f"测试切换到任务 {task_index + 1}")
            return self.task_manager.switch_to_task(task_index)
            
        except Exception as e:
            print(f"测试热键失败: {e}")
            return False
    
    def reload_config(self):
        """重新加载热键配置"""
        try:
            # 停止当前监听器
            was_running = self.running
            if was_running:
                self.stop()
            
            # 重新加载配置
            self.config = get_config()
            self.hotkey_config = self.config.get_hotkeys_config()
            self.enabled = self.hotkey_config.get("enabled", True)
            
            # 重新初始化热键组合
            self.hotkey_combinations.clear()
            self._initialize_hotkey_combinations()
            
            # 如果之前在运行，重新启动
            if was_running and self.enabled:
                self.start()
            
            print("[OK] 热键配置已重新加载")
            
        except Exception as e:
            print(f"重新加载热键配置失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            self.stop()
            self.hotkey_combinations.clear()
            self.pressed_keys.clear()
            self._active_alt_key = None
            self._alt_press_started_at = None
            self._alt_tap_invalidated = False
            self._last_alt_tap_released_at = None
            self._last_summon_emitted_at = None
            
            print("[OK] 热键管理器已清理")
            
        except Exception as e:
            print(f"清理热键管理器失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()
