#!/usr/bin/env python3
"""
诊断FreeSimpleGUI表格颜色问题
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_python_version():
    """检查Python版本兼容性"""
    print("🐍 Python版本兼容性检查...")
    
    version_info = sys.version_info
    print(f"当前Python版本: {sys.version}")
    
    # 检查已知问题版本
    issues = []
    
    if version_info.major == 3 and version_info.minor == 7:
        if version_info.micro in [3, 4]:
            issues.append("Python 3.7.3 和 3.7.4 的 tkinter 存在表格颜色问题")
            issues.append("建议降级到 Python 3.7.2 或升级到 3.8+")
        elif version_info.micro == 2:
            print("✅ Python 3.7.2 - 表格颜色支持最佳")
        else:
            print("ℹ️ Python 3.7.x 其他版本，需要测试")
    
    if issues:
        print("⚠️ 发现潜在问题:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("✅ Python版本应该支持表格颜色")
        return True

def test_basic_table_colors():
    """测试基础表格颜色功能"""
    print("\n🧪 测试基础表格颜色功能...")
    
    try:
        import FreeSimpleGUI as sg
        print(f"✅ FreeSimpleGUI版本: {sg.version}")
    except ImportError:
        print("❌ FreeSimpleGUI未安装")
        return False
    except AttributeError:
        print("ℹ️ 无法获取FreeSimpleGUI版本信息")
    
    # 简单的颜色测试
    try:
        sg.theme('DarkGrey13')
        
        test_data = [
            ['行1', '普通'],
            ['行2', '应该是绿色'],
            ['行3', '普通']
        ]
        
        # 测试正确的row_colors格式
        row_colors = [(1, '#00FF00', '#2D2D2D')]  # 第2行绿色
        
        table = sg.Table(
            values=test_data,
            headings=['编号', '描述'],
            row_colors=row_colors,
            num_rows=3
        )
        
        layout = [
            [sg.Text('表格颜色测试 - 第2行应该是绿色')],
            [table],
            [sg.Button('确定')]
        ]
        
        window = sg.Window('颜色测试', layout, finalize=True)
        
        print("📋 测试窗口已打开，请检查第2行是否为绿色")
        
        event, values = window.read()
        window.close()
        
        if event != sg.WIN_CLOSED:
            response = input("第2行是否显示为绿色？(y/n): ").lower().strip()
            return response == 'y'
        
        return False
        
    except Exception as e:
        print(f"❌ 表格颜色测试失败: {e}")
        return False

def test_dynamic_colors():
    """测试动态颜色更新"""
    print("\n🧪 测试动态颜色更新...")
    
    try:
        import FreeSimpleGUI as sg
        
        sg.theme('DarkGrey13')
        
        test_data = [
            ['任务1', '普通'],
            ['任务2', '普通'],
            ['任务3', '普通']
        ]
        
        table = sg.Table(
            values=test_data,
            headings=['任务', '状态'],
            key='-TABLE-',
            num_rows=3
        )
        
        layout = [
            [sg.Text('动态颜色测试')],
            [table],
            [sg.Button('高亮任务1', key='-T1-'), sg.Button('高亮任务2', key='-T2-'), sg.Button('高亮任务3', key='-T3-')],
            [sg.Button('清除高亮', key='-CLEAR-'), sg.Button('退出', key='-EXIT-')]
        ]
        
        window = sg.Window('动态颜色测试', layout, finalize=True)
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, '-EXIT-'):
                break
            elif event == '-T1-':
                window['-TABLE-'].update(row_colors=[(0, '#00FF00', '#2D2D2D')])
                print("设置任务1为绿色")
            elif event == '-T2-':
                window['-TABLE-'].update(row_colors=[(1, '#00FF00', '#2D2D2D')])
                print("设置任务2为绿色")
            elif event == '-T3-':
                window['-TABLE-'].update(row_colors=[(2, '#00FF00', '#2D2D2D')])
                print("设置任务3为绿色")
            elif event == '-CLEAR-':
                window['-TABLE-'].update(row_colors=[])
                print("清除所有颜色")
        
        window.close()
        
        response = input("动态颜色更新是否正常工作？(y/n): ").lower().strip()
        return response == 'y'
        
    except Exception as e:
        print(f"❌ 动态颜色测试失败: {e}")
        return False

def suggest_solutions():
    """提供解决方案建议"""
    print("\n💡 解决方案建议:")
    print("1. 检查Python版本 - 避免使用Python 3.7.3和3.7.4")
    print("2. 更新FreeSimpleGUI到最新版本")
    print("3. 如果表格颜色完全不工作，考虑替代方案:")
    print("   • 使用文本前缀标记当前任务 (如 ► 符号)")
    print("   • 在任务名称中添加颜色标记文字")
    print("   • 使用状态图标区分当前任务")
    print("4. 验证主题设置不会覆盖自定义颜色")

def main():
    """主函数"""
    print("🚀 FreeSimpleGUI表格颜色问题诊断")
    print("=" * 50)
    
    # 检查Python版本
    python_ok = check_python_version()
    
    # 测试基础颜色功能
    basic_ok = test_basic_table_colors()
    
    # 测试动态颜色
    dynamic_ok = test_dynamic_colors() if basic_ok else False
    
    print("\n" + "=" * 50)
    print("📊 诊断结果:")
    print(f"  Python版本: {'✅' if python_ok else '⚠️'}")
    print(f"  基础颜色: {'✅' if basic_ok else '❌'}")
    print(f"  动态颜色: {'✅' if dynamic_ok else '❌'}")
    
    if not (basic_ok and dynamic_ok):
        suggest_solutions()
    else:
        print("🎉 表格颜色功能正常！问题可能在具体实现中。")

if __name__ == "__main__":
    main()