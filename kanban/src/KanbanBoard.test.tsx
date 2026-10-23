// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { KanbanBoard } from "./KanbanBoard";
import type { HerdrAgent, Project, Task, TaskStatus } from "./types";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

const project: Project = {
  id: "project-1", name: "测试项目", root_path: "E:/fixture",
  herdr_workspace: "fixture", cs_task_id: null, created_at: "2026-10-23",
};
const agent: HerdrAgent = {
  pane_id: "pane-1", name: "codex", title: "测试 Agent", status: "idle",
};
let storedTask: Task;
let availableAgents: HerdrAgent[];
const sendPrompt = vi.fn<(input: Record<string, string>) => Promise<void>>();

beforeEach(() => {
  vi.mocked(invoke).mockReset();
  storedTask = {
    id: "task-1", project_id: project.id, name: "修复拖放派发", status: "todo",
    prompt_json: JSON.stringify({ type: "doc", content: [
      { type: "paragraph", content: [{ type: "text", text: "请修复拖放派发" }] },
    ] }),
    prompt_snapshot: null, dispatched_at: null, dispatched_to: null,
    created_at: "2026-10-23", updated_at: "2026-10-23",
  };
  availableAgents = [agent];
  sendPrompt.mockReset().mockResolvedValue(undefined);
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    const input = args as Record<string, string>;
    switch (command) {
      case "list_tasks": return [{ ...storedTask }];
      case "herdr_list_agents": return availableAgents;
      case "update_task_status":
        storedTask.status = input.status as TaskStatus;
        return;
      case "dispatch_to_herdr":
        await sendPrompt(input);
        // Mirror the backend contract: only successful dispatch changes status.
        storedTask = { ...storedTask, status: "in_progress",
          dispatched_to: `${input.workspace}/${input.agentName}` };
        return;
      default: throw new Error(`Unexpected IPC command: ${command}`);
    }
  });
});

afterEach(cleanup);

async function renderBoard(status: TaskStatus = "todo") {
  storedTask.status = status;
  render(<KanbanBoard project={project} />);
  await screen.findByText(storedTask.name);
}

function column(status: TaskStatus) {
  return document.querySelector(`.col-${status}`) as HTMLElement;
}

function dropOn(target: HTMLElement, emptyTransfer = false, withDragStart = true) {
  const card = screen.getByText(storedTask.name).closest(".card-wrapper")!;
  const dataTransfer = {
    setData: vi.fn(), getData: vi.fn(() => emptyTransfer ? "" : storedTask.id),
    effectAllowed: "move",
  };
  if (withDragStart) fireEvent.dragStart(card, { dataTransfer });
  fireEvent.dragOver(target, { dataTransfer });
  fireEvent.drop(target, { dataTransfer });
  fireEvent.dragEnd(card, { dataTransfer });
}

function expectNoStatusWrite() {
  expect(vi.mocked(invoke).mock.calls.some(([command]) => command === "update_task_status")).toBe(false);
}

describe("拖入开发中列", () => {
  it("打开派发弹窗，确认前保留原列和持久化状态", async () => {
    await renderBoard();
    dropOn(column("in_progress"));
    await screen.findByRole("heading", { name: `派发任务: ${storedTask.name}` });
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    expect(storedTask.status).toBe("todo");
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("取消派发不移动任务、不发送提示词", async () => {
    await renderBoard();
    dropOn(column("in_progress"));
    fireEvent.click(await screen.findByRole("button", { name: "取消" }));
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    expect(storedTask.status).toBe("todo");
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("确认后发送到选定 Agent，仅收到成功响应后移动卡片", async () => {
    let finishDispatch!: () => void;
    sendPrompt.mockReturnValue(new Promise<void>((resolve) => { finishDispatch = resolve; }));
    await renderBoard();
    dropOn(column("in_progress"));
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: agent.pane_id } });
    const dialog = screen.getByRole("heading", { name: /派发任务:/ }).closest(".dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "派发" }));
    await waitFor(() => expect(sendPrompt).toHaveBeenCalledExactlyOnceWith({
      taskId: storedTask.id, agentName: agent.pane_id,
      workspace: project.herdr_workspace, promptText: "请修复拖放派发",
    }));
    expect(storedTask.status).toBe("todo");
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    finishDispatch();
    await waitFor(() => expect(within(column("in_progress")).getByText(storedTask.name)).toBeTruthy());
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expect(screen.getByText("fixture/pane-1")).toBeTruthy();
    expectNoStatusWrite();
  });

  it("派发失败时显示错误，保留弹窗及原任务状态", async () => {
    sendPrompt.mockRejectedValue(new Error("Agent unavailable"));
    await renderBoard();
    dropOn(column("in_progress"));
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: agent.pane_id } });
    const dialog = screen.getByRole("heading", { name: /派发任务:/ }).closest(".dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "派发" }));
    await screen.findByText("Error: Agent unavailable");
    expect(screen.getByRole("heading", { name: /派发任务:/ })).toBeTruthy();
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    expect(storedTask.status).toBe("todo");
    expectNoStatusWrite();
  });

  it("没有 Agent 时仍显示弹窗提示，不提前移动任务", async () => {
    availableAgents = [];
    await renderBoard();
    dropOn(column("in_progress"));
    await screen.findByText(/未找到 Agent/);
    const dialog = screen.getByRole("heading", { name: /派发任务:/ }).closest(".dialog") as HTMLElement;
    expect((within(dialog).getByRole("button", { name: "派发" }) as HTMLButtonElement).disabled).toBe(true);
    expect(storedTask.status).toBe("todo");
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it.each([
    ["WebView2 的 dataTransfer 为空时使用拖拽引用", true, true],
    ["没有拖拽引用时使用 dataTransfer", false, false],
  ])("%s", async (_label, emptyTransfer, withDragStart) => {
    await renderBoard();
    dropOn(column("in_progress"), emptyTransfer, withDragStart);
    await screen.findByRole("heading", { name: /派发任务:/ });
    expectNoStatusWrite();
  });

  it("已完成任务拖入开发中也需要确认派发", async () => {
    await renderBoard("done");
    dropOn(column("in_progress"));
    await screen.findByRole("heading", { name: /派发任务:/ });
    expect(within(column("done")).getByText(storedTask.name)).toBeTruthy();
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });
});

describe("保留其他拖放与派发行为", () => {
  it.each(["todo", "in_progress", "done"] as const)("拖回原列 %s 不触发派发或状态更新", async (status) => {
    await renderBoard(status);
    dropOn(column(status));
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it.each(["todo", "done"] as const)("拖到 %s 列仍直接更新状态", async (status) => {
    await renderBoard("in_progress");
    dropOn(column(status));
    await waitFor(() => expect(within(column(status)).getByText(storedTask.name)).toBeTruthy());
    expect(invoke).toHaveBeenCalledWith("update_task_status", { id: storedTask.id, status });
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("拖到 Agent 仍预选目标且等待确认", async () => {
    await renderBoard();
    dropOn(screen.getByText(agent.title).closest(".agent-chip") as HTMLElement);
    const select = await screen.findByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe(agent.pane_id);
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it.each(["todo", "in_progress"] as const)("%s 卡片上的派发按钮仍打开弹窗", async (status) => {
    await renderBoard(status);
    fireEvent.click(screen.getByRole("button", { name: status === "todo" ? "派发" : "再派发" }));
    await screen.findByRole("heading", { name: /派发任务:/ });
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });
});
