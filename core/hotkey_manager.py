"""
全局热键管理模块

负责注册和处理全局热键:
- Ctrl+Alt+1-9 热键注册
- 热键事件处理
- 热键冲突检测
- 热键生命周期管理
"""

import threading
import time
from typing import Dict, List, Callable, Optional, Any

try:
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode, Listener
except ImportError:
    print("错误: 请先安装pynput库")
    print("运行: pip install pynput")
    raise

from core.task_manager import TaskManager
from utils.config import get_config


class HotkeyManager:
    """全局热键管理器"""
    
    def __init__(self, task_manager: TaskManager):
        """初始化热键管理器
        
        Args:
            task_manager: 任务管理器实例
        """
        self.task_manager = task_manager
        self.config = get_config()
        
        # 热键配置
        self.hotkey_config = self.config.get_hotkeys_config()
        self.enabled = self.hotkey_config.get("enabled", True)
        
        # 热键监听器
        self.listener: Optional[Listener] = None
        self.running = False
        
        # 热键状态跟踪
        self.pressed_keys = set()
        self.hotkey_combinations = {}
        self.last_hotkey_time = 0
        self.hotkey_debounce = 0.2  # 防抖间隔（秒）
        
        # 回调函数
        self.on_hotkey_pressed: Optional[Callable[[str, int], None]] = None
        self.on_hotkey_error: Optional[Callable[[str], None]] = None
        
        # 初始化热键组合
        self._initialize_hotkey_combinations()
        
        print("✓ 热键管理器初始化完成")
    
    def _initialize_hotkey_combinations(self):
        """初始化热键组合"""
        # 从配置读取修饰键和数字键
        modifiers = self.hotkey_config.get("modifiers", ["ctrl", "alt"])
        keys = self.hotkey_config.get("keys", ["1", "2", "3", "4", "5", "6", "7", "8", "9"])
        
        # 转换修饰键
        modifier_keys = set()
        for mod in modifiers:
            if mod.lower() == "ctrl":
                modifier_keys.add(Key.ctrl_l)
                modifier_keys.add(Key.ctrl_r)
            elif mod.lower() == "alt":
                modifier_keys.add(Key.alt_l)
                modifier_keys.add(Key.alt_r)
            elif mod.lower() == "shift":
                modifier_keys.add(Key.shift_l)
                modifier_keys.add(Key.shift_r)
            elif mod.lower() == "win":
                modifier_keys.add(Key.cmd)
        
        # 创建热键组合
        for i, key in enumerate(keys):
            if i >= 9:  # 最多支持9个热键
                break
            
            # 创建热键组合描述
            hotkey_name = "+".join(modifiers + [key])
            
            self.hotkey_combinations[hotkey_name] = {
                "modifiers": modifier_keys.copy(),
                "key": KeyCode.from_char(key),
                "task_index": i,
                "description": f"切换到任务 {i+1}"
            }
        
        print(f"✓ 已配置 {len(self.hotkey_combinations)} 个热键组合")
    
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
            self.listener = Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            
            # 启动监听器
            self.listener.start()
            self.running = True
            
            print("✓ 热键监听器已启动")
            
            # 显示注册的热键
            for hotkey_name, hotkey_info in self.hotkey_combinations.items():
                print(f"  {hotkey_name}: {hotkey_info['description']}")
            
            return True
            
        except Exception as e:
            print(f"启动热键监听器失败: {e}")
            if self.on_hotkey_error:
                self.on_hotkey_error(f"启动失败: {e}")
            return False
    
    def stop(self):
        """停止热键监听"""
        if not self.running:
            return
        
        self.running = False
        
        if self.listener:
            try:
                self.listener.stop()
                self.listener = None
                print("✓ 热键监听器已停止")
            except Exception as e:
                print(f"停止热键监听器时出错: {e}")
        
        # 清除按键状态
        self.pressed_keys.clear()
    
    def is_running(self) -> bool:
        """检查热键监听器是否运行"""
        return self.running and self.listener and self.listener.running
    
    def _on_key_press(self, key):
        """按键按下事件处理"""
        if not self.running:
            return
        
        try:
            # 添加到按下的按键集合
            self.pressed_keys.add(key)
            
            # 检查是否匹配热键组合
            self._check_hotkey_combination()
            
        except Exception as e:
            print(f"处理按键按下事件失败: {e}")
    
    def _on_key_release(self, key):
        """按键释放事件处理"""
        if not self.running:
            return
        
        try:
            # 从按下的按键集合中移除
            self.pressed_keys.discard(key)
            
        except Exception as e:
            print(f"处理按键释放事件失败: {e}")
    
    def _check_hotkey_combination(self):
        """检查当前按键组合是否匹配热键"""
        current_time = time.time()
        
        # 防抖处理
        if current_time - self.last_hotkey_time < self.hotkey_debounce:
            return
        
        for hotkey_name, hotkey_info in self.hotkey_combinations.items():
            if self._is_hotkey_pressed(hotkey_info):
                # 记录热键触发时间
                self.last_hotkey_time = current_time
                
                # 处理热键
                self._handle_hotkey(hotkey_name, hotkey_info)
                break
    
    def _is_hotkey_pressed(self, hotkey_info: Dict[str, Any]) -> bool:
        """检查指定热键是否被按下"""
        required_modifiers = hotkey_info["modifiers"]
        required_key = hotkey_info["key"]
        
        # 检查修饰键
        modifier_pressed = False
        for modifier in required_modifiers:
            if modifier in self.pressed_keys:
                modifier_pressed = True
                break
        
        if not modifier_pressed:
            return False
        
        # 检查目标键
        if required_key not in self.pressed_keys:
            return False
        
        # 确保没有按下额外的修饰键
        extra_modifiers = {Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r, 
                          Key.shift_l, Key.shift_r, Key.cmd} - required_modifiers
        
        for extra_mod in extra_modifiers:
            if extra_mod in self.pressed_keys:
                return False
        
        return True
    
    def _handle_hotkey(self, hotkey_name: str, hotkey_info: Dict[str, Any]):
        """处理热键触发"""
        try:
            task_index = hotkey_info["task_index"]
            
            print(f"热键触发: {hotkey_name} -> 任务 {task_index + 1}")
            
            # 切换到指定任务
            success = self.task_manager.switch_to_task(task_index)
            
            if not success:
                print(f"切换到任务 {task_index + 1} 失败")
            
            # 触发回调
            if self.on_hotkey_pressed:
                self.on_hotkey_pressed(hotkey_name, task_index)
                
        except Exception as e:
            print(f"处理热键失败: {e}")
            if self.on_hotkey_error:
                self.on_hotkey_error(f"处理热键失败: {e}")
    
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
            
            print("✓ 热键配置已重新加载")
            
        except Exception as e:
            print(f"重新加载热键配置失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            self.stop()
            self.hotkey_combinations.clear()
            self.pressed_keys.clear()
            
            print("✓ 热键管理器已清理")
            
        except Exception as e:
            print(f"清理热键管理器失败: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()