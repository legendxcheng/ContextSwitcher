from core.herdr_workspace import HerdrWorkspaceError
from core.task_manager import Task, TaskManager


def test_task_migrates_legacy_wave_workspace_to_herdr():
    task = Task.from_dict({
        "id": "task-1",
        "name": "Legacy task",
        "wave_workspace": "contextSwitcher",
    })

    assert task.herdr_workspace == "contextSwitcher"
    assert "wave_workspace" not in task.to_dict()
    assert "herdr_workspace" not in task.to_dict()
    assert task.to_dict()["herdr_binding"] == {
        "workspace_id": None,
        "label": "contextSwitcher",
    }


def test_explicit_herdr_workspace_wins_over_legacy_value():
    task = Task.from_dict({
        "id": "task-1",
        "name": "Migrated task",
        "herdr_workspace": "new-name",
        "wave_workspace": "old-name",
    })

    assert task.herdr_workspace == "new-name"


def test_workspace_only_task_switch_is_successful():
    class FakeWindowManager:
        @staticmethod
        def abort_current_switch(_switch_id):
            return False

    class FakeTimeTracker:
        current_session = None

        @staticmethod
        def start_session(_task_id, _task_name):
            return None

    task = Task(
        id="task-1",
        name="Workspace only",
        herdr_workspace="contextSwitcher",
    )
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    manager.current_task_index = -1
    manager.window_manager = FakeWindowManager()
    manager.time_tracker = FakeTimeTracker()
    manager.on_task_switched = None
    manager._switch_herdr_workspace_for_task = lambda _task: True
    manager._validate_bound_windows = lambda _task: []

    assert manager.switch_to_task(0) is True


def test_deferred_herdr_switch_skips_sync_cli_and_accepts_workspace_only_task():
    class FakeWindowManager:
        @staticmethod
        def abort_current_switch(_switch_id):
            return False

    class FakeTimeTracker:
        current_session = None

        @staticmethod
        def start_session(_task_id, _task_name):
            return None

    task = Task(
        id="task-1",
        name="Workspace only",
        herdr_workspace="ContextSwitcher",
    )
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    manager.current_task_index = -1
    manager.window_manager = FakeWindowManager()
    manager.time_tracker = FakeTimeTracker()
    switched = []
    manager.on_task_switched = lambda current, index: switched.append(
        (current.id, index)
    )
    manager._switch_herdr_workspace_for_task = lambda _task: (_ for _ in ()).throw(
        AssertionError("the synchronous Herdr client must not run")
    )
    manager._validate_bound_windows = lambda _task: []

    assert manager.switch_to_task(0, defer_herdr=True) is True
    assert switched == [("task-1", 0)]


def test_task_switch_persists_resolved_herdr_workspace_id(monkeypatch):
    class FakeWindowManager:
        @staticmethod
        def abort_current_switch(_switch_id):
            return False

    class FakeTimeTracker:
        current_session = None

        @staticmethod
        def start_session(_task_id, _task_name):
            return None

    task = Task(
        id="task-1",
        name="Workspace only",
        herdr_workspace="ContextSwitcher",
    )
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    manager.current_task_index = -1
    manager.window_manager = FakeWindowManager()
    manager.time_tracker = FakeTimeTracker()
    manager.on_task_switched = None
    manager.on_task_updated = None
    manager._validate_bound_windows = lambda _task: []

    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.resolve_executable",
        lambda _configured: "herdr.exe",
    )
    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.focus_or_create_workspace",
        lambda _client, _label: "workspace-3",
    )

    assert manager.switch_to_task(0) is True
    assert task.herdr_workspace_id == "workspace-3"


def test_task_switch_focuses_persisted_workspace_id_before_label(monkeypatch):
    class FakeWindowManager:
        @staticmethod
        def abort_current_switch(_switch_id):
            return False

    class FakeTimeTracker:
        current_session = None

        @staticmethod
        def start_session(_task_id, _task_name):
            return None

    task = Task(
        id="task-1",
        name="Renamed workspace",
        herdr_workspace="old-label",
        herdr_workspace_id="workspace-3",
    )
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    manager.current_task_index = -1
    manager.window_manager = FakeWindowManager()
    manager.time_tracker = FakeTimeTracker()
    manager.on_task_switched = None
    manager.on_task_updated = None
    manager._validate_bound_windows = lambda _task: []
    focused_ids = []

    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.resolve_executable",
        lambda _configured: "herdr.exe",
    )
    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.focus_workspace_by_id",
        lambda _client, workspace_id: focused_ids.append(workspace_id),
    )
    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.focus_or_create_workspace",
        lambda _client, _label: (_ for _ in ()).throw(
            AssertionError("label fallback should not run")
        ),
    )

    assert manager.switch_to_task(0) is True
    assert focused_ids == ["workspace-3"]


def test_task_switch_falls_back_to_label_when_workspace_id_is_stale(monkeypatch):
    class FakeWindowManager:
        @staticmethod
        def abort_current_switch(_switch_id):
            return False

    class FakeTimeTracker:
        current_session = None

        @staticmethod
        def start_session(_task_id, _task_name):
            return None

    task = Task(
        id="task-1",
        name="Stale workspace",
        herdr_workspace="ContextSwitcher",
        herdr_workspace_id="stale-id",
    )
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    manager.current_task_index = -1
    manager.window_manager = FakeWindowManager()
    manager.time_tracker = FakeTimeTracker()
    manager.on_task_switched = None
    manager.on_task_updated = None
    manager._validate_bound_windows = lambda _task: []

    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.resolve_executable",
        lambda _configured: "herdr.exe",
    )
    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.focus_workspace_by_id",
        lambda _client, _workspace_id: (_ for _ in ()).throw(
            HerdrWorkspaceError("missing")
        ),
    )
    monkeypatch.setattr(
        "core.herdr_workspace.HerdrWorkspaceClient.focus_or_create_workspace",
        lambda _client, _label: "workspace-4",
    )

    assert manager.switch_to_task(0) is True
    assert task.herdr_workspace_id == "workspace-4"


def test_task_serializes_structured_herdr_binding_and_round_trips():
    task = Task(
        id="task-1",
        name="Structured binding",
        herdr_workspace="ContextSwitcher",
        herdr_workspace_id="w3",
    )

    payload = task.to_dict()
    restored = Task.from_dict(payload)

    assert payload["herdr_binding"] == {
        "workspace_id": "w3",
        "label": "ContextSwitcher",
    }
    assert "herdr_workspace" not in payload
    assert "herdr_workspace_id" not in payload
    assert restored.herdr_workspace == "ContextSwitcher"
    assert restored.herdr_workspace_id == "w3"


def test_task_manager_updates_resolved_herdr_binding_through_public_seam():
    task = Task(id="task-1", name="Binding", herdr_workspace="old")
    manager = TaskManager.__new__(TaskManager)
    manager.tasks = [task]
    updated = []
    manager.on_task_updated = updated.append

    assert manager.update_herdr_binding("task-1", "workspace-3", "ContextSwitcher")
    assert task.herdr_workspace_id == "workspace-3"
    assert task.herdr_workspace == "ContextSwitcher"
    assert updated == [task]
