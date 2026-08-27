"""Thread-safe Qt boundary for global hotkey events."""

from PySide6.QtCore import QObject, Signal


class QtHotkeyProxy(QObject):
    """Queue listener-thread requests as Qt signals."""

    task_switcher_requested = Signal(str)
    main_window_summon_requested = Signal()
    hotkey_error = Signal(str)

    def request_task_switcher(self, hotkey_name: str) -> None:
        self.task_switcher_requested.emit(hotkey_name)

    def request_main_window_summon(self) -> None:
        self.main_window_summon_requested.emit()

    def report_hotkey_error(self, message: str) -> None:
        self.hotkey_error.emit(message)


__all__ = ["QtHotkeyProxy"]
