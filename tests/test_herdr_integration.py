from core.herdr_integration import (
    HerdrIntegrationCoordinator,
    HerdrTaskBinding,
    HerdrTaskState,
)


class FakeHerdrClient:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.focused_agents = []
        self.focused_workspaces = []
        self.metadata_reports = []
        self.metadata_clears = []

    def get_runtime_snapshot(self):
        value = self.snapshots.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def focus_agent(self, pane_id):
        self.focused_agents.append(pane_id)

    def focus_workspace_by_id(self, workspace_id):
        self.focused_workspaces.append(workspace_id)

    def report_workspace_metadata(self, workspace_id, tokens, sequence):
        self.metadata_reports.append((workspace_id, tokens, sequence))

    def clear_workspace_metadata(self, workspace_id, token_names, sequence):
        self.metadata_clears.append((workspace_id, tuple(token_names), sequence))


def _workspace(workspace_id, label, *, focused=False):
    return {
        "workspace_id": workspace_id,
        "label": label,
        "focused": focused,
    }


def _agent(workspace_id, pane_id, status, *, sequence=1, agent="codex"):
    return {
        "workspace_id": workspace_id,
        "pane_id": pane_id,
        "agent": agent,
        "agent_status": status,
        "state_change_seq": sequence,
    }


def test_refresh_aggregates_agent_state_for_each_bound_task():
    client = FakeHerdrClient([{
        "workspaces": [
            _workspace("w1", "blocked"),
            _workspace("w2", "working"),
            _workspace("w3", "done"),
            _workspace("w4", "idle"),
            _workspace("w5", "empty"),
        ],
        "agents": [
            _agent("w1", "w1:p1", "working", sequence=5),
            _agent("w1", "w1:p2", "blocked", sequence=7),
            _agent("w2", "w2:p1", "working", sequence=4),
            _agent("w3", "w3:p1", "idle", sequence=2),
            _agent("w3", "w3:p2", "done", sequence=8),
            _agent("w4", "w4:p1", "idle", sequence=3),
        ],
    }])
    coordinator = HerdrIntegrationCoordinator(client)
    bindings = [
        HerdrTaskBinding("task-blocked", "blocked", "w1"),
        HerdrTaskBinding("task-working", "working", "w2"),
        HerdrTaskBinding("task-done", "done", "w3"),
        HerdrTaskBinding("task-idle", "idle", "w4"),
        HerdrTaskBinding("task-empty", "empty", "w5"),
        HerdrTaskBinding("task-unbound", ""),
    ]

    result = coordinator.refresh(bindings)

    assert result.summary_for("task-blocked").state is HerdrTaskState.BLOCKED
    assert result.summary_for("task-blocked").urgent_pane_id == "w1:p2"
    assert result.summary_for("task-blocked").agent_counts == {
        "blocked": 1,
        "working": 1,
    }
    assert result.summary_for("task-working").state is HerdrTaskState.WORKING
    assert result.summary_for("task-done").state is HerdrTaskState.DONE
    assert result.summary_for("task-idle").state is HerdrTaskState.IDLE
    assert result.summary_for("task-empty").state is HerdrTaskState.NOT_STARTED
    assert result.summary_for("task-unbound").state is HerdrTaskState.NOT_BOUND
    assert result.transitions == ()


def test_refresh_emits_one_task_transition_when_background_agent_needs_attention():
    client = FakeHerdrClient([
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "working", sequence=10)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [
                _agent("w1", "w1:p1", "blocked", sequence=11),
                _agent("w1", "w1:p2", "blocked", sequence=12),
            ],
        },
    ])
    coordinator = HerdrIntegrationCoordinator(client)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")

    baseline = coordinator.refresh([binding])
    blocked = coordinator.refresh([binding])

    assert baseline.transitions == ()
    assert len(blocked.transitions) == 1
    transition = blocked.transitions[0]
    assert transition.task_id == "task-1"
    assert transition.workspace_id == "w1"
    assert transition.state is HerdrTaskState.BLOCKED
    assert transition.state_change_seq == 12


