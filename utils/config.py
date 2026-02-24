"""
配置管理模块

负责管理应用程序的配置信息，包括:
- 热键配置
- 窗口位置和大小
- 用户偏好设置
- 应用程序设置
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """配置管理器"""
    
    def __init__(self):
        self.app_name = "ContextSwitcher"
        self.config_file = "config.json"
        self.config_dir = self._get_config_dir()
        self.config_path = self.config_dir / self.config_file
        
        # 默认配置
        self.default_config = {
            "app": {
                "version": "1.0.0",
                "theme": "DefaultNoMoreNagging",
                "language": "zh_CN",
                "first_run": True,  # 首次运行标记
                "use_qt": True  # UI后端：True=PySide6, False=FreeSimpleGUI
            },
            "window": {
                "width": 600,
                "height": 400,
                "x": 100,
                "y": 100,
                "always_on_top": True,
                "remember_position": True
            },
            "hotkeys": {
                "switcher_enabled": True,
                "switcher_modifiers": ["ctrl", "alt"],
                "switcher_key": "space"
            },
            "data": {
                "auto_save": True,
                "backup_count": 3,
                "save_interval": 300  # 秒
            },
            "features": {
                "virtual_desktop": False,  # 实验性功能默认关闭
                "system_tray": False,
                "startup_with_windows": False
            },
            "integrations": {
                "wave": {
                    "exe_path": ""  # Wave.exe 路径（用于切换 workspace）
                }
            },
            "monitoring": {
                "idle_time_warning_minutes": 10,  # 待机时间警告阈值（分钟）
                "toast_notifications_enabled": True,  # 启用Toast通知
                "toast_cooldown_minutes": 30,  # Toast通知冷却时间（分钟）
                "check_interval_seconds": 60,  # 检查间隔（秒）
                "show_idle_time_column": True  # 显示待机时间列
            },
            "task_switcher": {
                "enabled": True,
                "window_size": [800, 700],
                "auto_close_delay": 2.0,
                "show_hotkey_hints": True,
                "show_empty_slots": True
            },
            "productivity": {
                "daily_goal_minutes": 120,  # 每日专注目标（分钟），默认2小时
                "show_goal_progress": True,  # 显示目标进度
                "goal_reminder_enabled": True,  # 启用目标达成提醒
                "weekly_goal_hours": 20  # 每周专注目标（小时）
            }
        }
        
        self.config = self._load_config()
    
    def _get_config_dir(self) -> Path:
        """获取配置文件目录

        使用固定的用户目录存储数据，确保数据持久性。
        无论exe放在哪里，数据都保存在固定位置，避免打包后数据丢失。

        Windows: %APPDATA%\ContextSwitcher
        Linux/Mac: ~/.contextswitcher
        """
        return self._get_user_config_dir()

    def _get_user_config_dir(self) -> Path:
        """获取用户配置目录（固定位置）"""
        if os.name == 'nt':
            # Windows: %APPDATA%\ContextSwitcher
            appdata = os.environ.get('APPDATA', '')
            if appdata:
                config_dir = Path(appdata) / self.app_name
            else:
                config_dir = Path.home() / f'.{self.app_name}'
        else:
            # Linux/Mac: ~/.contextswitcher
            config_dir = Path.home() / f'.{self.app_name.lower()}'

        # 确保目录存在
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"使用数据目录: {config_dir}")
        return config_dir

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 合并默认配置和加载的配置
                config = self._merge_config(self.default_config.copy(), loaded_config)
                return config
            else:
                # 配置文件不存在，使用默认配置并保存
                self._save_config(self.default_config)
                return self.default_config.copy()
                
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return self.default_config.copy()
    
    def _merge_config(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置，确保所有默认键都存在"""
        for key, value in default.items():
            if key in loaded:
                if isinstance(value, dict) and isinstance(loaded[key], dict):
                    default[key] = self._merge_config(value, loaded[key])
                else:
                    default[key] = loaded[key]
        return default
    
    def _save_config(self, config: Dict[str, Any] = None) -> bool:
        """保存配置到文件"""
        try:
            config_to_save = config or self.config
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key_path: 配置键路径，如 'window.width'
            default: 默认值
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> bool:
        """设置配置值
        
        Args:
            key_path: 配置键路径，如 'window.width'
            value: 要设置的值
        """
        keys = key_path.split('.')
        config = self.config
        
        try:
            # 遍历到最后一级
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # 设置值
            config[keys[-1]] = value
            
            # 保存配置
            return self._save_config()
            
        except Exception as e:
            print(f"设置配置值失败: {e}")
            return False
    
    def save(self) -> bool:
        """保存当前配置"""
        return self._save_config()
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        self.config = self.default_config.copy()
        return self._save_config()
    
    def get_data_dir(self) -> Path:
        """获取数据文件目录"""
        return self.config_dir
    
    def get_hotkeys_config(self) -> Dict[str, Any]:
        """获取热键配置"""
        return self.get('hotkeys', {})
    
    def get_window_config(self) -> Dict[str, Any]:
        """获取窗口配置"""
        return self.get('window', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self.get('monitoring', {})
    
    def get_productivity_config(self) -> Dict[str, Any]:
        """获取生产力配置"""
        return self.config.get("productivity", self.default_config["productivity"])

    def get_task_switcher_config(self) -> Dict[str, Any]:
        """获取任务切换器配置"""
        return self.get('task_switcher', {})
    
    def update_window_position(self, x: int, y: int, width: int, height: int) -> bool:
        """更新窗口位置和大小"""
        if not self.get('window.remember_position', True):
            return True
        
        success = True
        success &= self.set('window.x', x)
        success &= self.set('window.y', y)
        success &= self.set('window.width', width)
        success &= self.set('window.height', height)
        
        return success


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取全局配置实例"""
    return config
