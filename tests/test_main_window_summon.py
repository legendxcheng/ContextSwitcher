import threading
import unittest
from unittest.mock import patch

from core.task_manager import Task
from pynput.keyboard import Key
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from core.hotkey_manager import HotkeyManager
from gui.qt.hotkey_proxy import QtHotkeyProxy
from gui.qt.qt_main_window import QtMainWindow
from gui.qt.qt_welcome_dialog import QtWelcomeDialog
from gui.qt.widgets.system_tray import SystemTrayIcon
from main import ContextSwitcher


class _FakeTaskManager:
    def __init__(self):
        self.tasks = [Task(id="task-1", name="Task 1")]
        self.current_task_index = 0

    def get_current_task(self):
        return self.tasks[self.current_task_index]

    def get_task_by_id(self, task_id):
        return next((task for task in self.tasks if task.id == task_id), None)


class _ManualClock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _ManualKeyboardListener:
    instance = None

    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self.running = False
        type(self).instance = self

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def tap(self, key, clock):
        self.on_press(key)
        clock.advance(0.04)
        self.on_release(key)


class _FixedScreenContext:
    def __init__(self):
        self.cursor = QPoint(500, 300)
        self.work_area = QRect(0, 0, 1920, 1040)
        self.last_access_thread_id = None

    def current(self):
        self.last_access_thread_id = threading.get_ident()
        return self.cursor, self.work_area


class _FakeConfig:
    def get_hotkeys_config(self):
        return {
            "enabled": True,
            "switcher_enabled": True,
            "switcher_modifiers": ["ctrl", "alt"],
            "switcher_key": "space",
        }


class _FakeTaskSwitcher:
    def __init__(self):
        self.show_count = 0

    def show_switcher(self, _main_window_position):
        self.show_count += 1
        return False


