from core.herdr_integration import HerdrTaskBinding
from core.herdr_terminal import (
    HerdrTerminalController,
    ProcessSnapshot,
    TerminalSystemSnapshot,
    TerminalWindow,
    WindowsHerdrTerminalSystem,
)
from core.herdr_workspace import HerdrWorkspaceError


class FakeHerdrClient:
    def __init__(self):
        self.focused_workspace_ids = []
        self.focused_or_created_labels = []
        self.stale_workspace_ids = set()
        self.focus_or_create_failures = 0

    def focus_workspace_by_id(self, workspace_id):
        self.focused_workspace_ids.append(workspace_id)
        if workspace_id in self.stale_workspace_ids:
            raise HerdrWorkspaceError("missing")

    def focus_or_create_workspace(self, workspace_label):
        self.focused_or_created_labels.append(workspace_label)
        if self.focus_or_create_failures:
            self.focus_or_create_failures -= 1
            raise HerdrWorkspaceError("server not ready")
        return "workspace-created"


class FakeTerminalSystem:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)
        self.launches = []

    def capture_state(self):
        if len(self._snapshots) > 1:
            return self._snapshots.pop(0)
        return self._snapshots[0]

    def resolve_terminal_executable(self):
        return "wt.exe"

    def launch_terminal(self, terminal_executable, herdr_executable):
        self.launches.append((terminal_executable, herdr_executable))


def _running_herdr_snapshot(hwnd=101):
    return TerminalSystemSnapshot(
        windows=(TerminalWindow(hwnd, process_id=10, is_foreground=False),),
        processes=(
            ProcessSnapshot(10, 1, "WindowsTerminal.exe", "WindowsTerminal.exe"),
            ProcessSnapshot(11, 10, "OpenConsole.exe", "OpenConsole.exe"),
            ProcessSnapshot(12, 11, "powershell.exe", "powershell.exe"),
            ProcessSnapshot(13, 12, "herdr.exe", '"C:\\Program Files\\Herdr\\herdr.exe"'),
        ),
    )


def _empty_snapshot():
    return TerminalSystemSnapshot(windows=(), processes=())


def test_existing_herdr_terminal_is_reused_for_bound_task():
    client = FakeHerdrClient()
    terminal_system = FakeTerminalSystem([_running_herdr_snapshot()])
    controller = HerdrTerminalController(
        client,
        herdr_executable="C:\\Program Files\\Herdr\\herdr.exe",
        terminal_system=terminal_system,
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "workspace-3")
    )

    assert result.success is True
    assert result.hwnd == 101
    assert result.launched is False
    assert result.workspace_id == "workspace-3"
    assert client.focused_workspace_ids == ["workspace-3"]
    assert terminal_system.launches == []


def test_missing_herdr_terminal_is_started_in_a_new_window_and_then_reused():
    client = FakeHerdrClient()
    terminal_system = FakeTerminalSystem([
        _empty_snapshot(),
        _running_herdr_snapshot(hwnd=202),
    ])
    controller = HerdrTerminalController(
        client,
        herdr_executable="C:\\Program Files\\Herdr\\herdr.exe",
        terminal_system=terminal_system,
        clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "workspace-3")
    )

    assert result.success is True
    assert result.hwnd == 202
    assert result.launched is True
    assert terminal_system.launches == [
        ("wt.exe", "C:\\Program Files\\Herdr\\herdr.exe")
    ]


def test_new_terminal_retries_workspace_focus_once_while_server_starts():
    client = FakeHerdrClient()
    client.focus_or_create_failures = 1
    terminal_system = FakeTerminalSystem([
        _empty_snapshot(),
        _running_herdr_snapshot(hwnd=202),
    ])
    controller = HerdrTerminalController(
        client,
        herdr_executable="herdr.exe",
        terminal_system=terminal_system,
        clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )

    result = controller.reveal_task(HerdrTaskBinding("task-1", "ContextSwitcher"))

    assert result.success is True
    assert result.workspace_id == "workspace-created"
    assert client.focused_or_created_labels == ["ContextSwitcher", "ContextSwitcher"]


def test_label_only_binding_is_resolved_after_terminal_is_available():
    client = FakeHerdrClient()
    controller = HerdrTerminalController(
        client,
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([_running_herdr_snapshot()]),
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher")
    )

    assert result.success is True
    assert result.workspace_id == "workspace-created"
    assert client.focused_or_created_labels == ["ContextSwitcher"]


def test_stale_workspace_id_falls_back_to_the_binding_label():
    client = FakeHerdrClient()
    client.stale_workspace_ids.add("stale-id")
    controller = HerdrTerminalController(
        client,
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([_running_herdr_snapshot()]),
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "stale-id")
    )

    assert result.success is True
    assert result.workspace_id == "workspace-created"
    assert client.focused_workspace_ids == ["stale-id"]
    assert client.focused_or_created_labels == ["ContextSwitcher"]


def test_stale_workspace_id_without_a_label_returns_a_failure_result():
    client = FakeHerdrClient()
    client.stale_workspace_ids.add("stale-id")
    controller = HerdrTerminalController(
        client,
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([_running_herdr_snapshot()]),
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "", "stale-id")
    )

    assert result.success is False
    assert result.hwnd == 101
    assert "stale-id" in result.message


