import json
import subprocess
from unittest.mock import patch

import pytest

from core.herdr_workspace import HerdrWorkspaceClient, HerdrWorkspaceError


def _workspace_list_output(*workspaces):
    return json.dumps({
        "id": "cli:workspace:list",
        "result": {
            "type": "workspace_list",
            "workspaces": list(workspaces),
        },
    })


def _workspace_created_output(workspace_id, label):
    return json.dumps({
        "id": "cli:workspace:create",
        "result": {
            "type": "workspace_created",
            "workspace": {
                "workspace_id": workspace_id,
                "label": label,
            },
        },
    })


def _session_snapshot_output(*, workspaces=(), agents=()):
    return json.dumps({
        "id": "cli:api:snapshot",
        "result": {
            "type": "session_snapshot",
            "snapshot": {
                "protocol": 19,
                "version": "0.8.0-test",
                "workspaces": list(workspaces),
                "agents": list(agents),
            },
        },
    })


@patch("core.herdr_workspace.subprocess.run")
def test_focus_workspace_resolves_label_to_workspace_id(run):
    run.side_effect = [
        subprocess.CompletedProcess(
            [],
            0,
            stdout=_workspace_list_output(
                {"workspace_id": "w1", "label": "stone-oasis"},
                {"workspace_id": "w3", "label": "contextSwitcher"},
            ),
            stderr="",
        ),
        subprocess.CompletedProcess([], 0, stdout="{}", stderr=""),
    ]

    workspace_id = HerdrWorkspaceClient("herdr.exe").focus_workspace("contextSwitcher")

    assert workspace_id == "w3"
    assert run.call_args_list[0].args[0] == ["herdr.exe", "workspace", "list"]
    assert run.call_args_list[1].args[0] == ["herdr.exe", "workspace", "focus", "w3"]


@patch("core.herdr_workspace.subprocess.run")
def test_focus_workspace_allows_unique_case_insensitive_match(run):
    run.side_effect = [
        subprocess.CompletedProcess(
            [],
            0,
            stdout=_workspace_list_output(
                {"workspace_id": "w3", "label": "contextSwitcher"},
            ),
            stderr="",
        ),
        subprocess.CompletedProcess([], 0, stdout="{}", stderr=""),
    ]

    workspace_id = HerdrWorkspaceClient("herdr.exe").focus_workspace("CONTEXTSWITCHER")

    assert workspace_id == "w3"


@patch("core.herdr_workspace.subprocess.run")
def test_focus_workspace_reports_available_labels_when_missing(run):
    run.return_value = subprocess.CompletedProcess(
        [],
        0,
        stdout=_workspace_list_output(
            {"workspace_id": "w1", "label": "stone-oasis"},
        ),
        stderr="",
    )

    with pytest.raises(HerdrWorkspaceError, match="当前可用: stone-oasis"):
        HerdrWorkspaceClient("herdr.exe").focus_workspace("missing")


@patch("core.herdr_workspace.subprocess.run")
def test_focus_or_create_focuses_existing_workspace(run):
    run.side_effect = [
        subprocess.CompletedProcess(
            [],
            0,
            stdout=_workspace_list_output(
                {"workspace_id": "w3", "label": "contextSwitcher"},
            ),
            stderr="",
        ),
        subprocess.CompletedProcess([], 0, stdout="{}", stderr=""),
    ]

    workspace_id = HerdrWorkspaceClient("herdr.exe").focus_or_create_workspace(
        "contextSwitcher"
    )

    assert workspace_id == "w3"
    assert run.call_args_list[1].args[0] == ["herdr.exe", "workspace", "focus", "w3"]


@patch("core.herdr_workspace.subprocess.run")
def test_focus_or_create_creates_and_focuses_missing_workspace(run):
    run.side_effect = [
        subprocess.CompletedProcess(
            [],
            0,
            stdout=_workspace_list_output(
                {"workspace_id": "w1", "label": "stone-oasis"},
            ),
            stderr="",
        ),
        subprocess.CompletedProcess(
            [],
            0,
            stdout=_workspace_created_output("w4", "new-workspace"),
            stderr="",
        ),
    ]

    workspace_id = HerdrWorkspaceClient("herdr.exe").focus_or_create_workspace(
        "new-workspace"
    )

    assert workspace_id == "w4"
    assert run.call_args_list[1].args[0] == [
        "herdr.exe",
        "workspace",
        "create",
        "--label",
        "new-workspace",
        "--focus",
    ]


def test_parse_json_output_accepts_log_lines_before_payload():
    output = "starting client\n" + _workspace_list_output(
        {"workspace_id": "w1", "label": "demo"},
    )

    payload = HerdrWorkspaceClient._parse_json_output(output)

    assert payload["result"]["workspaces"][0]["label"] == "demo"


@patch("core.herdr_workspace.subprocess.run")
def test_runtime_snapshot_uses_single_api_snapshot_command(run):
    run.return_value = subprocess.CompletedProcess(
        [],
        0,
        stdout=_session_snapshot_output(
            workspaces=({"workspace_id": "w3", "label": "ContextSwitcher"},),
            agents=({
                "workspace_id": "w3",
                "pane_id": "w3:p1",
                "agent": "codex",
                "agent_status": "working",
            },),
        ),
        stderr="",
    )

    snapshot = HerdrWorkspaceClient("herdr.exe").get_runtime_snapshot()

    assert snapshot["protocol"] == 19
    assert snapshot["workspaces"][0]["workspace_id"] == "w3"
    assert snapshot["agents"][0]["agent_status"] == "working"
    assert run.call_args.args[0] == ["herdr.exe", "api", "snapshot"]


@patch("core.herdr_workspace.subprocess.run")
def test_focus_commands_use_stable_runtime_ids(run):
    run.return_value = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
    client = HerdrWorkspaceClient("herdr.exe")

    client.focus_agent("w3:p2")
    client.focus_workspace_by_id("w3")

    assert run.call_args_list[0].args[0] == [
        "herdr.exe", "agent", "focus", "w3:p2"
    ]
    assert run.call_args_list[1].args[0] == [
        "herdr.exe", "workspace", "focus", "w3"
    ]


@patch("core.herdr_workspace.subprocess.run")
def test_workspace_metadata_commands_use_contextswitcher_owned_tokens(run):
    run.return_value = subprocess.CompletedProcess([], 0, stdout="{}", stderr="")
    client = HerdrWorkspaceClient("herdr.exe")

    client.report_workspace_metadata(
        "w3",
        {"cs_task": "Agent monitor", "cs_task_id": "task-1"},
        sequence=4,
    )
    client.clear_workspace_metadata(
        "w3",
        ("cs_task", "cs_task_id"),
        sequence=5,
    )

    assert run.call_args_list[0].args[0] == [
        "herdr.exe", "workspace", "report-metadata", "w3",
        "--source", "contextswitcher",
        "--token", "cs_task=Agent monitor",
        "--token", "cs_task_id=task-1",
        "--seq", "4",
    ]
    assert run.call_args_list[1].args[0] == [
        "herdr.exe", "workspace", "report-metadata", "w3",
        "--source", "contextswitcher",
        "--clear-token", "cs_task",
        "--clear-token", "cs_task_id",
        "--seq", "5",
    ]
