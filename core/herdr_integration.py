"""Task-level Herdr runtime state, focus, notification, and metadata coordination."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from core.herdr_workspace import HerdrWorkspaceClient
from utils.localization import tr


class HerdrTaskState(str, Enum):
    """ContextSwitcher presentation states derived from Herdr runtime data."""

    NOT_BOUND = "not_bound"
    NOT_STARTED = "not_started"
    BLOCKED = "blocked"
    WORKING = "working"
    DONE = "done"
    IDLE = "idle"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HerdrTaskBinding:
    """The persisted identity ContextSwitcher uses to find a Herdr workspace."""

    task_id: str
    workspace_label: str
    workspace_id: Optional[str] = None

    @property
    def is_bound(self) -> bool:
        return bool((self.workspace_label or "").strip() or self.workspace_id)


@dataclass(frozen=True)
class HerdrTaskSummary:
    """One task's current Herdr presentation and focus information."""

    task_id: str
    state: HerdrTaskState
    workspace_id: Optional[str] = None
    workspace_label: str = ""
    workspace_focused: bool = False
    agent_counts: Mapping[str, int] = field(default_factory=dict)
    urgent_pane_id: Optional[str] = None
    urgent_agent: Optional[str] = None
    state_change_seq: int = 0
    last_updated: float = 0.0
    stale: bool = False
    error: Optional[str] = None

@dataclass(frozen=True)
class HerdrTaskTransition:
    """A task-level state entry that may require user attention."""

    task_id: str
    workspace_id: str
    state: HerdrTaskState
    state_change_seq: int


@dataclass(frozen=True)
class HerdrBindingUpdate:
    """A resolved workspace identity that should be persisted for a task."""

    task_id: str
    workspace_id: str
    workspace_label: str


@dataclass(frozen=True)
class HerdrFocusResult:
    """Outcome of a user-requested Agent/workspace focus action."""

    success: bool
    target_kind: Optional[str] = None
    target_id: Optional[str] = None
    message: str = ""


@dataclass(frozen=True)
class HerdrMetadataResult:
    """Outcome of a best-effort workspace metadata synchronization."""

    success: bool
    workspace_id: Optional[str] = None
    message: str = ""


@dataclass(frozen=True)
class HerdrRefreshResult:
    """Atomic result published to ContextSwitcher after one refresh."""

    summaries: Tuple[HerdrTaskSummary, ...]
    requested_bindings: Tuple[HerdrTaskBinding, ...] = ()
    transitions: Tuple[HerdrTaskTransition, ...] = ()
    binding_updates: Tuple[HerdrBindingUpdate, ...] = ()
    available: bool = True
    reconnected: bool = False
    error: Optional[str] = None

    def summary_for(self, task_id: str) -> HerdrTaskSummary:
        for summary in self.summaries:
            if summary.task_id == task_id:
                return summary
        raise KeyError(task_id)


