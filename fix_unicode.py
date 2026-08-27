#!/usr/bin/env python3
"""
Unicode符号修复脚本
修复所有Python文件中的Unicode符号，避免GBK编码错误
"""
import os
import re
from pathlib import Path

def fix_unicode_in_file(file_path):
    """修复单个文件中的Unicode符号"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换常见的Unicode符号
        replacements = {
            '✓': '[OK]',
            '✗': '[ERROR]',
            '⚠️': '[WARN]',
            '⚠': '[WARN]',
            '🔧': '[TOOL]',
            '📁': '[DIR]',
            '🎯': '[TARGET]',
            '🔄': '[RELOAD]',
            '📋': '[LIST]',
            '💾': '[SAVE]',
            '🚀': '[START]',
            '🔍': '[SEARCH]',
            '❌': '[FAIL]',
            '✅': '[SUCCESS]',
            '🔥': '[FIRE]',
            '⭐': '[STAR]',
            '💡': '[IDEA]'
        }
        
        modified = False
        for unicode_char, replacement in replacements.items():
            if unicode_char in content:
                content = content.replace(unicode_char, replacement)
                modified = True
                print(f"  替换 {unicode_char} -> {replacement}")
        
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"处理文件失败 {file_path}: {e}")
        return False

def main():
    """主函数"""
    print("开始修复Unicode符号...")
    
    # 获取所有Python文件
    py_files = list(Path('.').glob('**/*.py'))
    
    fixed_count = 0
    for py_file in py_files:
        if py_file.name == 'fix_unicode.py':
            continue  # 跳过自身
        
        print(f"检查: {py_file}")
        if fix_unicode_in_file(py_file):
            fixed_count += 1
            print(f"  ✓ 已修复")
    
    print(f"\n修复完成! 共修复了 {fixed_count} 个文件")

if __name__ == "__main__":
    main()