class TestMainWindowSummon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = _ManualClock()
        self.task_manager = _FakeTaskManager()
        self.screen_context = _FixedScreenContext()
        self.window = QtMainWindow(
            self.task_manager,
            screen_context_provider=self.screen_context,
        )
        self.window.hide()

        self.proxy = QtHotkeyProxy()
        self.hotkeys = HotkeyManager(
            self.task_manager,
            listener_factory=_ManualKeyboardListener,
            monotonic_clock=self.clock,
            config=_FakeConfig(),
        )
        self.context_switcher = ContextSwitcher()
        self.context_switcher.task_manager = self.task_manager
        self.context_switcher.main_window = self.window
        self.context_switcher.hotkey_manager = self.hotkeys
        self.context_switcher.qt_hotkey_proxy = self.proxy
        self.assertTrue(self.context_switcher.register_hotkeys())

    def _double_alt(self, first=Key.alt_l, second=Key.alt_l, interval=0.20):
        listener = _ManualKeyboardListener.instance
        listener.tap(first, self.clock)
        self.clock.advance(interval)
        listener.tap(second, self.clock)

    def tearDown(self):
        self.hotkeys.cleanup()
        self.window.cleanup()
        self.window.close()
        self.qt_app.processEvents()

    def test_double_alt_summons_hidden_main_window(self):
        self._double_alt()
        self.qt_app.processEvents()

        self.assertTrue(self.window.isVisible())
        self.assertTrue(self.window.isActiveWindow())

    def test_double_right_alt_summons_hidden_main_window(self):
        self._double_alt(Key.alt_r, Key.alt_r)
        self.qt_app.processEvents()

        self.assertTrue(self.window.isVisible())

    def test_generic_alt_events_summon_hidden_main_window(self):
        self._double_alt(Key.alt, Key.alt)
        self.qt_app.processEvents()

        self.assertTrue(self.window.isVisible())

    def test_listener_thread_marshals_summon_to_qt_thread(self):
        qt_thread_id = threading.get_ident()
        listener_thread = threading.Thread(target=self._double_alt)

        listener_thread.start()
        listener_thread.join()
        self.qt_app.processEvents()

        self.assertEqual(qt_thread_id, self.screen_context.last_access_thread_id)

    def test_single_alt_does_not_summon_main_window(self):
        _ManualKeyboardListener.instance.tap(Key.alt_l, self.clock)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_slow_alt_taps_do_not_summon_main_window(self):
        listener = _ManualKeyboardListener.instance
        listener.tap(Key.alt_l, self.clock)
        self.clock.advance(0.40)
        listener.tap(Key.alt_l, self.clock)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_long_alt_press_does_not_contribute_a_tap(self):
        listener = _ManualKeyboardListener.instance
        listener.on_press(Key.alt_l)
        self.clock.advance(0.60)
        listener.on_release(Key.alt_l)
        self.clock.advance(0.20)
        listener.tap(Key.alt_l, self.clock)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_alt_tab_does_not_contribute_a_tap(self):
        listener = _ManualKeyboardListener.instance
        listener.on_press(Key.alt_l)
        listener.on_press(Key.tab)
        listener.on_release(Key.tab)
        listener.on_release(Key.alt_l)
        self.clock.advance(0.20)
        listener.tap(Key.alt_l, self.clock)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_alt_f4_does_not_contribute_a_tap(self):
        listener = _ManualKeyboardListener.instance
        listener.on_press(Key.alt_l)
        listener.on_press(Key.f4)
        listener.on_release(Key.f4)
        listener.on_release(Key.alt_l)
        self.clock.advance(0.20)
        listener.tap(Key.alt_l, self.clock)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_modifier_or_other_key_between_alt_taps_invalidates_sequence(self):
        listener = _ManualKeyboardListener.instance

        for interrupting_key in (Key.ctrl_l, Key.shift_l, Key.cmd, Key.space):
            with self.subTest(interrupting_key=interrupting_key):
                listener.tap(Key.alt_l, self.clock)
                listener.on_press(interrupting_key)
                listener.on_release(interrupting_key)
                listener.tap(Key.alt_l, self.clock)
                self.qt_app.processEvents()
                self.assertFalse(self.window.isVisible())
                self.clock.advance(0.50)

    def test_alt_key_repeat_is_not_counted_as_a_second_tap(self):
        listener = _ManualKeyboardListener.instance
        listener.on_press(Key.alt_l)
        self.clock.advance(0.04)
        listener.on_press(Key.alt_l)
        listener.on_release(Key.alt_l)
        self.qt_app.processEvents()

        self.assertFalse(self.window.isVisible())

    def test_pointer_leaving_hides_main_window(self):
        self.window.summon_at_cursor()
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(240)

        self.assertFalse(self.window.isVisible())

    def test_reentering_before_delay_cancels_auto_hide(self):
        self.window.summon_at_cursor()
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(100)
            QApplication.sendEvent(self.window, QEvent(QEvent.Enter))
            QTest.qWait(140)

        self.assertTrue(self.window.isVisible())

    def test_repeated_leave_enter_leave_uses_latest_hide_deadline(self):
        self.window.summon_at_cursor()
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(100)
            QApplication.sendEvent(self.window, QEvent(QEvent.Enter))
            QTest.qWait(50)
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(240)

        self.assertFalse(self.window.isVisible())

    def test_summon_is_clamped_to_pointer_monitor_work_area(self):
        self.screen_context.cursor = QPoint(-13, 687)
        self.screen_context.work_area = QRect(-1600, -200, 1600, 900)

        self._double_alt(Key.alt_l, Key.alt_r)
        self.qt_app.processEvents()

        self.assertTrue(
            self.screen_context.work_area.contains(self.window.frameGeometry())
        )
        self.assertTrue(self.window.frameGeometry().contains(self.screen_context.cursor))
        self.assertTrue(self.window.task_table.isVisible())
        self.assertAlmostEqual(0.98, self.window.windowOpacity(), places=2)

    def test_summon_has_a_safe_cursor_zone_near_all_work_area_corners(self):
        work_area = QRect(-1600, -200, 1600, 900)
        inset = 12
        corner_cursors = (
            QPoint(work_area.left() + inset, work_area.top() + inset),
            QPoint(work_area.right() - inset, work_area.top() + inset),
            QPoint(work_area.left() + inset, work_area.bottom() - inset),
            QPoint(work_area.right() - inset, work_area.bottom() - inset),
        )

        for cursor in corner_cursors:
            with self.subTest(cursor=cursor):
                self.screen_context.cursor = cursor
                self.screen_context.work_area = work_area
                self.window.summon_at_cursor()
                frame = self.window.frameGeometry()
                local_cursor = cursor - frame.topLeft()

                self.assertTrue(work_area.contains(frame))
                self.assertGreaterEqual(local_cursor.x(), 8)
                self.assertGreaterEqual(local_cursor.y(), 8)
                self.assertLess(local_cursor.x(), frame.width() - 8)
                self.assertLess(local_cursor.y(), frame.height() - 8)

    def test_exact_screen_corners_use_an_opaque_interaction_region(self):
        work_area = QRect(-1600, -200, 1600, 900)
        corner_cursors = (
            work_area.topLeft(),
            work_area.topRight(),
            work_area.bottomLeft(),
            work_area.bottomRight(),
        )

        for cursor in corner_cursors:
            with self.subTest(cursor=cursor):
                self.screen_context.cursor = cursor
                self.screen_context.work_area = work_area
                self.window.summon_at_cursor()
                frame = self.window.frameGeometry()
                local_cursor = cursor - frame.topLeft()
                rendered_window = self.window.grab().toImage()

                self.assertTrue(work_area.contains(frame))
                self.assertTrue(frame.contains(cursor))
                self.assertGreater(
                    rendered_window.pixelColor(local_cursor).alpha(),
                    0,
                )

    def test_hide_and_resummon_preserves_current_task_state(self):
        self.task_manager.tasks.append(Task(id="task-2", name="Task 2"))
        self.task_manager.current_task_index = 1
        current_task = self.task_manager.get_current_task()
        current_task.todo_items = [{"text": "Keep me", "completed": False}]
        self.window.pomodoro_running = True
        self.window.pomodoro_remaining = 123
        monitor = object()
        self.window._herdr_monitor = monitor
        self.window._last_herdr_metadata_signature = ("task-2", "running")
        window_identity = id(self.window)
        refresh_timer_was_active = self.window._refresh_timer.isActive()
        self.window.summon_at_cursor()
        self.window.hide_to_tray()
        self.window.summon_at_cursor()

        self.assertEqual(window_identity, id(self.window))
        self.assertEqual(1, self.task_manager.current_task_index)
        self.assertIs(current_task, self.task_manager.get_current_task())
        self.assertEqual("Keep me", current_task.todo_items[0]["text"])
        self.assertTrue(self.window.pomodoro_running)
        self.assertEqual(123, self.window.pomodoro_remaining)
        self.assertIs(monitor, self.window._herdr_monitor)
        self.assertEqual(
            ("task-2", "running"),
            self.window._last_herdr_metadata_signature,
        )
        self.assertEqual(refresh_timer_was_active, self.window._refresh_timer.isActive())

    def test_summon_repositions_an_already_visible_window(self):
        self._double_alt()
        self.qt_app.processEvents()
        first_position = self.window.pos()

        self.screen_context.cursor = QPoint(1500, 800)
        self.clock.advance(0.50)
        self._double_alt(Key.alt_r, Key.alt_l)
        self.qt_app.processEvents()

        self.assertNotEqual(first_position, self.window.pos())
        self.assertTrue(self.window.frameGeometry().contains(self.screen_context.cursor))

    def test_window_stays_at_active_opacity_during_hide_delay(self):
        self.window.summon_at_cursor()
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(100)

        self.assertAlmostEqual(0.98, self.window.windowOpacity(), places=2)

    def test_moving_from_main_window_to_todo_popup_keeps_app_visible(self):
        self.window.summon_at_cursor()
        self.window.todo_popup.move(
            self.window.x(), self.window.frameGeometry().bottom() + 2
        )
        self.window.todo_popup.show()
        self.qt_app.processEvents()
        popup_cursor = self.window.todo_popup.frameGeometry().center()

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=popup_cursor):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            self.window.eventFilter(self.window.todo_popup, QEvent(QEvent.Enter))
            QTest.qWait(240)

        self.assertTrue(self.window.isVisible())

    def test_leaving_todo_popup_hides_main_window(self):
        self.window.summon_at_cursor()
        self.window.todo_popup.move(
            self.window.x(), self.window.frameGeometry().bottom() + 2
        )
        self.window.todo_popup.show()
        self.qt_app.processEvents()
        popup_cursor = self.window.todo_popup.frameGeometry().center()

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=popup_cursor):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            self.window.eventFilter(self.window.todo_popup, QEvent(QEvent.Enter))
            QTest.qWait(240)

        outside = self.window.todo_popup.frameGeometry().bottomRight() + QPoint(100, 100)
        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            self.window.eventFilter(self.window.todo_popup, QEvent(QEvent.Leave))
            QTest.qWait(240)

        self.assertFalse(self.window.isVisible())

    def test_auto_hide_resumes_after_owned_modal_dialog_closes(self):
        self.window.summon_at_cursor()
        dialog = QDialog(self.window)
        dialog.setModal(True)
        dialog.show()
        self.qt_app.processEvents()
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(240)
            self.assertTrue(self.window.isVisible())

            dialog.close()
            QTest.qWait(240)

        self.assertFalse(self.window.isVisible())

    def test_auto_hide_resumes_after_title_bar_drag_ends(self):
        self.window.summon_at_cursor()
        press = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPointF(10, 10),
            QPointF(10, 10),
            QPointF(10, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        release = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            QPointF(10, 10),
            QPointF(10, 10),
            QPointF(10, 10),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        self.window.title_bar.mousePressEvent(press)
        outside = self.window.frameGeometry().bottomRight() + QPoint(100, 100)

        with patch("gui.qt.qt_main_window.QCursor.pos", return_value=outside):
            QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
            QTest.qWait(240)
            self.assertTrue(self.window.isVisible())

            self.window.title_bar.mouseReleaseEvent(release)
            QTest.qWait(240)

        self.assertFalse(self.window.isVisible())

    def test_existing_task_switcher_shortcut_remains_independent(self):
        task_switcher = _FakeTaskSwitcher()
        self.context_switcher.task_switcher = task_switcher
        listener = _ManualKeyboardListener.instance

        listener.on_press(Key.ctrl_l)
        listener.on_press(Key.alt_l)
        listener.on_press(Key.space)
        listener.on_release(Key.space)
        listener.on_release(Key.alt_l)
        listener.on_release(Key.ctrl_l)
        self.qt_app.processEvents()

        self.assertEqual(1, task_switcher.show_count)
        self.assertFalse(self.window.isVisible())

    def test_returning_user_background_startup_hides_window_and_keeps_controls_active(self):
        tray = SystemTrayIcon()
        self.context_switcher.tray_icon = tray
        self.window.show()

        try:
            with patch.object(self.context_switcher, "_show_welcome_if_needed") as welcome:
                self.assertTrue(self.context_switcher._enter_hidden_background_mode())

            welcome.assert_called_once_with()
            self.assertFalse(self.window.isVisible())
            self.assertTrue(tray.isVisible())
            self.assertTrue(self.hotkeys.is_running())
        finally:
            tray.hide()
            tray.deleteLater()

    def test_first_run_welcome_remains_part_of_background_startup(self):
        tray = SystemTrayIcon()
        self.context_switcher.tray_icon = tray

        try:
            with patch(
                "gui.qt.qt_welcome_dialog.show_welcome_if_first_run",
                return_value=True,
            ) as show_welcome:
                self.assertTrue(self.context_switcher._enter_hidden_background_mode())

            show_welcome.assert_called_once_with(self.window)
            self.assertFalse(self.window.isVisible())
            self.assertTrue(tray.isVisible())
            self.assertTrue(self.hotkeys.is_running())
        finally:
            tray.hide()
            tray.deleteLater()

    def test_user_facing_surfaces_explain_double_alt_summon(self):
        expected_copy = "双击 Alt 在鼠标位置唤出 ContextSwitcher"
        tray = SystemTrayIcon()
        welcome = QtWelcomeDialog()

        try:
            welcome_copy = " ".join(
                label.text() for label in welcome.findChildren(QLabel)
            )
            self.assertIn(expected_copy, tray.toolTip())
            self.assertIn(expected_copy, welcome_copy)
        finally:
            tray.hide()
            tray.deleteLater()
            welcome.close()
            welcome.deleteLater()


if __name__ == "__main__":
    unittest.main()