class HerdrIntegrationCoordinator:
    """Deep module that turns raw Herdr runtime data into task behavior."""

    _STATUS_PRIORITY = {
        "blocked": 0,
        "working": 1,
        "done": 2,
        "idle": 3,
        "unknown": 4,
    }
    METADATA_TOKEN_NAMES = (
        "cs_task",
        "cs_task_id",
        "cs_task_status",
        "cs_task_summary",
    )

    def __init__(
        self,
        client: HerdrWorkspaceClient,
        clock: Callable[[], float] = time.time,
    ):
        self.client = client
        self._clock = clock
        self._last_summaries: Dict[str, HerdrTaskSummary] = {}
        self._notified_transition_keys = set()
        self._baseline_ready = False
        self._was_unavailable = False
        # Herdr sequences are monotonic per source across the lifetime of its
        # session, which may outlive a ContextSwitcher process restart.
        self._metadata_sequence = int(self._clock() * 1000)
        self._metadata_workspace_id: Optional[str] = None

    def refresh(self, bindings: Iterable[HerdrTaskBinding]) -> HerdrRefreshResult:
        """Fetch one snapshot and publish task-level summaries atomically."""
        binding_list = tuple(bindings)
        try:
            snapshot = self.client.get_runtime_snapshot()
            workspace_data = snapshot.get("workspaces")
            agent_data = snapshot.get("agents")
            if not isinstance(workspace_data, list):
                raise ValueError(tr("herdr.snapshot_workspaces_missing"))
            if not isinstance(agent_data, list):
                raise ValueError(tr("herdr.snapshot_agents_missing"))
        except Exception as exc:
            return self._unavailable_result(binding_list, exc)

        reconnected = self._was_unavailable
        captured_at = self._clock()
        workspaces = tuple(
            item for item in workspace_data if isinstance(item, dict)
        )
        agents = tuple(
            item for item in agent_data if isinstance(item, dict)
        )

        summaries = tuple(
            self._summarize_binding(binding, workspaces, agents, captured_at)
            for binding in binding_list
        )
        updates = tuple(
            HerdrBindingUpdate(
                task_id=binding.task_id,
                workspace_id=summary.workspace_id,
                workspace_label=summary.workspace_label,
            )
            for binding, summary in zip(binding_list, summaries)
            if summary.workspace_id
            and (
                binding.workspace_id != summary.workspace_id
                or binding.workspace_label != summary.workspace_label
            )
        )

        transitions = ()
        if self._baseline_ready:
            transition_list = []
            for summary in summaries:
                previous = self._last_summaries.get(summary.task_id)
                if (
                    not summary.workspace_id
                    or summary.workspace_focused
                    or summary.state not in (HerdrTaskState.BLOCKED, HerdrTaskState.DONE)
                    or previous is None
                    or previous.state == summary.state
                    or previous.workspace_id != summary.workspace_id
                ):
                    continue
                event_key = (
                    summary.task_id,
                    summary.workspace_id,
                    summary.state,
                    summary.state_change_seq,
                )
                if event_key in self._notified_transition_keys:
                    continue
                self._notified_transition_keys.add(event_key)
                transition_list.append(HerdrTaskTransition(
                    task_id=summary.task_id,
                    workspace_id=summary.workspace_id,
                    state=summary.state,
                    state_change_seq=summary.state_change_seq,
                ))
            transitions = tuple(transition_list)

        self._last_summaries = {summary.task_id: summary for summary in summaries}
        self._baseline_ready = True
        self._was_unavailable = False
        return HerdrRefreshResult(
            summaries=summaries,
            requested_bindings=binding_list,
            transitions=transitions,
            binding_updates=updates,
            reconnected=reconnected,
        )

    def _unavailable_result(
        self,
        bindings: Sequence[HerdrTaskBinding],
        exc: Exception,
    ) -> HerdrRefreshResult:
        error = str(exc) or exc.__class__.__name__
        captured_at = self._clock()
        summaries = []
        for binding in bindings:
            previous = self._last_summaries.get(binding.task_id)
            if previous is not None:
                summaries.append(replace(previous, stale=True, error=error))
            elif not binding.is_bound:
                summaries.append(HerdrTaskSummary(
                    task_id=binding.task_id,
                    state=HerdrTaskState.NOT_BOUND,
                    last_updated=captured_at,
                    stale=True,
                    error=error,
                ))
            else:
                summaries.append(HerdrTaskSummary(
                    task_id=binding.task_id,
                    state=HerdrTaskState.UNAVAILABLE,
                    workspace_id=binding.workspace_id,
                    workspace_label=binding.workspace_label,
                    last_updated=captured_at,
                    stale=True,
                    error=error,
                ))

        self._baseline_ready = False
        self._was_unavailable = True
        return HerdrRefreshResult(
            summaries=tuple(summaries),
            requested_bindings=tuple(bindings),
            available=False,
            error=error,
        )

    def focus_task(self, binding: HerdrTaskBinding) -> HerdrFocusResult:
        """Focus the most urgent known Agent, or the bound workspace."""
        summary = self._last_summaries.get(binding.task_id)
        if summary is not None and not self._summary_matches_binding(summary, binding):
            summary = None

        try:
            if summary is not None and summary.urgent_pane_id:
                self.client.focus_agent(summary.urgent_pane_id)
                return HerdrFocusResult(
                    True,
                    target_kind="agent",
                    target_id=summary.urgent_pane_id,
                    message=tr("herdr.focused_agent"),
                )
            workspace_id = binding.workspace_id or (
                summary.workspace_id if summary is not None else None
            )
            if workspace_id:
                self.client.focus_workspace_by_id(workspace_id)
                return HerdrFocusResult(
                    True,
                    target_kind="workspace",
                    target_id=workspace_id,
                    message=tr("herdr.focused_workspace"),
                )
        except Exception as exc:
            return HerdrFocusResult(
                False, message=str(exc) or tr("herdr.focus_failed")
            )

        return HerdrFocusResult(False, message=tr("herdr.focus_target_missing"))

    def sync_task_metadata(
        self,
        binding: HerdrTaskBinding,
        *,
        task_name: str,
        task_status: str,
        summary: str = "",
    ) -> HerdrMetadataResult:
        """Best-effort sync of the active task's presentation-only metadata."""
        task_summary = self._last_summaries.get(binding.task_id)
        if task_summary is not None and not self._summary_matches_binding(task_summary, binding):
            task_summary = None
        workspace_id = binding.workspace_id or (
            task_summary.workspace_id if task_summary is not None else None
        )
        if not workspace_id:
            return HerdrMetadataResult(
                False, message=tr("herdr.metadata_target_missing")
            )

        try:
            if (
                self._metadata_workspace_id
                and self._metadata_workspace_id != workspace_id
            ):
                self.client.clear_workspace_metadata(
                    self._metadata_workspace_id,
                    self.METADATA_TOKEN_NAMES,
                    self._next_metadata_sequence(),
                )

            tokens = {
                "cs_task": self._sanitize_metadata(task_name, 80),
                "cs_task_id": self._sanitize_metadata(binding.task_id, 80),
                "cs_task_status": self._sanitize_metadata(task_status, 40),
                "cs_task_summary": self._sanitize_metadata(summary, 160),
            }
            self.client.report_workspace_metadata(
                workspace_id,
                tokens,
                self._next_metadata_sequence(),
            )
            self._metadata_workspace_id = workspace_id
            return HerdrMetadataResult(
                True, workspace_id, tr("herdr.metadata_synced")
            )
        except Exception as exc:
            return HerdrMetadataResult(
                False,
                workspace_id,
                str(exc) or tr("herdr.metadata_sync_failed"),
            )

    def clear_active_metadata(self) -> HerdrMetadataResult:
        """Clear ContextSwitcher-owned tokens from the last metadata workspace."""
        workspace_id = self._metadata_workspace_id
        if not workspace_id:
            return HerdrMetadataResult(
                True, message=tr("herdr.metadata_nothing_to_clear")
            )
        try:
            self.client.clear_workspace_metadata(
                workspace_id,
                self.METADATA_TOKEN_NAMES,
                self._next_metadata_sequence(),
            )
            self._metadata_workspace_id = None
            return HerdrMetadataResult(
                True, workspace_id, tr("herdr.metadata_cleared")
            )
        except Exception as exc:
            return HerdrMetadataResult(
                False,
                workspace_id,
                str(exc) or tr("herdr.metadata_clear_failed"),
            )

    def _next_metadata_sequence(self) -> int:
        self._metadata_sequence += 1
        return self._metadata_sequence

    @staticmethod
    def _sanitize_metadata(value: Any, limit: int) -> str:
        return " ".join(str(value or "").split())[:limit]

    @staticmethod
    def _summary_matches_binding(
        summary: HerdrTaskSummary,
        binding: HerdrTaskBinding,
    ) -> bool:
        if binding.workspace_id:
            return summary.workspace_id == binding.workspace_id
        label = (binding.workspace_label or "").strip().casefold()
        return bool(
            label
            and (summary.workspace_label or "").strip().casefold() == label
        )

    def _summarize_binding(
        self,
        binding: HerdrTaskBinding,
        workspaces: Sequence[Mapping[str, Any]],
        agents: Sequence[Mapping[str, Any]],
        captured_at: float,
    ) -> HerdrTaskSummary:
        if not binding.is_bound:
            return HerdrTaskSummary(
                task_id=binding.task_id,
                state=HerdrTaskState.NOT_BOUND,
                last_updated=captured_at,
            )

        workspace = self._resolve_workspace(binding, workspaces)
        if workspace is None:
            return HerdrTaskSummary(
                task_id=binding.task_id,
                state=HerdrTaskState.UNKNOWN,
                workspace_id=binding.workspace_id,
                workspace_label=binding.workspace_label,
                last_updated=captured_at,
                error=tr("herdr.binding_missing"),
            )

        workspace_id = str(workspace.get("workspace_id") or "")
        workspace_agents = tuple(
            agent for agent in agents if agent.get("workspace_id") == workspace_id
        )
        counts = Counter(
            str(agent.get("agent_status") or "unknown")
            for agent in workspace_agents
        )
        state = self._aggregate_state(counts, bool(workspace_agents))
        urgent = min(workspace_agents, key=self._agent_sort_key) if workspace_agents else None

        return HerdrTaskSummary(
            task_id=binding.task_id,
            state=state,
            workspace_id=workspace_id,
            workspace_label=str(workspace.get("label") or binding.workspace_label),
            workspace_focused=bool(workspace.get("focused", False)),
            agent_counts=dict(sorted(counts.items())),
            urgent_pane_id=str(urgent.get("pane_id")) if urgent and urgent.get("pane_id") else None,
            urgent_agent=str(urgent.get("agent")) if urgent and urgent.get("agent") else None,
            state_change_seq=max(
                (self._coerce_sequence(agent.get("state_change_seq")) for agent in workspace_agents),
                default=0,
            ),
            last_updated=captured_at,
        )

    @staticmethod
    def _resolve_workspace(
        binding: HerdrTaskBinding,
        workspaces: Sequence[Mapping[str, Any]],
    ) -> Optional[Mapping[str, Any]]:
        if binding.workspace_id:
            for workspace in workspaces:
                if workspace.get("workspace_id") == binding.workspace_id:
                    return workspace

        label = (binding.workspace_label or "").strip().casefold()
        if not label:
            return None
        matches = [
            workspace
            for workspace in workspaces
            if isinstance(workspace.get("label"), str)
            and workspace["label"].casefold() == label
        ]
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def _agent_sort_key(cls, agent: Mapping[str, Any]):
        status = str(agent.get("agent_status") or "unknown")
        return (
            cls._STATUS_PRIORITY.get(status, cls._STATUS_PRIORITY["unknown"]),
            -cls._coerce_sequence(agent.get("state_change_seq")),
            str(agent.get("pane_id") or ""),
        )

    @staticmethod
    def _coerce_sequence(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _aggregate_state(counts: Mapping[str, int], has_agents: bool) -> HerdrTaskState:
        if not has_agents:
            return HerdrTaskState.NOT_STARTED
        if counts.get("blocked", 0):
            return HerdrTaskState.BLOCKED
        if counts.get("working", 0):
            return HerdrTaskState.WORKING
        if counts.get("done", 0):
            return HerdrTaskState.DONE
        if counts.get("idle", 0) == sum(counts.values()):
            return HerdrTaskState.IDLE
        return HerdrTaskState.UNKNOWN


__all__ = [
    "HerdrBindingUpdate",
    "HerdrFocusResult",
    "HerdrIntegrationCoordinator",
    "HerdrMetadataResult",
    "HerdrRefreshResult",
    "HerdrTaskBinding",
    "HerdrTaskState",
    "HerdrTaskSummary",
    "HerdrTaskTransition",
]
