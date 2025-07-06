#!/usr/bin/env python3
"""
验证双击和图标修复的脚本
"""

import os
import sys
from pathlib import Path

def verify_icon_fix():
    """验证图标修复"""
    print("🔍 验证图标修复...")
    
    # 检查图标文件
    project_root = Path(__file__).parent
    icon_ico = project_root / "icon.ico"
    icon_png = project_root / "icon.png"
    
    print(f"📁 项目根目录: {project_root}")
    
    if icon_ico.exists():
        size = icon_ico.stat().st_size
        print(f"✅ ICO图标存在: {icon_ico} (大小: {size} bytes)")
        
        # 验证ICO文件格式
        try:
            with open(icon_ico, 'rb') as f:
                header = f.read(4)
                if header[:2] == b'\x00\x00' and header[2:4] == b'\x01\x00':
                    print("✅ ICO文件格式正确")
                else:
                    print("⚠️ ICO文件格式可能有问题")
        except Exception as e:
            print(f"⚠️ 无法验证ICO文件格式: {e}")
    else:
        print("❌ ICO图标文件不存在")
    
    if icon_png.exists():
        size = icon_png.stat().st_size
        print(f"✅ PNG图标存在: {icon_png} (大小: {size} bytes)")
    else:
        print("❌ PNG图标文件不存在")
    
    return icon_ico.exists()

def verify_double_click_fix():
    """验证双击修复"""
    print("\n🔍 验证双击修复...")
    
    # 检查关键文件
    task_dialog = Path(__file__).parent / "gui" / "task_dialog.py"
    
    if not task_dialog.exists():
        print("❌ task_dialog.py 文件不存在")
        return False
    
    # 检查双击相关代码
    try:
        with open(task_dialog, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键修复点
        checks = [
            ("bind('<Double-Button-1>', ' Double')", "双击事件绑定"),
            ("_handle_table_double_click", "双击处理方法"),
            ("-WINDOW_TABLE- Double", "双击事件处理")
        ]
        
        all_found = True
        for check_text, description in checks:
            if check_text in content:
                print(f"✅ {description}: 已实现")
            else:
                print(f"❌ {description}: 未找到")
                all_found = False
        
        # 检查是否移除了旧的双击检测代码
        if "double_click_threshold" not in content:
            print("✅ 旧的双击检测代码已清理")
        else:
            print("⚠️ 仍有旧的双击检测代码残留")
        
        return all_found
        
    except Exception as e:
        print(f"❌ 无法检查双击修复: {e}")
        return False

def verify_ui_updates():
    """验证UI更新"""
    print("\n🔍 验证UI更新...")
    
    task_dialog = Path(__file__).parent / "gui" / "task_dialog.py"
    
    try:
        with open(task_dialog, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查提示文本是否更新
        if "双击窗口行直接添加" in content:
            print("✅ 用户界面提示已更新")
            return True
        else:
            print("❌ 用户界面提示未更新")
            return False
            
    except Exception as e:
        print(f"❌ 无法检查UI更新: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始验证修复...")
    print("=" * 50)
    
    # 验证各项修复
    icon_ok = verify_icon_fix()
    double_click_ok = verify_double_click_fix()
    ui_ok = verify_ui_updates()
    
    print("\n" + "=" * 50)
    print("📊 验证结果摘要:")
    print(f"  • 图标修复: {'✅ 完成' if icon_ok else '❌ 失败'}")
    print(f"  • 双击修复: {'✅ 完成' if double_click_ok else '❌ 失败'}")
    print(f"  • UI更新: {'✅ 完成' if ui_ok else '❌ 失败'}")
    
    if icon_ok and double_click_ok and ui_ok:
        print("\n🎉 所有修复都已完成！")
        print("\n💡 使用说明:")
        print("1. 双击窗口表格行可直接添加窗口到任务")
        print("2. 应用程序图标应该在任务栏和对话框中正确显示")
        print("3. 界面提示文本已更新为双击操作")
        print("\n🔧 如果仍有问题，请检查:")
        print("  • FreeSimpleGUI版本是否最新")
        print("  • 系统是否有权限访问图标文件")
        print("  • 是否需要重启应用程序")
    else:
        print("\n⚠️ 部分修复可能需要进一步调整")

if __name__ == "__main__":
    main()