from core.herdr_integration import HerdrTaskState, HerdrTaskTransition
from core.task_manager import Task
from main import ContextSwitcher


class FakeConfig:
    def __init__(self, *, blocked=True, done=True):
        self.value = {
            "monitoring_enabled": True,
            "notify_on_blocked": blocked,
            "notify_on_done": done,
        }

    def get(self, key, default=None):
        if key == "integrations.herdr":
            return self.value
        return default


class FakeTray:
    def __init__(self):
        self.messages = []

    def show_message(self, title, message):
        self.messages.append((title, message))


def test_background_blocked_transition_shows_task_notification(monkeypatch):
    app = ContextSwitcher()
    app.task_manager = type("Manager", (), {
        "tasks": [Task(id="task-1", name="Agent task")],
    })()
    app.tray_icon = FakeTray()
    monkeypatch.setattr("utils.config.get_config", lambda: FakeConfig())

    app._on_herdr_transition(HerdrTaskTransition(
        task_id="task-1",
        workspace_id="workspace-1",
        state=HerdrTaskState.BLOCKED,
        state_change_seq=8,
    ))

    assert app.tray_icon.messages == [
        ("Herdr Agent 需要关注", "Agent task · Agent 已阻塞"),
    ]


def test_disabled_done_notifications_are_suppressed(monkeypatch):
    app = ContextSwitcher()
    app.task_manager = type("Manager", (), {
        "tasks": [Task(id="task-1", name="Agent task")],
    })()
    app.tray_icon = FakeTray()
    monkeypatch.setattr("utils.config.get_config", lambda: FakeConfig(done=False))

    app._on_herdr_transition(HerdrTaskTransition(
        task_id="task-1",
        workspace_id="workspace-1",
        state=HerdrTaskState.DONE,
        state_change_seq=9,
    ))

    assert app.tray_icon.messages == []
