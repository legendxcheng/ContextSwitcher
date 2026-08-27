import threading
import unittest

try:
    import PySide6  # noqa: F401
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from PySide6.QtCore import Qt

    from core.herdr_integration import HerdrTaskBinding
    from core.herdr_terminal import HerdrTerminalResult
    from gui.qt.herdr_runtime_monitor import HerdrRuntimeMonitor


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not available")
class TestHerdrRuntimeMonitor(unittest.TestCase):
    def test_only_one_snapshot_refresh_can_be_in_flight(self):
        entered = threading.Event()
        release = threading.Event()

        class BlockingCoordinator:
            calls = 0

            def refresh(self, _bindings):
                self.calls += 1
                entered.set()
                release.wait(timeout=2)
                return "snapshot"

        coordinator = BlockingCoordinator()
        monitor = HerdrRuntimeMonitor(coordinator)
        try:
            self.assertTrue(monitor.request_refresh(()))
            self.assertTrue(entered.wait(timeout=1))
            self.assertFalse(monitor.request_refresh(()))
            self.assertEqual(1, coordinator.calls)
        finally:
            release.set()
            monitor.shutdown(wait=True)

    def test_reveal_requests_are_serialized_and_only_the_latest_waiter_is_kept(self):
        entered = threading.Event()
        release = threading.Event()
        latest_finished = threading.Event()

        class UnusedCoordinator:
            pass

        class BlockingTerminalController:
            def __init__(self):
                self.task_ids = []

            def reveal_task(self, binding):
                self.task_ids.append(binding.task_id)
                if len(self.task_ids) == 1:
                    entered.set()
                    release.wait(timeout=2)
                if binding.task_id == "task-3":
                    latest_finished.set()
                return HerdrTerminalResult(True, binding.task_id, hwnd=101)

        controller = BlockingTerminalController()
        monitor = HerdrRuntimeMonitor(
            UnusedCoordinator(),
            terminal_controller=controller,
        )
        try:
            self.assertTrue(
                monitor.request_reveal(HerdrTaskBinding("task-1", "one", "ws-1"))
            )
            self.assertTrue(entered.wait(timeout=1))
            self.assertTrue(
                monitor.request_reveal(HerdrTaskBinding("task-2", "two", "ws-2"))
            )
            self.assertTrue(
                monitor.request_reveal(HerdrTaskBinding("task-3", "three", "ws-3"))
            )
            release.set()
            self.assertTrue(latest_finished.wait(timeout=1))
            self.assertEqual(["task-1", "task-3"], controller.task_ids)
        finally:
            release.set()
            monitor.shutdown(wait=True)

    def test_startup_timeout_is_forwarded_to_latest_waiter_without_relaunching(self):
        entered = threading.Event()
        release = threading.Event()
        latest_finished = threading.Event()
        emitted = []

        class UnusedCoordinator:
            pass

        class TimedOutTerminalController:
            def __init__(self):
                self.task_ids = []

            def reveal_task(self, binding):
                self.task_ids.append(binding.task_id)
                entered.set()
                release.wait(timeout=2)
                return HerdrTerminalResult(
                    False,
                    binding.task_id,
                    launched=True,
                    message="startup timed out",
                )

        controller = TimedOutTerminalController()
        monitor = HerdrRuntimeMonitor(
            UnusedCoordinator(),
            terminal_controller=controller,
        )

        def collect(result):
            emitted.append(result)
            if result.task_id == "task-2":
                latest_finished.set()

        monitor.reveal_finished.connect(collect, Qt.DirectConnection)
        try:
            self.assertTrue(
                monitor.request_reveal(HerdrTaskBinding("task-1", "one", "ws-1"))
            )
            self.assertTrue(entered.wait(timeout=1))
            self.assertTrue(
                monitor.request_reveal(HerdrTaskBinding("task-2", "two", "ws-2"))
            )
            release.set()
            self.assertTrue(latest_finished.wait(timeout=1))
            self.assertEqual(["task-1"], controller.task_ids)
            self.assertFalse(emitted[-1].success)
            self.assertEqual("startup timed out", emitted[-1].message)
        finally:
            release.set()
            monitor.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
