import unittest

try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    from core.herdr_integration import (
        HerdrBindingUpdate,
        HerdrFocusResult,
        HerdrRefreshResult,
        HerdrTaskState,
        HerdrTaskSummary,
        HerdrTaskTransition,
    )
    from core.herdr_terminal import HerdrTerminalResult
    from core.task_manager import Task
    from gui.qt.qt_main_window import QtMainWindow

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


if PYSIDE_AVAILABLE:
    class FakeMonitor(QObject):
        refreshed = Signal(object)
        focus_finished = Signal(object)
        metadata_finished = Signal(object)
        reveal_finished = Signal(object)

        def __init__(self):
            super().__init__()
            self.refreshes = []
            self.focuses = []
            self.metadata = []
            self.reveals = []

        def request_refresh(self, bindings):
            self.refreshes.append(tuple(bindings))
            return True

        def request_focus(self, binding):
            self.focuses.append(binding)
            return True

        def request_reveal(self, binding):
            self.reveals.append(binding)
            return True

        def request_metadata_sync(self, binding, **metadata):
            self.metadata.append((binding, metadata))
            return True

        def request_metadata_clear(self):
            self.metadata.append(None)
            return True


    class FakeTaskManager:
        class FakeWindowManager:
            def __init__(self):
                self.activations = []
                self.activation_result = True

            def activate_window(self, hwnd):
                self.activations.append(hwnd)
                return self.activation_result

        def __init__(self):
            self.tasks = [
                Task(
                    id="task-1",
                    name="Agent task",
                    description="Implement status UI",
                    herdr_workspace="ContextSwitcher",
                )
            ]
            self.current_task_index = 0
            self.updated = []
            self.switches = []
            self.window_manager = self.FakeWindowManager()
            self.on_task_updated = self.updated.append

        def get_current_task(self):
            return self.tasks[self.current_task_index]

        def update_herdr_binding(self, task_id, workspace_id, workspace_label):
            task = next(task for task in self.tasks if task.id == task_id)
            if (
                task.herdr_workspace_id == workspace_id
                and task.herdr_workspace == workspace_label
            ):
                return True
            task.herdr_workspace_id = workspace_id
            task.herdr_workspace = workspace_label
            self.on_task_updated(task)
            return True

        def switch_to_task(self, index, *, defer_herdr=False):
            self.switches.append((index, defer_herdr))
            self.current_task_index = index
            return True


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not available")
class TestQtMainWindowHerdr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.task_manager = FakeTaskManager()
        self.window = QtMainWindow(self.task_manager)
        self.monitor = FakeMonitor()

    def tearDown(self):
        self.window.cleanup()
        self.window.close()
        self._app.processEvents()

    def test_refresh_updates_runtime_state_persists_binding_and_emits_transition(self):
        transitions = []
        self.window.herdr_transition.connect(transitions.append)
        self.window.set_herdr_monitor(self.monitor)

        self.assertEqual("task-1", self.monitor.refreshes[0][0].task_id)
        result = HerdrRefreshResult(
            summaries=(HerdrTaskSummary(
                task_id="task-1",
                state=HerdrTaskState.BLOCKED,
                workspace_id="workspace-1",
                workspace_label="ContextSwitcher",
                agent_counts={"blocked": 1},
                urgent_pane_id="pane-1",
            ),),
            binding_updates=(HerdrBindingUpdate(
                task_id="task-1",
                workspace_id="workspace-1",
                workspace_label="ContextSwitcher",
            ),),
            transitions=(HerdrTaskTransition(
                task_id="task-1",
                workspace_id="workspace-1",
                state=HerdrTaskState.BLOCKED,
                state_change_seq=7,
            ),),
        )

        self.monitor.refreshed.emit(result)

        task = self.task_manager.tasks[0]
        self.assertIs(HerdrTaskState.BLOCKED, task.herdr_summary.state)
        self.assertEqual("workspace-1", task.herdr_workspace_id)
        self.assertEqual([task], self.task_manager.updated)
        self.assertEqual(1, len(transitions))
        self.assertEqual("●", self.window.task_table.item(0, 1).text())

    def test_agent_column_click_requests_urgent_focus(self):
        self.window.set_herdr_monitor(self.monitor)

        self.window.task_table.agent_focus_requested.emit(0)

        self.assertEqual("task-1", self.monitor.focuses[0].task_id)
        messages = []
        self.window.set_status = messages.append
        self.monitor.focus_finished.emit(HerdrFocusResult(True, message="focused"))
        self.assertEqual(["focused"], messages)

    def test_double_click_defers_bound_herdr_task_to_terminal_controller(self):
        self.window.set_herdr_monitor(self.monitor)

        self.window._on_task_activated(0)

        self.assertEqual([(0, True)], self.task_manager.switches)
        self.assertEqual("task-1", self.monitor.reveals[0].task_id)

    def test_double_click_on_unbound_task_keeps_existing_switch_behavior(self):
        task = self.task_manager.tasks[0]
        task.herdr_workspace = None
        task.herdr_workspace_id = None
        self.window.set_herdr_monitor(self.monitor)

        self.window._on_task_activated(0)

        self.assertEqual([(0, False)], self.task_manager.switches)
        self.assertEqual([], self.monitor.reveals)

    def test_terminal_result_activates_herdr_last_and_persists_resolved_binding(self):
        self.window.set_herdr_monitor(self.monitor)
        messages = []
        self.window.set_status = messages.append
        self.window._on_task_activated(0)

        self.monitor.reveal_finished.emit(HerdrTerminalResult(
            True,
            "task-1",
            hwnd=808,
            workspace_id="workspace-8",
            workspace_label="ContextSwitcher",
            message="Herdr Terminal 已就绪",
        ))

        self.assertEqual([808], self.task_manager.window_manager.activations)
        self.assertEqual("workspace-8", self.task_manager.tasks[0].herdr_workspace_id)
        self.assertEqual("Herdr Terminal 已就绪", messages[-1])

    def test_vanished_terminal_is_rediscovered_once_before_reporting_failure(self):
        self.window.set_herdr_monitor(self.monitor)
        self.task_manager.window_manager.activation_result = False
        messages = []
        self.window.set_status = messages.append
        self.window._on_task_activated(0)
        result = HerdrTerminalResult(
            True,
            "task-1",
            hwnd=808,
            workspace_id="workspace-8",
            workspace_label="ContextSwitcher",
        )

        self.monitor.reveal_finished.emit(result)

        self.assertEqual([808], self.task_manager.window_manager.activations)
        self.assertEqual(2, len(self.monitor.reveals))
        self.assertIn("重新查找", messages[-1])

        self.monitor.reveal_finished.emit(result)

        self.assertEqual([808, 808], self.task_manager.window_manager.activations)
        self.assertEqual(2, len(self.monitor.reveals))
        self.assertIn("聚焦失败", messages[-1])

    def test_disabling_metadata_sync_clears_owned_tokens_once(self):
        self.window.set_herdr_monitor(self.monitor)
        self.window._herdr_config = lambda: {"metadata_sync_enabled": False}

        self.window.sync_active_task_metadata()
        self.window.sync_active_task_metadata()

        self.assertEqual([None], self.monitor.metadata)

    def test_switching_to_unbound_task_clears_previous_metadata(self):
        self.window.set_herdr_monitor(self.monitor)

        self.window.sync_active_task_metadata()
        self.window.sync_active_task_metadata()

        self.assertEqual([None], self.monitor.metadata)

    def test_refresh_result_does_not_overwrite_binding_changed_while_in_flight(self):
        task = self.task_manager.tasks[0]
        task.herdr_workspace = "old"
        task.herdr_workspace_id = "workspace-1"
        self.window.set_herdr_monitor(self.monitor)
        submitted_binding = self.monitor.refreshes[-1][0]
        task.herdr_workspace = "new"
        task.herdr_workspace_id = "workspace-2"

        self.monitor.refreshed.emit(HerdrRefreshResult(
            summaries=(HerdrTaskSummary(
                task_id="task-1",
                state=HerdrTaskState.WORKING,
                workspace_id="workspace-1",
                workspace_label="old",
            ),),
            binding_updates=(HerdrBindingUpdate(
                task_id="task-1",
                workspace_id="workspace-1",
                workspace_label="old",
            ),),
            requested_bindings=(submitted_binding,),
        ))

        self.assertEqual("new", task.herdr_workspace)
        self.assertEqual("workspace-2", task.herdr_workspace_id)
        self.assertFalse(hasattr(task, "herdr_summary"))


if __name__ == "__main__":
    unittest.main()
