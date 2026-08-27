"""Qt-safe background execution for the synchronous Herdr integration seam."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from typing import Iterable, Optional

from PySide6.QtCore import QObject, Signal

from core.herdr_integration import (
    HerdrFocusResult,
    HerdrIntegrationCoordinator,
    HerdrMetadataResult,
    HerdrRefreshResult,
    HerdrTaskBinding,
)
from core.herdr_terminal import HerdrTerminalController, HerdrTerminalResult
from utils.localization import tr


class HerdrRuntimeMonitor(QObject):
    """Serialize Herdr CLI work off the GUI thread and publish Qt signals."""

    refreshed = Signal(object)
    focus_finished = Signal(object)
    metadata_finished = Signal(object)
    reveal_finished = Signal(object)

    def __init__(
        self,
        coordinator: HerdrIntegrationCoordinator,
        terminal_controller: Optional[HerdrTerminalController] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.coordinator = coordinator
        self.terminal_controller = terminal_controller
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="contextswitcher-herdr",
        )
        self._lock = threading.Lock()
        self._refresh_pending = False
        self._reveal_in_flight = False
        self._pending_reveal: Optional[HerdrTaskBinding] = None
        self._closed = False

    @property
    def is_refreshing(self) -> bool:
        with self._lock:
            return self._refresh_pending

    def request_refresh(self, bindings: Iterable[HerdrTaskBinding]) -> bool:
        """Start one snapshot refresh; reject overlapping timer ticks."""
        with self._lock:
            if self._closed or self._refresh_pending:
                return False
            self._refresh_pending = True

        future = self._executor.submit(self.coordinator.refresh, tuple(bindings))
        future.add_done_callback(self._complete_refresh)
        return True

    def request_focus(self, binding: HerdrTaskBinding) -> bool:
        """Queue a user-requested Agent/workspace focus operation."""
        return self._submit(
            self.coordinator.focus_task,
            self.focus_finished,
            binding,
            fallback=HerdrFocusResult(False, message=tr("herdr.focus_failed")),
        )

    def request_reveal(self, binding: HerdrTaskBinding) -> bool:
        """Reveal Herdr serially, coalescing queued requests to the newest task."""
        with self._lock:
            if self._closed or self.terminal_controller is None:
                return False
            if self._reveal_in_flight:
                self._pending_reveal = binding
                return True
            self._reveal_in_flight = True

        self._submit_reveal(binding)
        return True

    def request_metadata_sync(
        self,
        binding: HerdrTaskBinding,
        *,
        task_name: str,
        task_status: str,
        summary: str = "",
    ) -> bool:
        """Queue presentation-only metadata for the active task."""
        return self._submit(
            self.coordinator.sync_task_metadata,
            self.metadata_finished,
            binding,
            task_name=task_name,
            task_status=task_status,
            summary=summary,
            fallback=HerdrMetadataResult(
                False, message=tr("herdr.metadata_sync_failed")
            ),
        )

    def request_metadata_clear(self) -> bool:
        """Clear ContextSwitcher-owned metadata from the former active workspace."""
        return self._submit(
            self.coordinator.clear_active_metadata,
            self.metadata_finished,
            fallback=HerdrMetadataResult(
                False, message=tr("herdr.metadata_clear_failed")
            ),
        )

    def _submit(self, operation, signal, *args, fallback, **kwargs) -> bool:
        with self._lock:
            if self._closed:
                return False
        future = self._executor.submit(operation, *args, **kwargs)
        future.add_done_callback(
            lambda completed: self._emit_future(completed, signal, fallback)
        )
        return True

    def _complete_refresh(self, future: Future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = HerdrRefreshResult(
                summaries=(),
                available=False,
                error=str(exc) or exc.__class__.__name__,
            )
        with self._lock:
            self._refresh_pending = False
            closed = self._closed
        if not closed:
            self.refreshed.emit(result)

    def _submit_reveal(self, binding: HerdrTaskBinding) -> None:
        if self.terminal_controller is None:
            return
        future = self._executor.submit(self.terminal_controller.reveal_task, binding)
        future.add_done_callback(
            lambda completed: self._complete_reveal(completed, binding)
        )

    def _complete_reveal(
        self,
        future: Future,
        binding: HerdrTaskBinding,
    ) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = HerdrTerminalResult(
                False,
                binding.task_id,
                workspace_id=binding.workspace_id,
                workspace_label=binding.workspace_label,
                message=str(exc) or tr("main.messages.herdr_terminal_failed"),
            )

        with self._lock:
            closed = self._closed
            next_binding = self._pending_reveal
            self._pending_reveal = None
            forwarded_result = None
            startup_timed_out = (
                not result.success
                and result.launched
                and result.hwnd is None
            )
            if next_binding is not None and startup_timed_out:
                forwarded_result = replace(
                    result,
                    task_id=next_binding.task_id,
                    workspace_id=next_binding.workspace_id,
                    workspace_label=next_binding.workspace_label,
                )
                next_binding = None
            if closed or next_binding is None:
                self._reveal_in_flight = False

        if not closed:
            self.reveal_finished.emit(result)
            if forwarded_result is not None:
                self.reveal_finished.emit(forwarded_result)
        if not closed and next_binding is not None:
            self._submit_reveal(next_binding)

    def _emit_future(self, future: Future, signal, fallback) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = type(fallback)(False, message=str(exc) or fallback.message)
        with self._lock:
            closed = self._closed
        if not closed:
            signal.emit(result)

    def shutdown(self, wait: bool = False) -> None:
        """Stop accepting work and cancel operations that have not started."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)


__all__ = ["HerdrRuntimeMonitor"]
