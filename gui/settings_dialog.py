"""
设置对话框模块

负责应用程序设置界面:
- 待机提醒时间设置
- 快捷键修饰键设置
- 配置验证和保存
- 冲突检测和用户反馈
"""

from typing import List, Dict, Any, Optional
import traceback
import time

try:
    import FreeSimpleGUI as sg
    # 设置现代化主题
    sg.theme('DarkGrey13')
except ImportError:
    print("错误: 请先安装FreeSimpleGUI")
    raise

from core.task_manager import TaskManager
from gui.modern_config import ModernUIConfig
from utils.config import get_config
from utils.hotkey_conflict_detector import get_conflict_detector


class SettingsDialog:
    """设置对话框类"""
    
    def __init__(self, parent_window: sg.Window, task_manager: TaskManager):
        """初始化设置对话框
        
        Args:
            parent_window: 父窗口
            task_manager: 任务管理器
        """
        self.parent_window = parent_window
        self.task_manager = task_manager
        self.config = get_config()
        self.conflict_detector = get_conflict_detector()
        
        # 对话框窗口
        self.dialog_window: Optional[sg.Window] = None
        
        # 当前设置值
        self.idle_time_minutes = self.config.get_monitoring_config().get('idle_time_warning_minutes', 10)
        hotkey_config = self.config.get_hotkeys_config()
        self.switcher_enabled = hotkey_config.get('switcher_enabled', True)
        self.switcher_modifiers = hotkey_config.get('switcher_modifiers', ['ctrl', 'alt'])
        self.switcher_key = hotkey_config.get('switcher_key', 'space')
        
        # 原始设置备份（用于回滚）
        self.original_settings = {
            'idle_time_minutes': self.idle_time_minutes,
            'switcher_enabled': self.switcher_enabled,
            'switcher_modifiers': self.switcher_modifiers.copy(),
            'switcher_key': self.switcher_key
        }
        
        print("✓ 设置对话框初始化完成")
    
    def show_settings_dialog(self) -> bool:
        """显示设置对话框
        
        Returns:
            是否成功保存设置
        """
        # 创建对话框
        layout = self._create_settings_layout()
        
        # 获取图标路径
        icon_path = ModernUIConfig._get_icon_path()
        
        self.dialog_window = sg.Window(
            "应用设置",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=False,
            size=(480, 380),  # 调整为适中的高度
            location=(300, 150),
            no_titlebar=False,
            alpha_channel=0.98,
            background_color="#202020",
            margins=(15, 12),
            element_padding=(5, 4),
            icon=icon_path if icon_path else None
        )
        
        # 初始化界面状态
        self._update_interface()
        
        # 运行对话框
        try:
            result = self._run_dialog()
            return result
        finally:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None
    
    def _create_settings_layout(self) -> List[List[Any]]:
        """创建设置界面布局"""
        
        # 待机时间设置区域
        idle_time_frame = [
            [sg.Text("待机提醒时间:", font=("Segoe UI", 10), text_color="#FFFFFF")],
            [sg.Input(str(self.idle_time_minutes), key="-IDLE_TIME-", size=(8, 1), 
                     enable_events=True),
             sg.Text("分钟", font=("Segoe UI", 9)),
             sg.Text("(范围: 1-1440分钟)", font=("Segoe UI", 8), text_color="#888888")],
            [sg.Text("快速选择:", font=("Segoe UI", 9)),
             sg.Button("5", key="-QUICK_5-", size=(3, 1)),
             sg.Button("15", key="-QUICK_15-", size=(3, 1)),
             sg.Button("30", key="-QUICK_30-", size=(3, 1)),
             sg.Button("60", key="-QUICK_60-", size=(3, 1))]
        ]
        
        # 任务切换器设置区域
        switcher_frame = [
            [sg.Checkbox("启用任务切换器", key="-SWITCHER_ENABLED-", 
                        default=self.switcher_enabled, enable_events=True,
                        font=("Segoe UI", 10), text_color="#FFFFFF")],
            [sg.Text("切换器热键修饰键:", font=("Segoe UI", 10), text_color="#FFFFFF")],
            [sg.Checkbox("Ctrl", key="-CTRL-", default="ctrl" in self.switcher_modifiers, 
                        enable_events=True, font=("Segoe UI", 9)),
             sg.Checkbox("Alt", key="-ALT-", default="alt" in self.switcher_modifiers, 
                        enable_events=True, font=("Segoe UI", 9)),
             sg.Checkbox("Shift", key="-SHIFT-", default="shift" in self.switcher_modifiers, 
                        enable_events=True, font=("Segoe UI", 9)),
             sg.Checkbox("Win", key="-WIN-", default="win" in self.switcher_modifiers, 
                        enable_events=True, font=("Segoe UI", 9))],
            [sg.Text("触发键:", font=("Segoe UI", 9)),
             sg.Combo(["space", "tab", "enter"], default_value=self.switcher_key,
                     key="-SWITCHER_KEY-", enable_events=True, readonly=True,
                     font=("Segoe UI", 9), size=(8, 1))],
            [sg.Text("当前组合: ", font=("Segoe UI", 9)),
             sg.Text(self._format_switcher_preview(), key="-HOTKEY_PREVIEW-", 
                    font=("Segoe UI", 9), text_color="#0078D4")],
            [sg.Text("状态: ", font=("Segoe UI", 9)),
             sg.Text("✅ 无冲突", key="-CONFLICT_STATUS-", 
                    font=("Segoe UI", 9), text_color="#107C10")]
        ]
        
        # 按钮区域
        button_row = [
            sg.Push(),
            sg.Button("确定", key="-OK-", size=(8, 1), 
                     button_color=("#FFFFFF", "#107C10"), 
                     font=("Segoe UI", 10), border_width=0),
            sg.Button("取消", key="-CANCEL-", size=(8, 1),
                     button_color=("#FFFFFF", "#404040"), 
                     font=("Segoe UI", 10), border_width=0),
            sg.Button("恢复默认", key="-DEFAULTS-", size=(8, 1),
                     button_color=("#FFFFFF", "#FF8C00"), 
                     font=("Segoe UI", 10), border_width=0),
            sg.Push()
        ]
        
        # 完整布局（移除重复的标题）
        layout = [
            # 待机时间设置
            [sg.Text("通知设置", font=("Segoe UI", 10, "bold"), text_color="#CCCCCC")],
            *idle_time_frame,
            [sg.Text("")],  # 间隔
            
            # 任务切换器设置
            [sg.Text("任务切换器设置", font=("Segoe UI", 10, "bold"), text_color="#CCCCCC")],
            *switcher_frame,
            [sg.Text("")],  # 间隔
            
            [sg.HorizontalSeparator()],
            button_row
        ]
        
        return layout
    
    def _run_dialog(self) -> bool:
        """运行对话框事件循环
        
        Returns:
            用户是否确认保存设置
        """
        if not self.dialog_window:
            return False
        
        try:
            while True:
                event, values = self.dialog_window.read()
                
                if event in (sg.WIN_CLOSED, "-CANCEL-"):
                    return False
                
                elif event == "-OK-":
                    if self._validate_and_save_settings(values):
                        return True
                
                elif event == "-DEFAULTS-":
                    self._restore_defaults()
                
                elif event in ["-QUICK_5-", "-QUICK_15-", "-QUICK_30-", "-QUICK_60-"]:
                    self._handle_quick_time_select(event)
                
                elif event in ["-CTRL-", "-ALT-", "-SHIFT-", "-WIN-", "-IDLE_TIME-", 
                              "-SWITCHER_ENABLED-", "-SWITCHER_KEY-"]:
                    self._handle_setting_change(values)
        
        except Exception as e:
            print(f"设置对话框运行错误: {e}")
            traceback.print_exc()
            return False
    
    def _handle_quick_time_select(self, event: str):
        """处理快速时间选择"""
        time_map = {
            "-QUICK_5-": "5",
            "-QUICK_15-": "15", 
            "-QUICK_30-": "30",
            "-QUICK_60-": "60"
        }
        
        if event in time_map:
            self.dialog_window["-IDLE_TIME-"].update(time_map[event])
            self._update_interface()
    
    def _handle_setting_change(self, values: Dict[str, Any]):
        """处理设置变更"""
        # 更新界面显示
        self._update_interface(values)
    
    def _update_interface(self, values: Optional[Dict[str, Any]] = None):
        """更新界面显示"""
        if not self.dialog_window:
            return
        
        try:
            # 获取当前值
            if values:
                # 从界面获取当前设置
                current_modifiers = []
                if values.get("-CTRL-", False):
                    current_modifiers.append("ctrl")
                if values.get("-ALT-", False):
                    current_modifiers.append("alt")
                if values.get("-SHIFT-", False):
                    current_modifiers.append("shift")
                if values.get("-WIN-", False):
                    current_modifiers.append("win")
            else:
                # 使用初始设置
                current_modifiers = self.switcher_modifiers
            
            # 更新快捷键预览
            current_key = self.dialog_window["-SWITCHER_KEY-"].get() if self.dialog_window else self.switcher_key
            preview_text = self._format_switcher_preview(current_modifiers, current_key)
            self.dialog_window["-HOTKEY_PREVIEW-"].update(preview_text)
            
            # 检查冲突
            conflict_status, conflict_color = self._check_conflicts(current_modifiers)
            self.dialog_window["-CONFLICT_STATUS-"].update(conflict_status, text_color=conflict_color)
            
        except Exception as e:
            print(f"更新界面显示失败: {e}")
    
    def _format_switcher_preview(self, modifiers: Optional[List[str]] = None, key: Optional[str] = None) -> str:
        """格式化切换器热键预览文本"""
        if modifiers is None:
            modifiers = self.switcher_modifiers
        if key is None:
            key = self.switcher_key
        
        if not modifiers or not key:
            return "未设置"
        
        # 格式化修饰键
        formatted_mods = []
        for mod in modifiers:
            if mod == "ctrl":
                formatted_mods.append("Ctrl")
            elif mod == "alt":
                formatted_mods.append("Alt")
            elif mod == "shift":
                formatted_mods.append("Shift")
            elif mod == "win":
                formatted_mods.append("Win")
        
        # 格式化触发键
        formatted_key = key.title() if key else "?"
        
        if formatted_mods and formatted_key:
            return "+".join(formatted_mods) + "+" + formatted_key
        else:
            return "未设置"
    
    def _check_conflicts(self, modifiers: List[str]) -> tuple:
        """检查快捷键冲突
        
        Returns:
            (状态文本, 颜色)
        """
        if not modifiers:
            return "❌ 至少需要一个修饰键", "#D13438"
        
        # 使用冲突检测器进行检查
        conflict_result = self.conflict_detector.check_hotkey_conflicts(modifiers)
        
        if conflict_result['severity'] == 'error':
            # 严重冲突（系统保留）
            return "❌ 系统冲突，无法使用", "#D13438"
        elif conflict_result['severity'] == 'warning':
            # 警告级冲突（应用冲突）
            conflict_count = len(conflict_result['conflicts'])
            return f"⚠️ 发现{conflict_count}个潜在冲突", "#FF8C00"
        elif conflict_result['warnings']:
            # 使用性警告
            return f"⚠️ {conflict_result['warnings'][0]}", "#FF8C00"
        else:
            # 无冲突
            return "✅ 无冲突", "#107C10"
    
    def _validate_and_save_settings(self, values: Dict[str, Any]) -> bool:
        """验证并保存设置"""
        try:
            # 验证待机时间
            try:
                idle_time = int(values["-IDLE_TIME-"])
                if not (1 <= idle_time <= 1440):
                    sg.popup("待机提醒时间必须在1-1440分钟范围内", title="设置错误")
                    return False
            except ValueError:
                sg.popup("请输入有效的数字", title="设置错误")
                return False
            
            # 验证任务切换器设置
            switcher_enabled = values.get("-SWITCHER_ENABLED-", True)
            switcher_key = values.get("-SWITCHER_KEY-", "space")
            
            modifiers = []
            if values.get("-CTRL-", False):
                modifiers.append("ctrl")
            if values.get("-ALT-", False):
                modifiers.append("alt")
            if values.get("-SHIFT-", False):
                modifiers.append("shift")
            if values.get("-WIN-", False):
                modifiers.append("win")
            
            if switcher_enabled and not modifiers:
                sg.popup("启用任务切换器时，至少需要选择一个修饰键", title="设置错误")
                return False
            
            # 如果启用切换器，进行冲突检测
            if switcher_enabled and modifiers:
                conflict_result = self.conflict_detector.check_hotkey_conflicts(modifiers)
                
                if conflict_result['severity'] == 'error':
                    # 严重冲突，不允许保存
                    conflicts_text = '\n'.join(conflict_result['conflicts'])
                    sg.popup(f"检测到严重冲突，无法保存:\n\n{conflicts_text}", title="快捷键冲突")
                    return False
                elif conflict_result['severity'] == 'warning':
                    # 警告级冲突，询问用户是否继续
                    conflicts_text = '\n'.join(conflict_result['conflicts'])
                    suggestions_text = '\n'.join(conflict_result['suggestions'][:2])
                    
                    result = sg.popup_yes_no(
                        f"检测到潜在冲突:\n\n{conflicts_text}\n\n建议:\n{suggestions_text}\n\n是否继续保存此设置?",
                        title="快捷键冲突警告"
                    )
                    if result != "Yes":
                        return False
            
            # 保存设置
            return self._apply_new_settings(idle_time, switcher_enabled, modifiers, switcher_key)
            
        except Exception as e:
            print(f"验证设置失败: {e}")
            sg.popup(f"保存设置失败: {e}", title="错误")
            return False
    
    def _apply_new_settings(self, idle_time: int, switcher_enabled: bool, 
                          modifiers: List[str], switcher_key: str) -> bool:
        """应用新设置"""
        try:
            switcher_combo = '+'.join(modifiers) + '+' + switcher_key if modifiers else "未设置"
            print(f"🔧 应用新设置: 待机时间={idle_time}分钟, 切换器={switcher_enabled}, 热键={switcher_combo}")
            
            # 创建配置备份
            backup_success = self._create_settings_backup()
            if not backup_success:
                sg.popup("无法创建配置备份，操作取消", title="错误")
                return False
            
            # 更新配置
            monitoring_config = self.config.get_monitoring_config()
            monitoring_config['idle_time_warning_minutes'] = idle_time
            
            hotkeys_config = self.config.get_hotkeys_config()
            hotkeys_config['switcher_enabled'] = switcher_enabled
            hotkeys_config['switcher_modifiers'] = modifiers
            hotkeys_config['switcher_key'] = switcher_key
            
            # 保存配置文件
            self.config.save()
            
            # 重载相关系统组件
            self._reload_system_components()
            
            print("✅ 设置保存成功")
            return True
            
        except Exception as e:
            print(f"❌ 应用设置失败: {e}")
            # 尝试回滚
            self._restore_settings_backup()
            sg.popup(f"设置保存失败，已恢复原设置: {e}", title="错误")
            return False
    
    def _create_settings_backup(self) -> bool:
        """创建设置备份"""
        try:
            import json
            from pathlib import Path
            
            # 获取配置目录
            config_dir = self.config.get_data_dir()
            backup_path = config_dir / "config.backup.json"
            
            # 读取当前配置
            current_config = {
                'monitoring': self.config.get_monitoring_config().copy(),
                'hotkeys': self.config.get_hotkeys_config().copy(),
                'backup_timestamp': time.time()
            }
            
            # 保存备份文件
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(current_config, f, indent=4, ensure_ascii=False)
            
            print(f"✅ 配置备份已创建: {backup_path}")
            return True
            
        except Exception as e:
            print(f"❌ 创建备份失败: {e}")
            return False
    
    def _restore_settings_backup(self):
        """恢复设置备份"""
        try:
            import json
            from pathlib import Path
            
            # 获取备份文件路径
            config_dir = self.config.get_data_dir()
            backup_path = config_dir / "config.backup.json"
            
            if backup_path.exists():
                # 从备份文件恢复
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_config = json.load(f)
                
                # 恢复监控配置
                monitoring_config = self.config.get_monitoring_config()
                monitoring_config.update(backup_config['monitoring'])
                
                # 恢复快捷键配置
                hotkeys_config = self.config.get_hotkeys_config()
                hotkeys_config.update(backup_config['hotkeys'])
                
                print("✅ 从备份文件恢复设置")
            else:
                # 使用内存中的原始设置
                monitoring_config = self.config.get_monitoring_config()
                monitoring_config['idle_time_warning_minutes'] = self.original_settings['idle_time_minutes']
                
                hotkeys_config = self.config.get_hotkeys_config()
                hotkeys_config['modifiers'] = self.original_settings['hotkey_modifiers']
                
                print("✅ 从内存恢复原始设置")
            
            # 保存恢复的配置
            self.config.save()
            self._reload_system_components()
            
            print("✅ 设置已成功回滚")
            
        except Exception as e:
            print(f"❌ 恢复备份失败: {e}")
            # 最后的备用方案：使用内存中的原始设置
            try:
                monitoring_config = self.config.get_monitoring_config()
                monitoring_config['idle_time_warning_minutes'] = self.original_settings['idle_time_minutes']
                
                hotkeys_config = self.config.get_hotkeys_config()
                hotkeys_config['modifiers'] = self.original_settings['hotkey_modifiers']
                
                self.config.save()
                print("✅ 使用内存备份恢复设置")
            except Exception as fallback_error:
                print(f"❌ 最后备用恢复也失败: {fallback_error}")
    
    def _reload_system_components(self):
        """重载系统组件"""
        try:
            # 重载热键管理器
            hotkey_manager = None
            
            # 尝试从任务管理器获取热键管理器
            if hasattr(self.task_manager, 'hotkey_manager'):
                hotkey_manager = self.task_manager.hotkey_manager
            
            # 如果任务管理器没有，尝试从主程序获取
            if not hotkey_manager:
                try:
                    import main
                    if hasattr(main, 'hotkey_manager'):
                        hotkey_manager = main.hotkey_manager
                except:
                    pass
            
            # 重载热键配置
            if hotkey_manager:
                hotkey_manager.reload_config()
                print("✓ 热键管理器已重载")
            else:
                print("⚠️ 未找到热键管理器，跳过重载")
            
            # 重载监控系统相关的组件
            # 待机时间监控会在下次检查时自动使用新配置
            print("✓ 监控系统将在下次检查时使用新配置")
            
            # 可以添加其他需要重载的组件
            
        except Exception as e:
            print(f"⚠️ 重载系统组件时出错: {e}")
            # 不抛出异常，因为配置已经保存，组件重载失败不应该影响设置保存
    
    def _restore_defaults(self):
        """恢复默认设置"""
        try:
            # 恢复默认值
            self.dialog_window["-IDLE_TIME-"].update("10")
            self.dialog_window["-SWITCHER_ENABLED-"].update(True)
            self.dialog_window["-CTRL-"].update(True)
            self.dialog_window["-ALT-"].update(True)
            self.dialog_window["-SHIFT-"].update(False)
            self.dialog_window["-WIN-"].update(False)
            self.dialog_window["-SWITCHER_KEY-"].update("space")
            
            # 更新界面
            self._update_interface({
                "-SWITCHER_ENABLED-": True,
                "-CTRL-": True,
                "-ALT-": True,
                "-SHIFT-": False,
                "-WIN-": False,
                "-SWITCHER_KEY-": "space"
            })
            
            print("🔄 已恢复默认设置")
            
        except Exception as e:
            print(f"恢复默认设置失败: {e}")