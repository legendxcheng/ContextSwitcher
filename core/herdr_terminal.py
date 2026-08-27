"""Locate the Windows Terminal window hosting the interactive Herdr client."""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Iterable, Optional, Protocol, Tuple

from core.herdr_integration import HerdrTaskBinding
from core.herdr_workspace import HerdrWorkspaceError
from utils.localization import tr


@dataclass(frozen=True)
class ProcessSnapshot:
    """Process identity captured at one point in time."""

    process_id: int
    parent_process_id: int
    name: str
    command_line: str = ""


@dataclass(frozen=True)
class TerminalWindow:
    """One Windows Terminal top-level window candidate."""

    hwnd: int
    process_id: int
    is_foreground: bool = False
    title: str = ""
    screen_text: str = ""


@dataclass(frozen=True)
class TerminalSystemSnapshot:
    """Atomic view of top-level windows and their process tree."""

    windows: Tuple[TerminalWindow, ...]
    processes: Tuple[ProcessSnapshot, ...]


@dataclass(frozen=True)
class HerdrTerminalResult:
    """Outcome of preparing a Herdr terminal for one task."""

    success: bool
    task_id: str
    hwnd: Optional[int] = None
    launched: bool = False
    workspace_id: Optional[str] = None
    workspace_label: str = ""
    message: str = ""


class HerdrTerminalSystem(Protocol):
    """Operating-system boundary used by the Herdr terminal controller."""

    def capture_state(self) -> TerminalSystemSnapshot:
        ...

    def resolve_terminal_executable(self) -> Optional[str]:
        ...

    def launch_terminal(
        self,
        terminal_executable: str,
        herdr_executable: str,
    ) -> None:
        ...


