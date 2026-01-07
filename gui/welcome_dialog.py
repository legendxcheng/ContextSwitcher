"""
欢迎引导对话框模块

为首次使用的用户提供友好的引导体验:
- 介绍应用核心功能
- 展示快捷键使用方法
- 引导创建第一个任务
"""

from typing import Optional
import FreeSimpleGUI as sg

from gui.modern_config import ModernUIConfig
from utils.config import get_config


class WelcomeDialog:
    """欢迎/首次运行引导对话框"""

    def __init__(self):
        """初始化欢迎对话框"""
        self.config = get_config()
        self.dialog_window: Optional[sg.Window] = None
        self.current_page = 0
        self.total_pages = 3

    def should_show(self) -> bool:
        """检查是否应该显示欢迎对话框"""
        return self.config.get('app.first_run', True)

    def mark_completed(self):
        """标记引导已完成"""
        self.config.set('app.first_run', False)

    def show(self) -> bool:
        """显示欢迎对话框"""
        self.current_page = 0
        layout = self._create_layout()
        icon_path = ModernUIConfig._get_icon_path()

        self.dialog_window = sg.Window(
            "欢迎使用 ContextSwitcher",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            resizable=False,
            size=(500, 380),
            background_color="#1a1a1a",
            icon=icon_path if icon_path else None,
            margins=(20, 15)
        )

        self._update_page_display()

        try:
            return self._run_dialog()
        finally:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None

    def _create_layout(self):
        """创建对话框布局"""
        bg = "#1a1a1a"

        # 第一页内容
        page0 = [
            [sg.Text("欢迎使用", font=("Segoe UI", 13), text_color="#888888", background_color=bg)],
            [sg.Text("ContextSwitcher", font=("Segoe UI", 22, "bold"), text_color="#0078D4", background_color=bg)],
            [sg.Text("")],
            [sg.Text("一款专为开发者设计的多任务上下文切换工具",
                    font=("Segoe UI", 10), text_color="#CCCCCC", background_color=bg)],
            [sg.Text("")],
            [sg.Text("快速切换不同任务的窗口环境", font=("Segoe UI", 9), text_color="#888888", background_color=bg)],
            [sg.Text("让您专注于当前工作，提升效率", font=("Segoe UI", 9), text_color="#888888", background_color=bg)],
        ]

        # 第二页内容
        page1 = [
            [sg.Text("核心功能", font=("Segoe UI", 14, "bold"), text_color="#0078D4", background_color=bg)],
            [sg.Text("")],
            [sg.Text("任务管理", font=("Segoe UI", 11, "bold"), text_color="#FFFFFF", background_color=bg),
             sg.Text(" - 创建任务并绑定窗口", font=("Segoe UI", 9), text_color="#AAAAAA", background_color=bg)],
            [sg.Text("")],
            [sg.Text("快捷切换", font=("Segoe UI", 11, "bold"), text_color="#FFFFFF", background_color=bg),
             sg.Text(" - Ctrl+Alt+Space 快速切换", font=("Segoe UI", 9), text_color="#AAAAAA", background_color=bg)],
            [sg.Text("")],
            [sg.Text("窗口记忆", font=("Segoe UI", 11, "bold"), text_color="#FFFFFF", background_color=bg),
             sg.Text(" - 自动记忆文件夹路径", font=("Segoe UI", 9), text_color="#AAAAAA", background_color=bg)],
            [sg.Text("")],
            [sg.Text("时间追踪", font=("Segoe UI", 11, "bold"), text_color="#FFFFFF", background_color=bg),
             sg.Text(" - 记录任务专注时间", font=("Segoe UI", 9), text_color="#AAAAAA", background_color=bg)],
        ]

        # 第三页内容
        page2 = [
            [sg.Text("快速开始", font=("Segoe UI", 14, "bold"), text_color="#0078D4", background_color=bg)],
            [sg.Text("")],
            [sg.Text("1.", font=("Segoe UI", 13, "bold"), text_color="#0078D4", background_color=bg),
             sg.Text(" 点击 [+] 添加新任务", font=("Segoe UI", 10), text_color="#CCCCCC", background_color=bg)],
            [sg.Text("")],
            [sg.Text("2.", font=("Segoe UI", 13, "bold"), text_color="#0078D4", background_color=bg),
             sg.Text(" 为任务选择要绑定的窗口", font=("Segoe UI", 10), text_color="#CCCCCC", background_color=bg)],
            [sg.Text("")],
            [sg.Text("3.", font=("Segoe UI", 13, "bold"), text_color="#0078D4", background_color=bg),
             sg.Text(" 按 Ctrl+Alt+Space 切换", font=("Segoe UI", 10), text_color="#CCCCCC", background_color=bg)],
            [sg.Text("")],
            [sg.Text("提示: 可在设置中自定义快捷键", font=("Segoe UI", 8), text_color="#666666", background_color=bg)],
        ]

        layout = [
            # 页面0
            [sg.pin(sg.Column(page0, key="-PAGE_0-", visible=True, background_color=bg,
                             element_justification='center', expand_x=True))],
            # 页面1
            [sg.pin(sg.Column(page1, key="-PAGE_1-", visible=False, background_color=bg,
                             element_justification='left', expand_x=True))],
            # 页面2
            [sg.pin(sg.Column(page2, key="-PAGE_2-", visible=False, background_color=bg,
                             element_justification='left', expand_x=True))],

            # 垂直填充
            [sg.VPush(background_color=bg)],

            # 页面指示器
            [sg.Text("●", key="-IND_0-", font=("Segoe UI", 11), text_color="#0078D4",
                    pad=(2, 0), background_color=bg),
             sg.Text("○", key="-IND_1-", font=("Segoe UI", 11), text_color="#444444",
                    pad=(2, 0), background_color=bg),
             sg.Text("○", key="-IND_2-", font=("Segoe UI", 11), text_color="#444444",
                    pad=(2, 0), background_color=bg)],

            # 分隔线
            [sg.HorizontalSeparator(color="#333333")],

            # 导航按钮行
            [sg.Button("跳过", key="-SKIP-", size=(8, 1),
                      button_color=("#888888", "#333333"), font=("Segoe UI", 10)),
             sg.Push(background_color=bg),
             sg.Button("上一步", key="-PREV-", size=(8, 1), visible=False,
                      button_color=("#FFFFFF", "#404040"), font=("Segoe UI", 10)),
             sg.Button("下一步", key="-NEXT-", size=(8, 1),
                      button_color=("#FFFFFF", "#0078D4"), font=("Segoe UI", 10)),
             sg.Button("开始使用", key="-START-", size=(8, 1), visible=False,
                      button_color=("#FFFFFF", "#107C10"), font=("Segoe UI", 10))],
        ]

        return layout

    def _run_dialog(self) -> bool:
        """运行对话框事件循环"""
        while True:
            event, values = self.dialog_window.read()

            if event in (sg.WIN_CLOSED, "-SKIP-"):
                self.mark_completed()
                return False

            elif event == "-NEXT-":
                if self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    self._update_page_display()

            elif event == "-PREV-":
                if self.current_page > 0:
                    self.current_page -= 1
                    self._update_page_display()

            elif event == "-START-":
                self.mark_completed()
                return True

    def _update_page_display(self):
        """更新页面显示"""
        if not self.dialog_window:
            return

        # 更新页面可见性
        for i in range(self.total_pages):
            self.dialog_window[f"-PAGE_{i}-"].update(visible=(i == self.current_page))

        # 更新指示器
        for i in range(self.total_pages):
            indicator_text = "●" if i == self.current_page else "○"
            indicator_color = "#0078D4" if i == self.current_page else "#444444"
            self.dialog_window[f"-IND_{i}-"].update(indicator_text, text_color=indicator_color)

        # 更新按钮可见性
        is_first_page = (self.current_page == 0)
        is_last_page = (self.current_page == self.total_pages - 1)

        self.dialog_window["-PREV-"].update(visible=not is_first_page)
        self.dialog_window["-NEXT-"].update(visible=not is_last_page)
        self.dialog_window["-START-"].update(visible=is_last_page)


def show_welcome_if_first_run() -> bool:
    """如果是首次运行，显示欢迎对话框"""
    dialog = WelcomeDialog()
    if dialog.should_show():
        dialog.show()
        return True
    return False