def test_new_workspace_binding_establishes_baseline_without_notification():
    client = FakeHerdrClient([
        {"workspaces": [], "agents": []},
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=5)],
        },
    ])
    coordinator = HerdrIntegrationCoordinator(client)

    coordinator.refresh([HerdrTaskBinding("task-1", "")])
    first_bound = coordinator.refresh([
        HerdrTaskBinding("task-1", "ContextSwitcher", "w1")
    ])

    assert first_bound.summary_for("task-1").state is HerdrTaskState.BLOCKED
    assert first_bound.transitions == ()


def test_refresh_keeps_stale_state_and_reconnect_establishes_new_baseline():
    client = FakeHerdrClient([
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "working", sequence=1)],
        },
        RuntimeError("server unavailable"),
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=2)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "done", sequence=3)],
        },
    ])
    coordinator = HerdrIntegrationCoordinator(client, clock=lambda: 123.0)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")

    coordinator.refresh([binding])
    unavailable = coordinator.refresh([binding])
    reconnected = coordinator.refresh([binding])
    done = coordinator.refresh([binding])

    stale = unavailable.summary_for("task-1")
    assert unavailable.available is False
    assert stale.state is HerdrTaskState.WORKING
    assert stale.stale is True
    assert stale.error == "server unavailable"
    assert reconnected.reconnected is True
    assert reconnected.transitions == ()
    assert done.transitions[0].state is HerdrTaskState.DONE


def test_focus_task_targets_urgent_agent_then_falls_back_to_workspace():
    client = FakeHerdrClient([{
        "workspaces": [
            _workspace("w1", "agents"),
            _workspace("w2", "empty"),
        ],
        "agents": [
            _agent("w1", "w1:p1", "working", sequence=20),
            _agent("w1", "w1:p2", "blocked", sequence=10),
        ],
    }])
    coordinator = HerdrIntegrationCoordinator(client)
    agent_binding = HerdrTaskBinding("task-agent", "agents", "w1")
    empty_binding = HerdrTaskBinding("task-empty", "empty", "w2")
    coordinator.refresh([agent_binding, empty_binding])

    agent_focus = coordinator.focus_task(agent_binding)
    workspace_focus = coordinator.focus_task(empty_binding)

    assert agent_focus.success is True
    assert agent_focus.target_kind == "agent"
    assert agent_focus.target_id == "w1:p2"
    assert workspace_focus.success is True
    assert workspace_focus.target_kind == "workspace"
    assert workspace_focus.target_id == "w2"
    assert client.focused_agents == ["w1:p2"]
    assert client.focused_workspaces == ["w2"]


def test_focus_uses_latest_sequence_when_agent_status_priority_ties():
    client = FakeHerdrClient([{
        "workspaces": [_workspace("w1", "agents")],
        "agents": [
            _agent("w1", "w1:p1", "working", sequence=20),
            _agent("w1", "w1:p2", "working", sequence=21),
        ],
    }])
    coordinator = HerdrIntegrationCoordinator(client)
    binding = HerdrTaskBinding("task-1", "agents", "w1")

    coordinator.refresh([binding])
    result = coordinator.focus_task(binding)

    assert result.target_id == "w1:p2"


def test_rebound_task_does_not_focus_or_sync_metadata_to_cached_old_workspace():
    client = FakeHerdrClient([{
        "workspaces": [_workspace("old", "Old")],
        "agents": [_agent("old", "old:p1", "blocked", sequence=8)],
    }])
    coordinator = HerdrIntegrationCoordinator(client, clock=lambda: 123.0)
    coordinator.refresh([HerdrTaskBinding("task-1", "Old", "old")])
    rebound = HerdrTaskBinding("task-1", "New", "new")

    focus = coordinator.focus_task(rebound)
    metadata = coordinator.sync_task_metadata(
        rebound,
        task_name="Rebound",
        task_status="todo",
    )

    assert focus.target_kind == "workspace"
    assert focus.target_id == "new"
    assert client.focused_agents == []
    assert client.focused_workspaces == ["new"]
    assert metadata.workspace_id == "new"
    assert client.metadata_reports[0][0] == "new"


