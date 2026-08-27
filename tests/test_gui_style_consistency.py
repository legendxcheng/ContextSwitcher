import unittest

try:
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QPushButton,
        QSpinBox,
        QStyle,
        QStyleFactory,
    )
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from gui.qt.app_style import APPLICATION_STYLE, configure_application_style
    from gui.qt.styles import REQUIRED_ICON_NAMES, get_dark_theme, get_icon


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not available")
class TestGuiStyleConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_application_forces_platform_independent_fusion_style(self):
        native_style = next(
            (name for name in ("windows11", "windowsvista", "Windows") if name in QStyleFactory.keys()),
            None,
        )
        if native_style:
            self.app.setStyle(native_style)

        configure_application_style(self.app)

        self.assertEqual("Fusion", APPLICATION_STYLE)
        self.assertEqual(get_dark_theme(), self.app.styleSheet())

        stylesheet = self.app.styleSheet()
        self.app.setStyleSheet("")
        try:
            self.assertEqual("fusion", self.app.style().objectName().lower())
        finally:
            self.app.setStyleSheet(stylesheet)

    def test_stylesheet_resolves_bundled_subcontrol_icons(self):
        stylesheet = get_dark_theme()

        self.assertNotIn("url(none)", stylesheet)
        self.assertNotIn("__ICON_DIR__", stylesheet)

    def test_required_svg_icons_are_available_to_qt(self):
        for name in REQUIRED_ICON_NAMES:
            with self.subTest(icon=name):
                self.assertFalse(get_icon(name).isNull())

    def test_widget_metrics_do_not_depend_on_initial_windows_style(self):
        snapshots = []
        available_styles = QStyleFactory.keys()

        for initial_style in ("windows11", "windowsvista", "Windows"):
            if initial_style not in available_styles:
                continue

            self.app.setStyle(initial_style)
            configure_application_style(self.app)

            widgets = [QComboBox(), QCheckBox("启用"), QSpinBox(), QPushButton("确定")]
            snapshots.append(
                (
                    tuple(widget.sizeHint().toTuple() for widget in widgets),
                    self.app.style().pixelMetric(QStyle.PM_ScrollBarExtent),
                    self.app.style().pixelMetric(QStyle.PM_IndicatorWidth),
                )
            )

        self.assertGreaterEqual(len(snapshots), 2)
        self.assertTrue(all(snapshot == snapshots[0] for snapshot in snapshots[1:]))


if __name__ == "__main__":
    unittest.main()
