import unittest
from types import SimpleNamespace

try:
    from PySide6.QtWidgets import QApplication

    from core.herdr_integration import HerdrTaskState, HerdrTaskSummary
    from gui.qt.widgets.task_table import TaskTableWidget

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not available")
class TestTaskTableHerdrStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.table = TaskTableWidget()

    def tearDown(self):
        self.table.close()
        self._app.processEvents()

    def test_agent_status_has_a_dedicated_column_and_tooltip(self):
        task = SimpleNamespace(
            name="Agent task",
            bound_windows=[],
            status="todo",
            priority=2,
            last_active_seconds=None,
            herdr_workspace="ContextSwitcher",
            herdr_summary=HerdrTaskSummary(
                task_id="task-1",
                state=HerdrTaskState.BLOCKED,
                workspace_id="workspace-1",
                workspace_label="ContextSwitcher",
                agent_counts={"blocked": 1, "idle": 2},
                urgent_pane_id="pane-9",
                urgent_agent="codex",
                last_updated=123.0,
            ),
        )

        self.table.load_tasks([task])

        self.assertEqual("A", self.table.COLUMNS[1])
        agent_item = self.table.item(0, 1)
        self.assertEqual("●", agent_item.text())
        self.assertEqual("#D13438", agent_item.foreground().color().name().upper())
        self.assertIn("Agent 状态: 已阻塞", agent_item.toolTip())
        self.assertIn("blocked: 1", agent_item.toolTip())
        self.assertIn("codex", agent_item.toolTip())
        self.assertIn("更新于:", agent_item.toolTip())

    def test_clicking_agent_column_requests_focus_for_that_row(self):
        requested_rows = []
        self.table.agent_focus_requested.connect(requested_rows.append)

        self.table.cellClicked.emit(3, 1)

        self.assertEqual([3], requested_rows)


if __name__ == "__main__":
    unittest.main()
