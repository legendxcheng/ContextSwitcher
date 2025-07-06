"""
图标转换工具
将PNG图标转换为ICO格式以确保Windows兼容性
"""

import os
from pathlib import Path

def convert_png_to_ico():
    """将icon.png转换为icon.ico"""
    try:
        # 尝试导入PIL
        from PIL import Image
        
        project_root = Path(__file__).parent.parent
        png_path = project_root / "icon.png"
        ico_path = project_root / "icon.ico"
        
        if not png_path.exists():
            print(f"PNG图标文件不存在: {png_path}")
            return False
        
        # 打开PNG图像
        img = Image.open(png_path)
        
        # 转换为RGBA模式以支持透明度
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 创建多种尺寸的ICO文件
        # Windows推荐的ICO尺寸: 16x16, 32x32, 48x48, 256x256
        sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
        
        # 保存为ICO格式
        img.save(ico_path, format='ICO', sizes=sizes)
        
        print(f"✅ 图标转换成功: {ico_path}")
        return True
        
    except ImportError:
        print("❌ PIL/Pillow未安装，无法转换图标格式")
        print("建议: pip install Pillow")
        return False
    except Exception as e:
        print(f"❌ 图标转换失败: {e}")
        return False

if __name__ == "__main__":
    convert_png_to_ico()