"""
系统托盘管理器模块

负责应用程序的系统托盘功能:
- 托盘图标显示
- 右键菜单（显示/隐藏/退出）
- 双击显示主窗口
"""

import os
import threading
from typing import Optional, Callable
from pathlib import Path

try:
    import pystray
    from PIL import Image
except ImportError:
    pystray = None
    Image = None


class TrayManager:
    """系统托盘管理器"""

    def __init__(self, app_name: str = "ContextSwitcher"):
        """初始化系统托盘管理器

        Args:
            app_name: 应用程序名称
        """
        if pystray is None:
            raise ImportError("pystray 未安装，请运行: pip install pystray")

        self.app_name = app_name
        self.icon: Optional[pystray.Icon] = None
        self.running = False

        # 回调函数
        self.on_show: Optional[Callable] = None  # 显示窗口回调
        self.on_hide: Optional[Callable] = None  # 隐藏窗口回调
        self.on_exit: Optional[Callable] = None  # 退出程序回调
        self.on_toggle: Optional[Callable] = None  # 切换窗口显示状态回调

        # 加载图标
        self.icon_image = self._load_icon()

    def _load_icon(self):
        """加载托盘图标

        优先级:
        1. icon.ico (如果存在)
        2. 从 PNG/JPEG 转换
        3. 使用默认图标
        """
        # 尝试加载 ico 文件
        icon_path = Path(__file__).parent.parent / "icon.ico"
        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                print(f"加载 icon.ico 失败: {e}")

        # 尝试加���其他图片格式
        for ext in ['.png', '.jpg', '.jpeg']:
            img_path = Path(__file__).parent.parent / f"icon{ext}"
            if img_path.exists():
                try:
                    img = Image.open(img_path)
                    # 调整大小为托盘图标标准尺寸
                    return img.resize((64, 64), Image.Resampling.LANCZOS)
                except Exception as e:
                    print(f"加载 {img_path} 失败: {e}")

        # 创建默认图标
        return self._create_default_icon()

    def _create_default_icon(self):
        """创建默认图标"""
        # 创建一个简单的绿色圆形图标
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))

        # 简单的绿色圆形
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.ellipse([(4, 4), (size - 4, size - 4)], fill=(76, 175, 80, 255))
        draw.ellipse([(8, 8), (size - 8, size - 8)], outline=(255, 255, 255, 200), width=2)

        return img

    def _create_menu(self):
        """创建右键菜单"""
        return pystray.Menu(
            pystray.MenuItem("显示窗口", self._on_show_clicked, default=True),
            pystray.MenuItem("隐藏窗口", self._on_hide_clicked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._on_exit_clicked)
        )

    def _on_show_clicked(self):
        """显示菜单项被点击"""
        if self.on_show:
            # 在主线程中执行回调
            self.on_show()

    def _on_hide_clicked(self):
        """隐藏菜单项被点击"""
        if self.on_hide:
            self.on_hide()

    def _on_exit_clicked(self):
        """退出菜单项被点击"""
        if self.on_exit:
            self.on_exit()

    def _on_double_clicked(self):
        """托盘图标被双击 - 显示窗口"""
        if self.on_show:
            self.on_show()

    def start(self):
        """启动系统托盘（在后台线程中运行）"""
        if self.running:
            return

        self.running = True

        # 创建托盘图标
        self.icon = pystray.Icon(
            name=self.app_name,
            icon=self.icon_image,
            title=self.app_name,
            menu=self._create_menu(),
            action=self._on_double_clicked  # 双击事件
        )

        # 在独立线程中运行托盘
        self.tray_thread = threading.Thread(
            target=self.icon.run,
            daemon=True
        )
        self.tray_thread.start()
        print("[OK] 系统托盘已启动")

    def stop(self):
        """停止系统托盘"""
        if not self.running:
            return

        self.running = False

        if self.icon:
            self.icon.stop()
            self.icon = None

        if hasattr(self, 'tray_thread') and self.tray_thread:
            self.tray_thread.join(timeout=2)

        print("[OK] 系统托盘已停止")

    def set_tooltip(self, text: str):
        """设置托盘图标提示文本

        Args:
            text: 提示文本
        """
        if self.icon:
            self.icon.title = text

    def notify(self, title: str, message: str):
        """显示系统托盘通知

        Args:
            title: 通知标题
            message: 通知内容
        """
        if self.icon:
            self.icon.notify(message, title)

    def update_menu(self, visible: bool):
        """更新菜单状态

        Args:
            visible: 窗口是否可见
        """
        # 可以根据窗口状态动态更新菜单
        pass


def create_tray_manager(app_name: str = "ContextSwitcher") -> Optional[TrayManager]:
    """创建系统托盘管理器

    Args:
        app_name: 应用程序名称

    Returns:
        TrayManager 实例，如果 pystray 不可用则返回 None
    """
    if pystray is None:
        print("警告: pystray 未安装，系统托盘功能不可用")
        return None

    return TrayManager(app_name)
