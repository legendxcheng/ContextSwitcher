from core.windows_alt_monitor import WindowsAltMonitor
from core.hotkey_manager import HotkeyManager


ALT = 0x12
RIGHT_ALT = 0xA5
CTRL = 0x11
TAB = 0x09
A = 0x41


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class _Config:
    def get_hotkeys_config(self):
        return {"enabled": True, "switcher_enabled": False}


class _Sink:
    def __init__(self):
        self.summons = 0

    def request_main_window_summon(self):
        self.summons += 1

    def request_task_switcher(self, _name):
        pass

    def report_hotkey_error(self, _message):
        pass


def test_double_alt_still_works_after_long_running_unrelated_input():
    summons = []
    monitor = WindowsAltMonitor(lambda: summons.append("summon"))

    for second in range(1, 3601):
        monitor.process_snapshot({A}, float(second))
        monitor.process_snapshot(set(), float(second) + 0.01)

    monitor.process_snapshot({ALT}, 4000.00)
    monitor.process_snapshot(set(), 4000.04)
    monitor.process_snapshot({ALT}, 4000.20)
    monitor.process_snapshot(set(), 4000.24)

    assert summons == ["summon"]


def test_alt_tab_does_not_count_as_an_alt_tap():
    summons = []
    monitor = WindowsAltMonitor(lambda: summons.append("summon"))

    monitor.process_snapshot({ALT}, 10.00)
    monitor.process_snapshot({ALT, TAB}, 10.04)
    monitor.process_snapshot(set(), 10.08)
    monitor.process_snapshot({ALT}, 10.20)
    monitor.process_snapshot(set(), 10.24)

    assert summons == []


def test_right_alt_tolerates_the_ctrl_state_generated_by_altgr():
    summons = []
    monitor = WindowsAltMonitor(lambda: summons.append("summon"))

    monitor.process_snapshot({RIGHT_ALT, CTRL}, 20.00)
    monitor.process_snapshot(set(), 20.04)
    monitor.process_snapshot({RIGHT_ALT, CTRL}, 20.20)
    monitor.process_snapshot(set(), 20.24)

    assert summons == ["summon"]


def test_hook_and_polling_emissions_for_one_gesture_are_coalesced():
    clock = _Clock()
    sink = _Sink()
    manager = HotkeyManager(
        object(),
        listener_factory=object(),
        monotonic_clock=clock,
        config=_Config(),
    )
    manager.set_event_sink(sink)

    manager._emit_main_window_summon()
    manager._emit_main_window_summon()

    assert sink.summons == 1

    clock.now += 0.30
    manager._emit_main_window_summon()

    assert sink.summons == 2


def test_native_monitor_can_summon_when_hook_path_is_unavailable():
    sink = _Sink()
    manager = HotkeyManager(object(), config=_Config())
    manager.set_event_sink(sink)
    monitor = manager._native_alt_monitor

    assert monitor is not None

    monitor.process_snapshot({ALT}, 200.00)
    monitor.process_snapshot(set(), 200.04)
    monitor.process_snapshot({ALT}, 200.20)
    monitor.process_snapshot(set(), 200.24)

    assert sink.summons == 1
