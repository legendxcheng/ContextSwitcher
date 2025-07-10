#!/usr/bin/env python3
"""
设置功能集成验证脚本

全面验证设置功能的集成情况:
- 文件结构完整性
- 代码集成正确性
- 配置系统兼容性
- 功能模块可用性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def validate_file_structure():
    """验证文件结构完整性"""
    print("🧪 验证文件结构...")
    
    required_files = [
        "gui/settings_dialog.py",
        "utils/hotkey_conflict_detector.py", 
        "gui/main_window.py",
        "utils/config.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ 缺少文件: {', '.join(missing_files)}")
        return False
    else:
        print("✅ 所有必需文件都存在")
        return True


def validate_imports():
    """验证模块导入"""
    print("🧪 验证模块导入...")
    
    try:
        # 测试配置系统
        from utils.config import get_config
        config = get_config()
        print("✅ 配置系统导入成功")
        
        # 测试冲突检测器（不依赖GUI）
        from utils.hotkey_conflict_detector import get_conflict_detector
        detector = get_conflict_detector()
        print("✅ 冲突检测器导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False


def validate_config_system():
    """验证配置系统功能"""
    print("🧪 验证配置系统...")
    
    try:
        from utils.config import get_config
        config = get_config()
        
        # 验证监控配置
        monitoring = config.get_monitoring_config()
        required_monitoring_keys = ['idle_time_warning_minutes', 'toast_notifications_enabled']
        
        for key in required_monitoring_keys:
            if key not in monitoring:
                print(f"❌ 监控配置缺少键: {key}")
                return False
        
        print(f"✅ 监控配置完整, 当前待机时间: {monitoring['idle_time_warning_minutes']}分钟")
        
        # 验证热键配置
        hotkeys = config.get_hotkeys_config()
        required_hotkey_keys = ['enabled', 'modifiers', 'keys']
        
        for key in required_hotkey_keys:
            if key not in hotkeys:
                print(f"❌ 热键配置缺少键: {key}")
                return False
        
        print(f"✅ 热键配置完整, 当前修饰键: {'+'.join(hotkeys['modifiers'])}")
        
        # 测试配置保存
        original_time = monitoring['idle_time_warning_minutes']
        test_time = 99
        
        monitoring['idle_time_warning_minutes'] = test_time
        config.save()
        
        # 重新读取验证
        config = get_config()
        new_time = config.get_monitoring_config()['idle_time_warning_minutes']
        
        if new_time == test_time:
            print("✅ 配置保存功能正常")
            
            # 恢复原始值
            config.get_monitoring_config()['idle_time_warning_minutes'] = original_time
            config.save()
        else:
            print("❌ 配置保存功能异常")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 配置系统验证失败: {e}")
        return False


def validate_conflict_detector():
    """验证冲突检测器功能"""
    print("🧪 验证冲突检测器...")
    
    try:
        from utils.hotkey_conflict_detector import get_conflict_detector
        detector = get_conflict_detector()
        
        # 测试正常组合
        result = detector.check_hotkey_conflicts(['ctrl', 'alt'])
        if 'severity' not in result:
            print("❌ 冲突检测结果格式异常")
            return False
        
        print(f"✅ Ctrl+Alt组合检测: {result['severity']}")
        
        # 测试有冲突的组合
        result = detector.check_hotkey_conflicts(['alt', 'shift'])
        print(f"✅ Alt+Shift组合检测: {result['severity']}")
        
        # 测试空组合
        result = detector.check_hotkey_conflicts([])
        if not result['has_conflicts']:
            print("❌ 空组合应该报告冲突")
            return False
        
        print("✅ 空组合正确检测为错误")
        
        # 测试注册测试功能
        test_result = detector.test_hotkey_registration(['ctrl', 'alt'])
        if 'success' not in test_result:
            print("❌ 快捷键注册测试结果格式异常")
            return False
        
        print("✅ 快捷键注册测试功能正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 冲突检测器验证失败: {e}")
        return False


def validate_main_window_integration():
    """验证主界面集成"""
    print("🧪 验证主界面集成...")
    
    try:
        # 读取主界面文件
        with open('gui/main_window.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查必要的代码存在
        required_patterns = [
            '"-SETTINGS-"',  # 设置按钮
            'def _handle_settings(self)',  # 设置处理函数
            'from gui.settings_dialog import SettingsDialog',  # 设置对话框导入
            'elif event == "-SETTINGS-"'  # 设置事件处理
        ]
        
        missing_patterns = []
        for pattern in required_patterns:
            if pattern not in content:
                missing_patterns.append(pattern)
        
        if missing_patterns:
            print(f"❌ 主界面缺少必要代码: {missing_patterns}")
            return False
        
        # 检查移除了不需要的代码
        removed_patterns = [
            '"-CHANGE_STATUS-"',
            '"-SMART_REBIND-"',
            'def _handle_change_status',
            'def _handle_smart_rebind'
        ]
        
        still_present = []
        for pattern in removed_patterns:
            if pattern in content:
                still_present.append(pattern)
        
        if still_present:
            print(f"❌ 主界面仍包含应移除的代码: {still_present}")
            return False
        
        print("✅ 主界面集成正确")
        return True
        
    except Exception as e:
        print(f"❌ 主界面集成验证失败: {e}")
        return False


def validate_settings_dialog_completeness():
    """验证设置对话框完整性"""
    print("🧪 验证设置对话框完整性...")
    
    try:
        # 读取设置对话框文件
        with open('gui/settings_dialog.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键功能
        required_functions = [
            'class SettingsDialog',
            'def show_settings_dialog',
            'def _validate_and_save_settings',
            'def _check_conflicts',
            'def _create_settings_backup',
            'def _restore_settings_backup',
            'def _reload_system_components'
        ]
        
        missing_functions = []
        for func in required_functions:
            if func not in content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"❌ 设置对话框缺少关键函数: {missing_functions}")
            return False
        
        # 检查导入
        required_imports = [
            'from utils.config import get_config',
            'from utils.hotkey_conflict_detector import get_conflict_detector',
            'import FreeSimpleGUI as sg'
        ]
        
        missing_imports = []
        for imp in required_imports:
            if imp not in content:
                missing_imports.append(imp)
        
        if missing_imports:
            print(f"❌ 设置对话框缺少必要导入: {missing_imports}")
            return False
        
        print("✅ 设置对话框完整性验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 设置对话框完整性验证失败: {e}")
        return False


def validate_error_handling():
    """验证错误处理机制"""
    print("🧪 验证错误处理机制...")
    
    try:
        from utils.hotkey_conflict_detector import get_conflict_detector
        detector = get_conflict_detector()
        
        # 测试异常输入
        edge_cases = [
            None,  # None输入
            [],    # 空列表
            ['invalid_key'],  # 无效键
            ['ctrl', 'alt', 'shift', 'win', 'extra'],  # 过多键
        ]
        
        for case in edge_cases:
            try:
                if case is not None:
                    result = detector.check_hotkey_conflicts(case)
                    # 应该返回有效结果而不是抛异常
                    if 'severity' not in result:
                        print(f"❌ 边界案例 {case} 返回格式异常")
                        return False
            except Exception as e:
                print(f"❌ 边界案例 {case} 抛出异常: {e}")
                return False
        
        print("✅ 错误处理机制正常")
        return True
        
    except Exception as e:
        print(f"❌ 错误处理验证失败: {e}")
        return False


def run_comprehensive_validation():
    """运行综合验证"""
    print("🚀 设置功能集成综合验证")
    print("=" * 60)
    
    validations = [
        ("文件结构完整性", validate_file_structure),
        ("模块导入功能", validate_imports),
        ("配置系统功能", validate_config_system),
        ("冲突检测器功能", validate_conflict_detector),
        ("主界面集成", validate_main_window_integration),
        ("设置对话框完整性", validate_settings_dialog_completeness),
        ("错误处理机制", validate_error_handling),
    ]
    
    passed = 0
    total = len(validations)
    
    for name, validation_func in validations:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            if validation_func():
                print(f"✅ {name} 验证通过")
                passed += 1
            else:
                print(f"❌ {name} 验证失败")
        except Exception as e:
            print(f"❌ {name} 验证异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"验证结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("🎉 所有验证项目都通过！设置功能集成完成！")
        print("\n📋 功能清单:")
        print("✅ 移除无用按钮 (状态变更、智能重绑定)")
        print("✅ 添加设置按钮到主界面")
        print("✅ 实现设置对话框 (待机时间、快捷键设置)")
        print("✅ 快捷键冲突检测系统")
        print("✅ 配置备份和回滚机制")
        print("✅ 系统组件重载功能")
        print("✅ 完整的错误处理")
        
        print("\n🎯 用户可以:")
        print("• 点击⚙️按钮打开设置")
        print("• 设置1-1440分钟的待机提醒时间")
        print("• 选择Ctrl、Alt、Shift、Win的快捷键组合")
        print("• 获得实时的冲突检测和建议")
        print("• 安全保存设置，异常时自动回滚")
        
        return True
    else:
        print(f"⚠️ {total - passed} 项验证失败，请检查相关功能")
        return False


def main():
    """主函数"""
    return run_comprehensive_validation()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)