class WindowsHerdrTerminalSystem:
    """Read the Windows process tree and start Herdr in Windows Terminal."""

    def __init__(
        self,
        *,
        which: Callable[[str], Optional[str]] = shutil.which,
        popen: Callable[..., Any] = subprocess.Popen,
        run: Callable[..., Any] = subprocess.run,
        screen_reader: Optional[
            Callable[[Tuple[TerminalWindow, ...]], Dict[int, str]]
        ] = None,
    ):
        self._which = which
        self._popen = popen
        self._run = run
        self._screen_reader = screen_reader

    def capture_state(self) -> TerminalSystemSnapshot:
        import pythoncom
        import win32com.client
        import win32gui
        import win32process

        processes = []
        pythoncom.CoInitialize()
        try:
            service = win32com.client.GetObject("winmgmts:")
            rows = service.ExecQuery(
                "SELECT ProcessId, ParentProcessId, Name, CommandLine "
                "FROM Win32_Process"
            )
            for row in rows:
                processes.append(
                    ProcessSnapshot(
                        int(row.ProcessId),
                        int(row.ParentProcessId),
                        str(row.Name or ""),
                        str(row.CommandLine or ""),
                    )
                )
        finally:
            row = None
            rows = None
            service = None
            pythoncom.CoUninitialize()

        foreground_hwnd = int(win32gui.GetForegroundWindow() or 0)
        windows = []

        def collect_window(hwnd, _context):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                if win32gui.GetClassName(hwnd) != "CASCADIA_HOSTING_WINDOW_CLASS":
                    return True
                _thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            windows.append(
                TerminalWindow(
                    int(hwnd),
                    int(process_id),
                    int(hwnd) == foreground_hwnd,
                    str(win32gui.GetWindowText(hwnd) or ""),
                )
            )
            return True

        win32gui.EnumWindows(collect_window, None)
        terminal_windows = tuple(windows)
        owner_window_counts: Dict[int, int] = defaultdict(int)
        for window in terminal_windows:
            owner_window_counts[window.process_id] += 1
        ambiguous_windows = tuple(
            window
            for window in terminal_windows
            if owner_window_counts[window.process_id] > 1
        )
        if ambiguous_windows:
            reader = self._screen_reader or self._read_terminal_screen_texts
            try:
                screen_texts = reader(ambiguous_windows)
            except Exception:
                screen_texts = {}
            terminal_windows = tuple(
                replace(window, screen_text=screen_texts.get(window.hwnd, ""))
                for window in terminal_windows
            )

        return TerminalSystemSnapshot(terminal_windows, tuple(processes))

    def _read_terminal_screen_texts(
        self,
        windows: Tuple[TerminalWindow, ...],
    ) -> Dict[int, str]:
        powershell = self._which("powershell.exe") or self._which("powershell")
        if not powershell:
            return {}
        handles = ",".join(str(window.hwnd) for window in windows)
        script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$condition = [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ClassNameProperty,
    'TermControl'
)
$items = foreach ($handle in @(%s)) {
    try {
        $root = [System.Windows.Automation.AutomationElement]::FromHandle(
            [IntPtr][Int64]$handle
        )
        $terms = $root.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            $condition
        )
        $texts = foreach ($term in $terms) {
            try {
                $pattern = $term.GetCurrentPattern(
                    [System.Windows.Automation.TextPattern]::Pattern
                )
                $pattern.DocumentRange.GetText(-1)
            } catch {}
        }
        [pscustomobject]@{ hwnd = [Int64]$handle; text = ($texts -join "`n") }
    } catch {
        [pscustomobject]@{ hwnd = [Int64]$handle; text = '' }
    }
}
$json = ConvertTo-Json -InputObject @($items) -Compress
[Console]::Out.Write($json)
""" % handles
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        completed = self._run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-EncodedCommand",
                encoded_script,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=3.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return {}
        payload = json.loads(completed.stdout)
        if isinstance(payload, dict):
            payload = [payload]
        return {
            int(item["hwnd"]): str(item.get("text", "") or "")
            for item in payload
            if isinstance(item, dict) and "hwnd" in item
        }

    def resolve_terminal_executable(self) -> Optional[str]:
        return self._which("wt.exe") or self._which("wt")

    def launch_terminal(
        self,
        terminal_executable: str,
        herdr_executable: str,
    ) -> None:
        self._popen(
            [
                terminal_executable,
                "-w",
                "new",
                "nt",
                "--title",
                "Herdr",
                "--suppressApplicationTitle",
                herdr_executable,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class HerdrTerminalController:
    """Resolve a task binding and locate its interactive Herdr host window."""

    def __init__(
        self,
        client,
        *,
        herdr_executable: str,
        unavailable_message: str = "",
        terminal_system: Optional[HerdrTerminalSystem] = None,
        clock=time.monotonic,
        sleeper=time.sleep,
        startup_timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.1,
    ):
        self.client = client
        self.herdr_executable = herdr_executable
        self.unavailable_message = unavailable_message
        self.terminal_system = terminal_system or WindowsHerdrTerminalSystem()
        self._clock = clock
        self._sleeper = sleeper
        self.startup_timeout_seconds = startup_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def reveal_task(self, binding: HerdrTaskBinding) -> HerdrTerminalResult:
        """Prepare the existing interactive Herdr terminal for foregrounding."""
        if self.unavailable_message:
            return HerdrTerminalResult(
                False,
                binding.task_id,
                workspace_id=binding.workspace_id,
                workspace_label=binding.workspace_label,
                message=self.unavailable_message,
            )

        launched = False
        window = self._find_interactive_window(
            self.terminal_system.capture_state(),
            binding.workspace_label,
        )
        if window is None:
            terminal_executable = self.terminal_system.resolve_terminal_executable()
            if not terminal_executable:
                return HerdrTerminalResult(
                    False,
                    binding.task_id,
                    workspace_id=binding.workspace_id,
                    workspace_label=binding.workspace_label,
                    message=tr("herdr.terminal_wt_missing"),
                )
            try:
                self.terminal_system.launch_terminal(
                    terminal_executable,
                    self.herdr_executable,
                )
                launched = True
            except OSError as exc:
                return HerdrTerminalResult(
                    False,
                    binding.task_id,
                    workspace_id=binding.workspace_id,
                    workspace_label=binding.workspace_label,
                    message=tr("herdr.terminal_start_failed", error=exc),
                )

            deadline = self._clock() + self.startup_timeout_seconds
            while window is None and self._clock() <= deadline:
                window = self._find_interactive_window(
                    self.terminal_system.capture_state(),
                    binding.workspace_label,
                )
                if window is None:
                    self._sleeper(self.poll_interval_seconds)
            if window is None:
                return HerdrTerminalResult(
                    False,
                    binding.task_id,
                    launched=True,
                    workspace_id=binding.workspace_id,
                    workspace_label=binding.workspace_label,
                    message=tr("herdr.terminal_timeout"),
                )

        workspace_label = (binding.workspace_label or "").strip()
        if not binding.workspace_id and not workspace_label:
            return HerdrTerminalResult(
                False,
                binding.task_id,
                hwnd=window.hwnd,
                workspace_label=binding.workspace_label,
                message=tr("herdr.focus_target_missing"),
            )

        focus_attempts = 2 if launched else 1
        last_error: Optional[HerdrWorkspaceError] = None
        for attempt in range(focus_attempts):
            try:
                workspace_id = self._focus_binding(binding, workspace_label)
                return HerdrTerminalResult(
                    True,
                    binding.task_id,
                    hwnd=window.hwnd,
                    launched=launched,
                    workspace_id=workspace_id,
                    workspace_label=workspace_label,
                    message=tr("herdr.terminal_ready"),
                )
            except HerdrWorkspaceError as exc:
                last_error = exc
                if attempt + 1 < focus_attempts:
                    self._sleeper(self.poll_interval_seconds)

        return HerdrTerminalResult(
            False,
            binding.task_id,
            hwnd=window.hwnd,
            launched=launched,
            workspace_id=binding.workspace_id,
            workspace_label=workspace_label,
            message=tr(
                "herdr.terminal_focus_failed",
                target=binding.workspace_id or workspace_label,
                error=last_error,
            ),
        )

    def _focus_binding(
        self,
        binding: HerdrTaskBinding,
        workspace_label: str,
    ) -> Optional[str]:
        if binding.workspace_id:
            try:
                self.client.focus_workspace_by_id(binding.workspace_id)
                return binding.workspace_id
            except HerdrWorkspaceError:
                if not workspace_label:
                    raise
        if workspace_label:
            return self.client.focus_or_create_workspace(workspace_label)
        return None

    @classmethod
    def _find_interactive_window(
        cls,
        snapshot: TerminalSystemSnapshot,
        workspace_label: str = "",
    ) -> Optional[TerminalWindow]:
        processes = {process.process_id: process for process in snapshot.processes}
        children: Dict[int, list[int]] = defaultdict(list)
        for process in snapshot.processes:
            children[process.parent_process_id].append(process.process_id)

        ordered_windows = sorted(
            snapshot.windows,
            key=lambda window: not window.is_foreground,
        )
        candidates = []
        for window in ordered_windows:
            owner = processes.get(window.process_id)
            if owner is None or owner.name.casefold() != "windowsterminal.exe":
                continue
            descendants = cls._descendant_processes(
                window.process_id,
                children,
                processes,
            )
            if any(cls._is_interactive_herdr(process) for process in descendants):
                candidates.append(window)

        owner_window_counts: Dict[int, int] = defaultdict(int)
        for window in snapshot.windows:
            owner_window_counts[window.process_id] += 1
        for window in candidates:
            owner_is_unambiguous = owner_window_counts[window.process_id] == 1
            has_stable_title = window.title.strip().casefold() == "herdr"
            label = (workspace_label or "").strip().casefold()
            shows_workspace = bool(
                label and label in window.screen_text.casefold()
            )
            shows_herdr_tui = cls._screen_looks_like_herdr(window.screen_text)
            if (
                owner_is_unambiguous
                or has_stable_title
                or shows_workspace
                or shows_herdr_tui
            ):
                return window
        return None

    @staticmethod
    def _screen_looks_like_herdr(screen_text: str) -> bool:
        words = set(re.findall(r"[a-z]+", (screen_text or "").casefold()))
        return {"spaces", "agents", "priority"}.issubset(words)

    @staticmethod
    def _descendant_processes(
        root_process_id: int,
        children: Dict[int, list[int]],
        processes: Dict[int, ProcessSnapshot],
    ) -> Iterable[ProcessSnapshot]:
        pending = list(children.get(root_process_id, ()))
        while pending:
            process_id = pending.pop()
            process = processes.get(process_id)
            if process is None:
                continue
            yield process
            pending.extend(children.get(process_id, ()))

    @staticmethod
    def _is_interactive_herdr(process: ProcessSnapshot) -> bool:
        if process.name.casefold() not in {"herdr", "herdr.exe"}:
            return False
        command_line = (process.command_line or "").strip()
        if not command_line:
            return True
        if command_line.startswith('"'):
            closing_quote = command_line.find('"', 1)
            arguments = command_line[closing_quote + 1:].strip()
        else:
            parts = command_line.split(maxsplit=1)
            arguments = parts[1].strip() if len(parts) == 2 else ""
        if not arguments:
            return True
        normalized_arguments = arguments.casefold().split()
        return normalized_arguments in (
            ["--session", "default"],
            ["session", "attach", "default"],
        )


__all__ = [
    "HerdrTerminalController",
    "HerdrTerminalResult",
    "HerdrTerminalSystem",
    "ProcessSnapshot",
    "TerminalSystemSnapshot",
    "TerminalWindow",
    "WindowsHerdrTerminalSystem",
]
