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
from utils.localization import get_localizer, tr
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
        get_localizer().subscribe(self._on_language_changed)

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
        self.setModal(True)
        self.resize(520, 400)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.stack = QStackedWidget()
        self._rebuild_pages()
        layout.addWidget(self.stack, 1)

        # 指示器
        indicator_row = QHBoxLayout()
        indicator_row.addStretch()
        self.indicators = []
        for _ in range(self.total_pages):
            label = QLabel()
            label.setFixedSize(10, 10)
            self._style_indicator(label, active=False)
            indicator_row.addWidget(label)
            self.indicators.append(label)
        indicator_row.addStretch()
        layout.addLayout(indicator_row)

        # 按钮
        button_row = QHBoxLayout()
        self.skip_btn = QPushButton()
        self.prev_btn = QPushButton()
        self.next_btn = QPushButton()
        self.start_btn = QPushButton()

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

        self._retranslate_ui()

    def _build_page0(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._center_label(tr("welcome.welcome"), 12, "#888888"))
        layout.addWidget(self._center_label("ContextSwitcher", 20, "#0078D4", bold=True))
        layout.addWidget(self._center_label(""))
        layout.addWidget(self._center_label(tr("welcome.tagline"), 10, "#CCCCCC"))
        layout.addWidget(self._center_label(tr("welcome.benefit_windows"), 9, "#888888"))
        layout.addWidget(self._center_label(tr("welcome.benefit_focus"), 9, "#888888"))
        return page

    def _build_page1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self._title_label(tr("welcome.features_title")))
        layout.addWidget(self._feature_label(tr("welcome.feature_task_title"), tr("welcome.feature_task_desc")))
        layout.addWidget(self._feature_label(tr("welcome.feature_summon_title"), tr("welcome.summon_desc")))
        layout.addWidget(self._feature_label(tr("welcome.feature_switch_title"), tr("welcome.feature_switch_desc")))
        layout.addWidget(self._feature_label(tr("welcome.feature_memory_title"), tr("welcome.feature_memory_desc")))
        layout.addWidget(self._feature_label(tr("welcome.feature_time_title"), tr("welcome.feature_time_desc")))
        layout.addStretch()
        return page

    def _build_page2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignLeft)

        layout.addWidget(self._title_label(tr("welcome.quick_start")))
        layout.addWidget(self._step_label("1.", tr("welcome.step_add")))
        layout.addWidget(self._step_label("2.", tr("welcome.step_bind")))
        layout.addWidget(self._step_label("3.", tr("welcome.summon_desc")))
        layout.addWidget(self._step_label("4.", tr("welcome.step_switch")))
        layout.addWidget(self._center_label(tr("welcome.tip"), 8, "#666666"))
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
            self._style_indicator(indicator, active=idx == self.current_page)

        is_first = self.current_page == 0
        is_last = self.current_page == self.total_pages - 1

        self.prev_btn.setVisible(not is_first)
        self.next_btn.setVisible(not is_last)
        self.start_btn.setVisible(is_last)

    def _style_indicator(self, indicator: QLabel, active: bool):
        """自绘页码圆点，避免使用随系统字体变化的圆形字符。"""
        background = "#0078D4" if active else "transparent"
        border = "#0078D4" if active else "#606060"
        indicator.setStyleSheet(
            f"background-color: {background}; border: 1px solid {border}; border-radius: 5px;"
        )

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

    def _on_language_changed(self, _language: str) -> None:
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("welcome.window_title"))
        self.skip_btn.setText(tr("welcome.skip"))
        self.prev_btn.setText(tr("welcome.previous"))
        self.next_btn.setText(tr("welcome.next"))
        self.start_btn.setText(tr("welcome.start"))
        self._rebuild_pages()
        self._update_page()

    def _rebuild_pages(self) -> None:
        if not hasattr(self, "stack"):
            return
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater()
        self.stack.addWidget(self._build_page0())
        self.stack.addWidget(self._build_page1())
        self.stack.addWidget(self._build_page2())


def show_welcome_if_first_run(parent=None) -> bool:
    dialog = QtWelcomeDialog(parent)
    if dialog.should_show():
        dialog.show_dialog()
        return True
    return False


__all__ = ["QtWelcomeDialog", "show_welcome_if_first_run"]
