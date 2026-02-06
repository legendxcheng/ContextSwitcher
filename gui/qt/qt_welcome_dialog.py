"""
PySide6 欢迎引导对话框

首次运行展示功能引导与快捷键说明。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QStackedWidget
)

from utils.config import get_config
from gui.qt.styles import get_dark_theme


class QtWelcomeDialog(QDialog):
    """欢迎/首次运行引导对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.current_page = 0
        self.total_pages = 3

        self._setup_ui()
        self.setStyleSheet(get_dark_theme())

    def should_show(self) -> bool:
        return self.config.get("app.first_run", True)

    def mark_completed(self):
        self.config.set("app.first_run", False)

    def show_dialog(self) -> bool:
        self._update_page()
        result = self.exec()
        return result == QDialog.Accepted

    def reject(self):
        self.mark_completed()
        super().reject()

    def _setup_ui(self):
        self.setWindowTitle("欢迎使用 ContextSwitcher")
        self.setModal(True)
        self.resize(520, 400)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_page0())
        self.stack.addWidget(self._build_page1())
        self.stack.addWidget(self._build_page2())
        layout.addWidget(self.stack, 1)

        # 指示器
        indicator_row = QHBoxLayout()
        indicator_row.addStretch()
        self.indicators = []
        for _ in range(self.total_pages):
            label = QLabel("○")
            label.setStyleSheet("color: #444444; font-size: 12pt;")
            indicator_row.addWidget(label)
            self.indicators.append(label)
        indicator_row.addStretch()
        layout.addLayout(indicator_row)

        # 按钮
        button_row = QHBoxLayout()
        self.skip_btn = QPushButton("跳过")
        self.prev_btn = QPushButton("上一步")
        self.next_btn = QPushButton("下一步")
        self.start_btn = QPushButton("开始使用")

        self.skip_btn.clicked.connect(self._on_skip)
        self.prev_btn.clicked.connect(self._on_prev)
        self.next_btn.clicked.connect(self._on_next)
        self.start_btn.clicked.connect(self._on_start)

        button_row.addWidget(self.skip_btn)
        button_row.addStretch()
        button_row.addWidget(self.prev_btn)
        button_row.addWidget(self.next_btn)
        button_row.addWidget(self.start_btn)
        layout.addLayout(button_row)

    def _build_page0(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._center_label("欢迎使用", 12, "#888888"))
        layout.addWidget(self._center_label("ContextSwitcher", 20, "#0078D4", bold=True))
        layout.addWidget(self._center_label(""))
        layout.addWidget(self._center_label("一款专为开发者设计的多任务上下文切换工具", 10, "#CCCCCC"))
        layout.addWidget(self._center_label("快速切换不同任务的窗口环境", 9, "#888888"))
        layout.addWidget(self._center_label("让您专注于当前工作，提升效率", 9, "#888888"))
        return page

    def _build_page1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self._title_label("核心功能"))
        layout.addWidget(self._feature_label("任务管理", "创建任务并绑定窗口"))
        layout.addWidget(self._feature_label("快捷切换", "Ctrl+Alt+Space 快速切换"))
        layout.addWidget(self._feature_label("窗口记忆", "自动记忆文件夹路径"))
        layout.addWidget(self._feature_label("时间追踪", "记录任务专注时间"))
        layout.addStretch()
        return page

    def _build_page2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self._title_label("快速开始"))
        layout.addWidget(self._step_label("1.", "点击 [+] 添加新任务"))
        layout.addWidget(self._step_label("2.", "为任务选择要绑定的窗口"))
        layout.addWidget(self._step_label("3.", "按 Ctrl+Alt+Space 切换"))
        layout.addWidget(self._center_label("提示: 可在设置中自定义快捷键", 8, "#666666"))
        layout.addStretch()
        return page

    def _center_label(self, text: str, size: int = 10, color: str = "#FFFFFF", bold: bool = False) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        weight = "bold" if bold else "normal"
        label.setStyleSheet(f"color: {color}; font-size: {size}pt; font-weight: {weight};")
        return label

    def _title_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #0078D4; font-size: 14pt; font-weight: bold;")
        return label

    def _feature_label(self, title: str, desc: str) -> QLabel:
        label = QLabel(f"{title} - {desc}")
        label.setStyleSheet("color: #CCCCCC; font-size: 10pt;")
        return label

    def _step_label(self, step: str, text: str) -> QLabel:
        label = QLabel(f"{step} {text}")
        label.setStyleSheet("color: #CCCCCC; font-size: 10pt;")
        return label

    def _update_page(self):
        self.stack.setCurrentIndex(self.current_page)

        for idx, indicator in enumerate(self.indicators):
            if idx == self.current_page:
                indicator.setText("●")
                indicator.setStyleSheet("color: #0078D4; font-size: 12pt;")
            else:
                indicator.setText("○")
                indicator.setStyleSheet("color: #444444; font-size: 12pt;")

        is_first = self.current_page == 0
        is_last = self.current_page == self.total_pages - 1

        self.prev_btn.setVisible(not is_first)
        self.next_btn.setVisible(not is_last)
        self.start_btn.setVisible(is_last)

    def _on_skip(self):
        self.mark_completed()
        self.reject()

    def _on_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page()

    def _on_next(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_page()

    def _on_start(self):
        self.mark_completed()
        self.accept()


def show_welcome_if_first_run(parent=None) -> bool:
    dialog = QtWelcomeDialog(parent)
    if dialog.should_show():
        dialog.show_dialog()
        return True
    return False


__all__ = ["QtWelcomeDialog", "show_welcome_if_first_run"]
