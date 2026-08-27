"""
快捷键冲突检测模块

负责检测快捷键组合与系统或常见应用的冲突:
- 保守型冲突检测策略
- 已知冲突列表维护
- 用户友好的冲突描述
- 建议替代方案
"""

from typing import List, Dict, Tuple, Set, Optional
import time

from utils.localization import get_localizer, tr


class HotkeyConflictDetector:
    """快捷键冲突检测器"""
    
    # Windows系统保留快捷键
    SYSTEM_RESERVED = {
        frozenset(['ctrl', 'alt', 'del']): "system_security",
        frozenset(['ctrl', 'shift', 'esc']): "task_manager",
        frozenset(['win', 'l']): "lock_screen",
        frozenset(['alt', 'tab']): "window_switch",
        frozenset(['alt', 'f4']): "close_window",
        frozenset(['win', 'd']): "show_desktop",
        frozenset(['win', 'r']): "run_dialog",
        frozenset(['ctrl', 'alt', 'f4']): "close_application",
        frozenset(['ctrl', 'shift', 'n']): "new_folder",
    }
    
    # 常见应用程序快捷键冲突
    COMMON_APP_CONFLICTS = {
        frozenset(['ctrl', 'alt', 't']): ["Windows Terminal", "某些终端应用"],
        frozenset(['ctrl', 'alt', 'n']): ["OneNote", "Notion", "某些笔记应用"],
        frozenset(['ctrl', 'alt', 'v']): ["剪贴板管理工具", "某些密码管理器"],
        frozenset(['ctrl', 'alt', 'f']): ["某些浏览器全屏", "格式化工具"],
        frozenset(['ctrl', 'alt', 'l']): ["某些IDE格式化代码", "锁定工具"],
        frozenset(['ctrl', 'alt', 's']): ["某些编辑器保存所有", "截屏工具"],
        frozenset(['ctrl', 'alt', 'c']): ["某些颜色选择器", "复制工具"],
        frozenset(['ctrl', 'alt', 'p']): ["某些打印预览", "项目工具"],
        frozenset(['ctrl', 'shift', 't']): ["浏览器恢复标签页", "某些IDE"],
        frozenset(['alt', 'shift']): ["输入法切换", "语言切换"],
        frozenset(['win', 'shift']): ["某些系统工具", "窗口管理器"],
    }
    
    # 开发工具特定冲突
    DEVELOPER_TOOL_CONFLICTS = {
        frozenset(['ctrl', 'alt', 'f12']): ["浏览器开发者工具"],
        frozenset(['ctrl', 'shift', 'i']): ["浏览器开发者工具"],
        frozenset(['ctrl', 'alt', 'i']): ["某些IDE检查工具"],
        frozenset(['ctrl', 'alt', 'r']): ["某些IDE重构工具"],
        frozenset(['ctrl', 'alt', 'h']): ["某些IDE继承层次"],
    }
    
    def __init__(self):
        """初始化冲突检测器"""
        self.last_check_time = 0
        self.check_cache = {}
        self.cache_duration = 60  # 缓存60秒
        
        print("✓ 快捷键冲突检测器初始化完成")
    
    def check_hotkey_conflicts(self, modifiers: List[str], 
                             include_app_conflicts: bool = True,
                             include_dev_conflicts: bool = True) -> Dict[str, any]:
        """检测快捷键组合冲突
        
        Args:
            modifiers: 修饰键列表，如 ['ctrl', 'alt']
            include_app_conflicts: 是否检查常见应用冲突
            include_dev_conflicts: 是否检查开发工具冲突
            
        Returns:
            检测结果字典，包含冲突信息和建议
        """
        if not modifiers:
            return {
                'has_conflicts': True,
                'conflicts': [],
                'warnings': [tr('hotkey_conflicts.modifier_required')],
                'severity': 'error',
                'suggestions': [tr('hotkey_conflicts.modifier_suggestion')]
            }
        
        # 创建缓存键
        cache_key = (get_localizer().language, *sorted(modifiers))
        current_time = time.time()
        
        # 检查缓存
        if (cache_key in self.check_cache and 
            current_time - self.last_check_time < self.cache_duration):
            return self.check_cache[cache_key]
        
        result = self._perform_conflict_check(
            modifiers, include_app_conflicts, include_dev_conflicts
        )
        
        # 更新缓存
        self.check_cache[cache_key] = result
        self.last_check_time = current_time
        
        return result
    
    def _perform_conflict_check(self, modifiers: List[str],
                              include_app_conflicts: bool,
                              include_dev_conflicts: bool) -> Dict[str, any]:
        """执行实际的冲突检测"""
        modifier_set = frozenset(modifiers)
        conflicts = []
        warnings = []
        suggestions = []
        severity = 'none'
        
        # 检查系统保留快捷键
        system_conflicts = self._check_system_conflicts(modifier_set)
        if system_conflicts:
            conflicts.extend(system_conflicts)
            severity = 'error'
        
        # 检查常见应用冲突
        if include_app_conflicts:
            app_conflicts = self._check_app_conflicts(modifier_set)
            if app_conflicts:
                conflicts.extend(app_conflicts)
                if severity != 'error':
                    severity = 'warning'
        
        # 检查开发工具冲突
        if include_dev_conflicts:
            dev_conflicts = self._check_dev_conflicts(modifier_set)
            if dev_conflicts:
                conflicts.extend(dev_conflicts)
                if severity != 'error':
                    severity = 'warning'
        
        # 检查组合复杂度
        complexity_warnings = self._check_complexity(modifiers)
        warnings.extend(complexity_warnings)
        
        # 生成建议
        if conflicts or warnings:
            suggestions = self._generate_suggestions(modifier_set, severity)
        
        return {
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts,
            'warnings': warnings,
            'severity': severity,
            'suggestions': suggestions,
            'modifier_count': len(modifiers),
            'combination': '+'.join(sorted(modifiers)).title() + '+1~9'
        }
    
    def _check_system_conflicts(self, modifier_set: frozenset) -> List[str]:
        """检查系统保留快捷键冲突"""
        conflicts = []
        
        for reserved_set, description_key in self.SYSTEM_RESERVED.items():
            if modifier_set.issubset(reserved_set) or reserved_set.issubset(modifier_set):
                conflicts.append(
                    tr(
                        "hotkey_conflicts.system_prefix",
                        description=tr(f"hotkey_conflicts.{description_key}"),
                    )
                )
        
        return conflicts
    
    def _check_app_conflicts(self, modifier_set: frozenset) -> List[str]:
        """检查常见应用冲突"""
        conflicts = []
        
        for app_set, apps in self.COMMON_APP_CONFLICTS.items():
            if modifier_set == app_set:
                app_list = ', '.join(apps[:2])  # 最多显示2个应用
                if len(apps) > 2:
                    app_list += f" 等{len(apps)}个应用"
                conflicts.append(
                    tr("hotkey_conflicts.app_prefix", description=app_list)
                )
        
        return conflicts
    
    def _check_dev_conflicts(self, modifier_set: frozenset) -> List[str]:
        """检查开发工具冲突"""
        conflicts = []
        
        for dev_set, tools in self.DEVELOPER_TOOL_CONFLICTS.items():
            if modifier_set == dev_set:
                tool_list = ', '.join(tools)
                conflicts.append(
                    tr("hotkey_conflicts.developer_prefix", description=tool_list)
                )
        
        return conflicts
    
    def _check_complexity(self, modifiers: List[str]) -> List[str]:
        """检查快捷键组合复杂度"""
        warnings = []
        
        if len(modifiers) == 0:
            warnings.append(tr("hotkey_conflicts.none_selected"))
        elif len(modifiers) >= 4:
            warnings.append(tr("hotkey_conflicts.too_many"))
        elif len(modifiers) >= 3:
            warnings.append(tr("hotkey_conflicts.many"))
        
        # 检查特定组合的易用性
        if 'win' in modifiers and 'ctrl' in modifiers:
            warnings.append(tr("hotkey_conflicts.win_ctrl"))
        
        if 'shift' in modifiers and len(modifiers) >= 2:
            warnings.append(tr("hotkey_conflicts.shift_combo"))
        
        return warnings
    
    def _generate_suggestions(self, current_set: frozenset, severity: str) -> List[str]:
        """生成替代方案建议"""
        suggestions = []
        
        # 基于当前冲突严重程度提供建议
        if severity == 'error':
            suggestions.append(tr("hotkey_conflicts.change_required"))
        
        # 推荐的安全组合
        safe_combinations = [
            (['ctrl', 'alt'], "Ctrl+Alt - 最常用且相对安全的组合"),
            (['ctrl', 'shift'], "Ctrl+Shift - 适合开发者，但可能与IDE冲突"),
            (['alt', 'win'], "Alt+Win - 较少使用，冲突风险低"),
            (['ctrl', 'win'], "Ctrl+Win - 现代系统支持良好"),
        ]
        
        # 过滤掉当前使用的组合
        current_list = sorted(list(current_set))
        for combo, desc in safe_combinations:
            if sorted(combo) != current_list:
                suggestions.append(
                    tr("hotkey_conflicts.recommended", description=desc)
                )
        
        # 添加通用建议
        if len(suggestions) == 0:
            suggestions.append(tr("hotkey_conflicts.safe"))
        
        return suggestions
    
    def test_hotkey_registration(self, modifiers: List[str]) -> Dict[str, any]:
        """测试快捷键是否能够正常注册
        
        Args:
            modifiers: 修饰键列表
            
        Returns:
            测试结果字典
        """
        try:
            # 这里可以实现实际的快捷键注册测试
            # 目前提供基础的模拟测试
            
            if not modifiers:
                return {
                    'success': False,
                    'error': '没有指定修饰键',
                    'details': '快捷键至少需要一个修饰键'
                }
            
            # 模拟注册测试
            test_result = self._simulate_registration_test(modifiers)
            
            return {
                'success': test_result['can_register'],
                'error': test_result.get('error'),
                'details': test_result.get('details', ''),
                'tested_combination': '+'.join(sorted(modifiers)).title() + '+1'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'测试失败: {e}',
                'details': '无法执行快捷键注册测试'
            }
    
    def _simulate_registration_test(self, modifiers: List[str]) -> Dict[str, any]:
        """模拟快捷键注册测试"""
        # 检查是否是已知的无法注册的组合
        problem_combinations = {
            frozenset(['ctrl', 'alt', 'del']): "系统保留，无法注册",
            frozenset(['win', 'l']): "系统保留，无法注册",
            frozenset(['alt', 'tab']): "系统保留，无法注册",
        }
        
        modifier_set = frozenset(modifiers)
        
        for problem_set, reason in problem_combinations.items():
            if modifier_set.issubset(problem_set):
                return {
                    'can_register': False,
                    'error': '无法注册',
                    'details': reason
                }
        
        # 大多数组合应该可以注册
        return {
            'can_register': True,
            'details': '快捷键组合可以正常注册'
        }
    
    def get_recommended_combinations(self) -> List[Dict[str, any]]:
        """获取推荐的快捷键组合"""
        recommendations = [
            {
                'modifiers': ['ctrl', 'alt'],
                'description': 'Ctrl+Alt+1~9',
                'pros': ['最常用的组合', '与大多数应用兼容', '容易按下'],
                'cons': ['某些应用可能有冲突'],
                'rating': 5
            },
            {
                'modifiers': ['ctrl', 'shift'],
                'description': 'Ctrl+Shift+1~9',
                'pros': ['开发者友好', '较少系统冲突'],
                'cons': ['可能与IDE工具冲突', 'Shift键有时不稳定'],
                'rating': 4
            },
            {
                'modifiers': ['alt', 'win'],
                'description': 'Alt+Win+1~9',
                'pros': ['冲突风险很低', '现代系统支持好'],
                'cons': ['不太常见', '需要适应'],
                'rating': 4
            },
            {
                'modifiers': ['ctrl', 'win'],
                'description': 'Ctrl+Win+1~9',
                'pros': ['现代系统支持', '冲突较少'],
                'cons': ['可能与某些Windows功能冲突'],
                'rating': 3
            }
        ]
        
        return recommendations
    
    def clear_cache(self):
        """清除检测缓存"""
        self.check_cache.clear()
        self.last_check_time = 0
        print("✓ 冲突检测缓存已清除")


# 全局实例
conflict_detector = HotkeyConflictDetector()


def get_conflict_detector() -> HotkeyConflictDetector:
    """获取全局冲突检测器实例"""
    return conflict_detector