def test_foreground_workspace_does_not_emit_attention_transition():
    client = FakeHerdrClient([
        {
            "workspaces": [_workspace("w1", "ContextSwitcher", focused=True)],
            "agents": [_agent("w1", "w1:p1", "working", sequence=1)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher", focused=True)],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=2)],
        },
    ])
    coordinator = HerdrIntegrationCoordinator(client)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")

    coordinator.refresh([binding])
    foreground = coordinator.refresh([binding])

    assert foreground.transitions == ()


def test_attention_transition_deduplicates_same_authoritative_event_key():
    client = FakeHerdrClient([
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "working", sequence=9)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=10)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "unknown", sequence=10)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=10)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "unknown", sequence=10)],
        },
        {
            "workspaces": [_workspace("w1", "ContextSwitcher")],
            "agents": [_agent("w1", "w1:p1", "blocked", sequence=11)],
        },
    ])
    coordinator = HerdrIntegrationCoordinator(client)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")

    coordinator.refresh([binding])
    first = coordinator.refresh([binding])
    coordinator.refresh([binding])
    duplicate = coordinator.refresh([binding])
    coordinator.refresh([binding])
    reentered = coordinator.refresh([binding])

    assert len(first.transitions) == 1
    assert duplicate.transitions == ()
    assert len(reentered.transitions) == 1
    assert reentered.transitions[0].state_change_seq == 11


def test_metadata_switch_between_tasks_in_same_workspace_does_not_clear_tokens():
    client = FakeHerdrClient([{
        "workspaces": [_workspace("w1", "ContextSwitcher")],
        "agents": [],
    }])
    coordinator = HerdrIntegrationCoordinator(client, clock=lambda: 123.0)
    first = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")
    second = HerdrTaskBinding("task-2", "ContextSwitcher", "w1")
    coordinator.refresh([first, second])

    coordinator.sync_task_metadata(first, task_name="First", task_status="todo")
    coordinator.sync_task_metadata(second, task_name="Second", task_status="todo")

    assert client.metadata_clears == []
    assert [report[1]["cs_task_id"] for report in client.metadata_reports] == [
        "task-1",
        "task-2",
    ]


def test_sync_task_metadata_reports_sanitized_presentation_tokens():
    client = FakeHerdrClient([{
        "workspaces": [_workspace("w1", "ContextSwitcher")],
        "agents": [],
    }])
    coordinator = HerdrIntegrationCoordinator(client, clock=lambda: 123.0)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")
    coordinator.refresh([binding])

    result = coordinator.sync_task_metadata(
        binding,
        task_name="Agent monitoring",
        task_status="in_progress",
        summary="Show status\nwithout leaking terminal output",
    )

    assert result.success is True
    assert client.metadata_reports == [(
        "w1",
        {
            "cs_task": "Agent monitoring",
            "cs_task_id": "task-1",
            "cs_task_status": "in_progress",
            "cs_task_summary": "Show status without leaking terminal output",
        },
        123001,
    )]


def test_incomplete_snapshot_is_unavailable_instead_of_not_started():
    client = FakeHerdrClient([{
        "workspaces": [_workspace("w1", "ContextSwitcher")],
    }])
    coordinator = HerdrIntegrationCoordinator(client, clock=lambda: 123.0)
    binding = HerdrTaskBinding("task-1", "ContextSwitcher", "w1")

    result = coordinator.refresh([binding])

    assert result.available is False
    assert result.summary_for("task-1").state is HerdrTaskState.UNAVAILABLE
    assert "agents" in result.error
