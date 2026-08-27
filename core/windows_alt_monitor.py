"""Reliable Windows polling monitor for standalone double-Alt gestures."""

import ctypes
import threading
import time
from typing import Callable, Iterable, Optional, Set


class WindowsAltMonitor:
    """Detect double Alt without depending on a long-lived keyboard hook."""

    VK_ALT = 0x12
    VK_LEFT_ALT = 0xA4
    VK_RIGHT_ALT = 0xA5
    ALT_KEYS = frozenset((VK_ALT, VK_LEFT_ALT, VK_RIGHT_ALT))
    CTRL_KEYS = frozenset((0x11, 0xA2, 0xA3))

    def __init__(
        self,
        on_double_alt: Callable[[], None],
        key_state: Optional[Callable[[int], bool]] = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        poll_interval: float = 0.012,
    ):
        self._on_double_alt = on_double_alt
        self._clock = monotonic_clock
        self._poll_interval = poll_interval
        self._key_state = key_state or self._create_windows_key_state_reader()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.double_tap_interval = 0.35
        self.tap_max_duration = 0.5
        self._previous_alt_down = False
        self._alt_pressed_at: Optional[float] = None
        self._tap_invalidated = False
        self._last_tap_released_at: Optional[float] = None

    @staticmethod
    def _create_windows_key_state_reader() -> Callable[[int], bool]:
        get_async_key_state = ctypes.windll.user32.GetAsyncKeyState
        get_async_key_state.argtypes = (ctypes.c_int,)
        get_async_key_state.restype = ctypes.c_short
        return lambda virtual_key: bool(get_async_key_state(virtual_key) & 0x8000)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return
        self._reset_state()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ContextSwitcherAltMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
        self._reset_state()

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval):
            pressed_keys = self._read_pressed_keys()
            self.process_snapshot(pressed_keys, self._clock())

    def _read_pressed_keys(self) -> Set[int]:
        pressed = {
            virtual_key
            for virtual_key in self.ALT_KEYS
            if self._key_state(virtual_key)
        }
        should_scan_other_keys = bool(
            pressed
            or self._previous_alt_down
            or self._last_tap_released_at is not None
        )
        if should_scan_other_keys:
            pressed.update(
                virtual_key
                for virtual_key in range(0x08, 0xFF)
                if virtual_key not in self.ALT_KEYS and self._key_state(virtual_key)
            )
        return pressed

    def process_snapshot(self, pressed_keys: Iterable[int], now: float) -> None:
        """Advance the recognizer from one global keyboard-state snapshot."""
        pressed = set(pressed_keys)
        alt_down = bool(pressed & self.ALT_KEYS)
        other_pressed = pressed - self.ALT_KEYS

        # Windows reports AltGr as Right Alt plus an artificial Ctrl state.
        if self.VK_RIGHT_ALT in pressed:
            other_pressed -= self.CTRL_KEYS

        if (
            self._last_tap_released_at is not None
            and now - self._last_tap_released_at > self.double_tap_interval
        ):
            self._last_tap_released_at = None

        if alt_down:
            if not self._previous_alt_down:
                self._alt_pressed_at = now
                self._tap_invalidated = bool(other_pressed)
            elif other_pressed:
                self._tap_invalidated = True
        elif self._previous_alt_down:
            duration = (
                now - self._alt_pressed_at
                if self._alt_pressed_at is not None
                else None
            )
            valid_tap = bool(
                not self._tap_invalidated
                and not other_pressed
                and duration is not None
                and 0 <= duration <= self.tap_max_duration
            )
            self._alt_pressed_at = None
            self._tap_invalidated = False

            if not valid_tap:
                self._last_tap_released_at = None
            elif (
                self._last_tap_released_at is not None
                and 0 <= now - self._last_tap_released_at <= self.double_tap_interval
            ):
                self._last_tap_released_at = None
                self._on_double_alt()
            else:
                self._last_tap_released_at = now
        elif other_pressed and self._last_tap_released_at is not None:
            self._last_tap_released_at = None

        self._previous_alt_down = alt_down

    def _reset_state(self) -> None:
        self._previous_alt_down = False
        self._alt_pressed_at = None
        self._tap_invalidated = False
        self._last_tap_released_at = None


__all__ = ["WindowsAltMonitor"]