def test_attached_default_session_is_interactive_but_server_process_is_not():
    snapshot = TerminalSystemSnapshot(
        windows=(
            TerminalWindow(303, process_id=30, is_foreground=True),
            TerminalWindow(404, process_id=40, is_foreground=False),
        ),
        processes=(
            ProcessSnapshot(30, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(31, 30, "herdr.exe", "herdr.exe server"),
            ProcessSnapshot(40, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(41, 40, "herdr.exe", "herdr.exe --session default"),
        ),
    )
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([snapshot]),
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "workspace-3")
    )

    assert result.success is True
    assert result.hwnd == 404


def test_shared_terminal_process_uses_tui_markers_to_reuse_bare_herdr():
    snapshot = TerminalSystemSnapshot(
        windows=(
            TerminalWindow(505, process_id=50, is_foreground=True, title="PowerShell"),
            TerminalWindow(
                606,
                process_id=50,
                is_foreground=False,
                title="Windows PowerShell",
                screen_text="spaces\nother-workspace\nagents       priority",
            ),
        ),
        processes=(
            ProcessSnapshot(50, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(51, 50, "herdr.exe", "herdr.exe"),
        ),
    )
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([snapshot]),
        clock=iter((0.0, 1.0)).__next__,
        sleeper=lambda _seconds: None,
        startup_timeout_seconds=0.5,
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "workspace-3")
    )

    assert result.hwnd == 606


def test_multiple_interactive_candidates_prefer_the_foreground_window():
    snapshot = TerminalSystemSnapshot(
        windows=(
            TerminalWindow(707, process_id=70, is_foreground=False),
            TerminalWindow(808, process_id=80, is_foreground=True),
            TerminalWindow(909, process_id=90, is_foreground=False, title="Herdr"),
        ),
        processes=(
            ProcessSnapshot(70, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(71, 70, "herdr.exe", "herdr.exe"),
            ProcessSnapshot(80, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(81, 80, "herdr.exe", "herdr.exe"),
            ProcessSnapshot(90, 1, "WindowsTerminal.exe"),
            ProcessSnapshot(91, 90, "herdr.exe", "herdr.exe"),
        ),
    )
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="herdr.exe",
        terminal_system=FakeTerminalSystem([snapshot]),
    )

    result = controller.reveal_task(
        HerdrTaskBinding("task-1", "ContextSwitcher", "workspace-3")
    )

    assert result.hwnd == 808


def test_missing_windows_terminal_executable_returns_a_clear_failure():
    class MissingTerminalSystem(FakeTerminalSystem):
        def resolve_terminal_executable(self):
            return None

    terminal_system = MissingTerminalSystem([_empty_snapshot()])
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="herdr.exe",
        terminal_system=terminal_system,
    )

    result = controller.reveal_task(HerdrTaskBinding("task-1", "ContextSwitcher"))

    assert result.success is False
    assert "wt.exe" in result.message
    assert terminal_system.launches == []


def test_unavailable_herdr_executable_is_reported_before_terminal_launch():
    terminal_system = FakeTerminalSystem([_empty_snapshot()])
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="C:\\Missing\\herdr.exe",
        unavailable_message="Herdr 路径无效: C:\\Missing\\herdr.exe",
        terminal_system=terminal_system,
    )

    result = controller.reveal_task(HerdrTaskBinding("task-1", "ContextSwitcher"))

    assert result.success is False
    assert result.message == "Herdr 路径无效: C:\\Missing\\herdr.exe"
    assert terminal_system.launches == []


def test_terminal_startup_timeout_is_bounded_and_reported():
    times = iter((0.0, 0.0, 1.0))
    terminal_system = FakeTerminalSystem([_empty_snapshot()])
    controller = HerdrTerminalController(
        FakeHerdrClient(),
        herdr_executable="herdr.exe",
        terminal_system=terminal_system,
        clock=lambda: next(times),
        sleeper=lambda _seconds: None,
        startup_timeout_seconds=0.5,
    )

    result = controller.reveal_task(HerdrTaskBinding("task-1", "ContextSwitcher"))

    assert result.success is False
    assert result.launched is True
    assert "限定时间" in result.message
    assert terminal_system.launches == [("wt.exe", "herdr.exe")]


def test_windows_terminal_launch_uses_an_argument_list_and_a_new_window():
    calls = []

    def fake_popen(arguments, **options):
        calls.append((arguments, options))
        return object()

    system = WindowsHerdrTerminalSystem(
        which=lambda _name: "C:\\Apps\\wt.exe",
        popen=fake_popen,
    )

    assert system.resolve_terminal_executable() == "C:\\Apps\\wt.exe"
    system.launch_terminal("C:\\Apps\\wt.exe", "C:\\Apps\\Herdr\\herdr.exe")

    assert calls[0][0] == [
        "C:\\Apps\\wt.exe",
        "-w",
        "new",
        "nt",
        "--title",
        "Herdr",
        "--suppressApplicationTitle",
        "C:\\Apps\\Herdr\\herdr.exe",
    ]
    assert "shell" not in calls[0][1]
