"""Herdr workspace 命令行集成。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from utils.localization import tr


class HerdrWorkspaceError(RuntimeError):
    """Herdr workspace 操作失败。"""


class HerdrWorkspaceClient:
    """通过 Herdr CLI 按显示名称定位并切换 workspace。"""

    def __init__(self, executable: str, timeout_seconds: float = 5.0):
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def resolve_executable(configured_path: str = "") -> Optional[str]:
        """解析 Herdr CLI 路径，优先使用配置，其次自动检测。"""
        configured_path = (configured_path or "").strip()
        if configured_path:
            expanded_path = os.path.expandvars(os.path.expanduser(configured_path))
            if os.path.isfile(expanded_path):
                return os.path.abspath(expanded_path)

            resolved = shutil.which(expanded_path)
            if resolved:
                return resolved
            return None

        resolved = shutil.which("herdr") or shutil.which("herdr.exe")
        if resolved:
            return resolved

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if local_app_data:
                default_path = Path(local_app_data) / "Programs" / "Herdr" / "bin" / "herdr.exe"
                if default_path.is_file():
                    return str(default_path)

        return None

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """返回 Herdr 当前会话中的 workspace 列表。"""
        completed = self._run("workspace", "list")
        payload = self._parse_json_output(completed.stdout)
        result = payload.get("result", {})
        workspaces = result.get("workspaces")
        if not isinstance(workspaces, list):
            raise HerdrWorkspaceError(tr("herdr.workspace_list_missing"))
        return [item for item in workspaces if isinstance(item, dict)]

    def get_runtime_snapshot(self) -> Dict[str, Any]:
        """返回 Herdr 当前会话的完整结构化运行态快照。"""
        completed = self._run("api", "snapshot")
        payload = self._parse_json_output(completed.stdout)
        result = payload.get("result", {})
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, dict):
            raise HerdrWorkspaceError(tr("herdr.snapshot_missing"))
        return snapshot

    def focus_agent(self, pane_id: str) -> None:
        """按 pane ID 聚焦一个已检测到的 Agent。"""
        pane_id = (pane_id or "").strip()
        if not pane_id:
            raise HerdrWorkspaceError(tr("herdr.pane_id_required"))
        self._run("agent", "focus", pane_id)

    def focus_workspace_by_id(self, workspace_id: str) -> None:
        """按稳定 ID 聚焦 workspace。"""
        workspace_id = (workspace_id or "").strip()
        if not workspace_id:
            raise HerdrWorkspaceError(tr("herdr.workspace_id_required"))
        self._run("workspace", "focus", workspace_id)

    def report_workspace_metadata(
        self,
        workspace_id: str,
        tokens: Dict[str, str],
        sequence: int,
    ) -> None:
        """Report ContextSwitcher-owned presentation tokens for a workspace."""
        arguments = [
            "workspace", "report-metadata", workspace_id,
            "--source", "contextswitcher",
        ]
        for name, value in tokens.items():
            arguments.extend(("--token", f"{name}={value}"))
        arguments.extend(("--seq", str(sequence)))
        self._run(*arguments)

    def clear_workspace_metadata(
        self,
        workspace_id: str,
        token_names: Sequence[str],
        sequence: int,
    ) -> None:
        """Clear ContextSwitcher-owned presentation tokens from a workspace."""
        arguments = [
            "workspace", "report-metadata", workspace_id,
            "--source", "contextswitcher",
        ]
        for name in token_names:
            arguments.extend(("--clear-token", name))
        arguments.extend(("--seq", str(sequence)))
        self._run(*arguments)

    def focus_workspace(self, workspace_name: str) -> str:
        """按名称切换 workspace，并返回匹配到的 workspace ID。"""
        workspace_name = (workspace_name or "").strip()
        if not workspace_name:
            raise HerdrWorkspaceError(tr("herdr.workspace_name_required"))

        workspaces = self.list_workspaces()
        match = self._find_workspace(workspaces, workspace_name)
        if match is None:
            available = ", ".join(
                str(item.get("label")) for item in workspaces if item.get("label")
            )
            if available:
                message = tr(
                    "herdr.workspace_not_found_with_available",
                    name=workspace_name,
                    available=available,
                )
            else:
                message = tr("herdr.workspace_not_found", name=workspace_name)
            raise HerdrWorkspaceError(message)

        workspace_id = self._get_workspace_id(match, workspace_name)
        self._run("workspace", "focus", workspace_id)
        return workspace_id

    def focus_or_create_workspace(self, workspace_name: str) -> str:
        """按名称聚焦 workspace；不存在时创建并立即聚焦。"""
        workspace_name = (workspace_name or "").strip()
        if not workspace_name:
            raise HerdrWorkspaceError(tr("herdr.workspace_name_required"))

        workspaces = self.list_workspaces()
        match = self._find_workspace(workspaces, workspace_name)
        if match is not None:
            workspace_id = self._get_workspace_id(match, workspace_name)
            self._run("workspace", "focus", workspace_id)
            return workspace_id

        completed = self._run(
            "workspace", "create", "--label", workspace_name, "--focus"
        )
        payload = self._parse_json_output(completed.stdout)
        result = payload.get("result", {})
        created_workspace = result.get("workspace")
        if not isinstance(created_workspace, dict):
            raise HerdrWorkspaceError(
                tr("herdr.workspace_created_without_data")
            )

        return self._get_workspace_id(created_workspace, workspace_name)

    @staticmethod
    def _find_workspace(
        workspaces: List[Dict[str, Any]], workspace_name: str
    ) -> Optional[Dict[str, Any]]:
        """优先精确匹配名称，其次进行唯一的不区分大小写匹配。"""
        exact_matches = [item for item in workspaces if item.get("label") == workspace_name]

        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            raise HerdrWorkspaceError(
                tr("herdr.workspace_duplicate", name=workspace_name)
            )

        folded_name = workspace_name.casefold()
        folded_matches = [
            item for item in workspaces
            if isinstance(item.get("label"), str)
            and item["label"].casefold() == folded_name
        ]
        if len(folded_matches) == 1:
            return folded_matches[0]
        if len(folded_matches) > 1:
            raise HerdrWorkspaceError(
                tr("herdr.workspace_duplicate", name=workspace_name)
            )
        return None

    @staticmethod
    def _get_workspace_id(workspace: Dict[str, Any], workspace_name: str) -> str:
        workspace_id = workspace.get("workspace_id")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise HerdrWorkspaceError(
                tr("herdr.workspace_id_missing", name=workspace_name)
            )
        return workspace_id

    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            completed = subprocess.run(
                [self.executable, *arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                creationflags=creationflags,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HerdrWorkspaceError(tr("herdr.command_timeout")) from exc
        except OSError as exc:
            raise HerdrWorkspaceError(tr("herdr.launch_failed", error=exc)) from exc

        if completed.returncode != 0:
            detail = (
                completed.stderr
                or completed.stdout
                or tr("herdr.unknown_error")
            ).strip()
            raise HerdrWorkspaceError(tr("herdr.command_failed", detail=detail))
        return completed

    @staticmethod
    def _parse_json_output(output: str) -> Dict[str, Any]:
        output = (output or "").strip()
        if not output:
            raise HerdrWorkspaceError(tr("herdr.workspace_data_missing"))

        candidates = [output]
        candidates.extend(reversed([line.strip() for line in output.splitlines() if line.strip()]))
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        raise HerdrWorkspaceError(tr("herdr.workspace_parse_failed"))


__all__ = ["HerdrWorkspaceClient", "HerdrWorkspaceError"]
