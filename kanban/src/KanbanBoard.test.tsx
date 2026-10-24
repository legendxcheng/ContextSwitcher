// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { KanbanBoard } from "./KanbanBoard";
import App from "./App";
import type { HerdrAgent, Project, Task, TaskStatus } from "./types";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(), Channel: class { onmessage = () => {}; } }));
const flowEvents = vi.hoisted(() => new Set<(event: { payload: { project_id: string; task_id: string; operation_id: string } }) => void>());
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async (_name, callback) => {
  flowEvents.add(callback);
  return () => { flowEvents.delete(callback); };
}) }));
const terminalSize = vi.hoisted(() => ({ cols: 80, rows: 24 }));
// The terminal renderer is an external DOM/canvas system, simulated at that boundary.
vi.mock("@xterm/xterm", () => ({ Terminal: class {
  get cols() { return terminalSize.cols; } get rows() { return terminalSize.rows; }
  options = {}; textarea = document.createElement("textarea");
  open(element: HTMLElement) { this.textarea.setAttribute("aria-label", "终端输入"); element.append(this.textarea); }
  loadAddon() {} write(_data: unknown, done?: () => void) { done?.(); }
  onData(callback: (data: string) => void) { this.textarea.oninput = () => callback(this.textarea.value); return { dispose() {} }; }
  onResize() { return { dispose() {} }; } attachCustomKeyEventHandler() {} focus() { this.textarea.focus(); }
  dispose() { this.textarea.remove(); }
} }));
vi.mock("@xterm/addon-fit", () => ({ FitAddon: class { fit() {} } }));
vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });

const project: Project = {
  id: "project-1", name: "测试项目", root_path: "E:/fixture",
  herdr_workspace: "fixture", cs_task_id: null, created_at: "2026-10-23",
  herdr_session: "default", workspace_id: "w1", sync_status: "ready", directory_source: "herdr", herdr_directory: "E:/fixture",
};
const agent: HerdrAgent = {
  pane_id: "pane-1", name: "codex", title: "测试 Agent", status: "idle",
};

it("synchronizes Herdr workspaces on focus while retaining local tasks on failure", async () => {
  let offline = false;
  const original = vi.mocked(invoke).getMockImplementation()!;
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    if (command === "list_projects") return [project];
    if (command === "sync_projects") {
      if (offline) throw new Error("herdr.unavailable");
      return { projects: [{ ...project, name: "Synced name" }], workspaces: [], operations: [] };
    }
    if (command === "workspace_operations") return [];
    return original(command, args);
  });
  render(<App />);
  await screen.findByRole("button", { name: /^Synced name/ });
  offline = true;
  fireEvent(window, new Event("focus"));
  await screen.findByText(/同步失败/);
  expect(screen.getByText("修复拖放派发")).toBeTruthy();
});
let storedTask: Task;
let availableAgents: HerdrAgent[];
let extraTasks: Task[];
let deleted: boolean;
const sendPrompt = vi.fn<(input: Record<string, string>) => Promise<void>>();

beforeEach(() => {
  flowEvents.clear();
  terminalSize.cols = 80; terminalSize.rows = 24;
  vi.mocked(invoke).mockReset();
  storedTask = {
    id: "task-1", project_id: project.id, name: "修复拖放派发", status: "todo", priority: "normal", archived_at: null, cleanup_required: false,
    prompt_json: JSON.stringify({ type: "doc", content: [
      { type: "paragraph", content: [{ type: "text", text: "请修复拖放派发" }] },
    ] }),
    prompt_snapshot: null, dispatched_at: null, dispatched_to: null,
    created_at: "2026-10-23", updated_at: "2026-10-23",
  };
  availableAgents = [agent];
  extraTasks = [];
  deleted = false;
  sendPrompt.mockReset().mockResolvedValue(undefined);
  vi.mocked(invoke).mockImplementation(async (command, args) => {
    const input = args as Record<string, string>;
    switch (command) {
      case "list_projects": return [];
      case "list_tasks": return [...(deleted ? [] : [{ ...storedTask }]), ...extraTasks];
      case "delete_task": deleted = true; return;
      case "archive_task": deleted = true; return;
      case "create_task": {
        const task = { ...storedTask, id: "new-task", name: input.name, prompt_json: input.promptJson, priority: input.priority };
        extraTasks.push(task as Task);
        return task;
      }
      case "update_task": {
        const task = input.id === storedTask.id ? storedTask : extraTasks.find((t) => t.id === input.id)!;
        task.name = input.name; task.prompt_json = input.promptJson; task.priority = input.priority as Task["priority"]; return;
      }
      case "herdr_list_agents": return availableAgents;
      case "complete_task": storedTask.status = "done"; return {};
      case "start_task":
        await sendPrompt(input);
        storedTask.status = "in_progress"; bindTask();
        storedTask.flow = { session_id: null, operation_id: input.operationId, kind: "start", state: "succeeded", error: "", pane_id: "pane-1" };
        return storedTask.flow;
      case "update_task_status":
        storedTask.status = input.status as TaskStatus;
        return;
      case "resolve_dispatch":
        storedTask.binding = { state: "valid", target: storedTask.binding?.target ?? null, operation: null };
        return;
      case "repair_binding": storedTask.binding = { state: "valid", target: null, operation: null }; return;
      case "terminal_open": return input.connectionId;
      case "terminal_close": case "terminal_input": case "terminal_resize": case "terminal_ack": return;
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

describe("任务优先级", () => {
  it("保存中锁定表单且只提交一次，失败保留完整草稿并可重试", async () => {
    const base = vi.mocked(invoke).getMockImplementation()!;
    let rejectSave!: (error: Error) => void;
    vi.mocked(invoke).mockImplementation((command, args, options) => command === "create_task"
      ? new Promise((_resolve, reject) => { rejectSave = reject; }) : base(command, args, options));
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    const dialog = screen.getByRole("dialog", { name: "新建任务" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "标题" }), { target: { value: "保留全部输入" } });
    fireEvent.paste(within(dialog).getByRole("textbox", { name: "提示词" }), {
      clipboardData: { getData: (type: string) => type === "text/plain" ? "失败也不能丢失正文" : "", files: [] },
    });
    fireEvent.change(within(dialog).getByRole("combobox"), { target: { value: "high" } });
    const save = within(dialog).getByRole("button", { name: "添加任务" });
    fireEvent.click(save); fireEvent.submit(dialog);
    fireEvent.keyDown(save, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(within(dialog).getByRole("textbox", { name: "提示词" }).getAttribute("contenteditable")).toBe("false");
    expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === "create_task")).toHaveLength(1);
    rejectSave(new Error("保存失败"));
    await screen.findByRole("alert");
    expect(document.activeElement).toBe(within(dialog).getByRole("textbox", { name: "标题" }));
    expect((within(dialog).getByRole("textbox", { name: "标题" }) as HTMLInputElement).value).toBe("保留全部输入");
    expect(within(dialog).getByRole("textbox", { name: "提示词" }).textContent).toBe("失败也不能丢失正文");
    expect((within(dialog).getByRole("combobox") as HTMLSelectElement).value).toBe("high");
    vi.mocked(invoke).mockImplementation(base);
    fireEvent.click(save);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByText("保留全部输入")).toBeTruthy();
  });

  it("新建一次保存标题、提示词和优先级，关闭后重新编辑可读回", async () => {
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    const dialog = screen.getByRole("dialog", { name: "新建任务" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "标题" }), { target: { value: "完整任务" } });
    const prompt = within(dialog).getByRole("textbox", { name: "提示词" });
    fireEvent.paste(prompt, { clipboardData: { getData: (type: string) => type === "text/plain" ? "请检查新建表单" : "", files: [] } });
    fireEvent.change(within(dialog).getByRole("combobox", { name: "优先级" }), { target: { value: "urgent" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "添加任务" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const card = (await screen.findByText("完整任务")).closest(".task-card")! as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "编辑" }));
    const edit = screen.getByRole("dialog", { name: "编辑任务" });
    expect((within(edit).getByRole("textbox", { name: "标题" }) as HTMLInputElement).value).toBe("完整任务");
    expect(within(edit).getByRole("textbox", { name: "提示词" }).textContent).toBe("请检查新建表单");
    expect((within(edit).getByRole("combobox", { name: "优先级" }) as HTMLSelectElement).value).toBe("urgent");
  });

  it("快捷键只打开顶部新建表单，取消不创建，创建失败保留输入", async () => {
    const base = vi.mocked(invoke).getMockImplementation()!;
    vi.mocked(invoke).mockImplementation((command, args, options) => command === "create_task"
      ? Promise.reject(new Error("数据库写入失败")) : base(command, args, options));
    await renderBoard();
    fireEvent.keyDown(document, { key: "n" });
    const dialog = screen.getByRole("dialog", { name: "新建任务" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "标题" }), { target: { value: "保留草稿" } });
    fireEvent.change(within(dialog).getByRole("combobox", { name: "优先级" }), { target: { value: "high" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "添加任务" }));
    await screen.findByRole("alert");
    expect((within(dialog).getByRole("textbox", { name: "标题" }) as HTMLInputElement).value).toBe("保留草稿");
    expect((within(dialog).getByRole("combobox") as HTMLSelectElement).value).toBe("high");
    fireEvent.click(within(dialog).getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(extraTasks).toHaveLength(0);
  });

  it("新建时保存紧急优先级，编辑可修改，下一次新建恢复一般", async () => {
    await renderBoard();
    expect(screen.queryByRole("textbox", { name: "标题" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "标题" }), { target: { value: "紧急故障" } });
    fireEvent.change(screen.getByRole("combobox", { name: "优先级" }), { target: { value: "urgent" } });
    fireEvent.click(screen.getByRole("button", { name: "添加任务" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const card = (await screen.findByText("紧急故障")).closest(".task-card")! as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "编辑" }));
    const editor = screen.getByRole("dialog", { name: "编辑任务" });
    const priority = within(editor).getByRole("combobox", { name: "优先级" });
    expect((priority as HTMLSelectElement).value).toBe("urgent");
    fireEvent.change(priority, { target: { value: "high" } });
    fireEvent.click(within(editor).getByRole("button", { name: "保存" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "编辑任务" })).toBeNull());
    expect(extraTasks[0].priority).toBe("high");
    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    expect((screen.getByRole("combobox", { name: "优先级" }) as HTMLSelectElement).value).toBe("normal");
  });
});

describe("紧凑卡片与归档", () => {
  it("从编辑图标按下拖动不会开始任务拖拽", async () => {
    await renderBoard();
    const edit = screen.getByRole("button", { name: "编辑" });
    const transfer = { setData: vi.fn(), effectAllowed: "none" };
    fireEvent.pointerDown(edit);
    const accepted = fireEvent.dragStart(edit.closest(".card-wrapper")!, { dataTransfer: transfer });
    expect(accepted).toBe(false);
    expect(transfer.setData).not.toHaveBeenCalled();
  });

  it("归档成功后即使列表刷新失败也移除卡片并更新统计", async () => {
    const base = vi.mocked(invoke).getMockImplementation()!;
    vi.mocked(invoke).mockImplementation((command, args, options) => command === "list_tasks" && deleted
      ? Promise.reject(new Error("列表暂时不可用")) : base(command, args, options));
    await renderBoard("done");
    fireEvent.click(screen.getByRole("button", { name: "归档" }));
    await waitFor(() => expect(screen.queryByText(storedTask.name)).toBeNull());
    expect(await screen.findByText("0 / 0 已完成")).toBeTruthy();
  });

  it("卡片不显示时间、修复绑定或再派发，保留图标编辑与完整标题", async () => {
    bindTask();
    storedTask.dispatched_to = "workspace/target";
    storedTask.dispatched_at = "2026-10-24T12:00:00Z";
    await renderBoard("in_progress");
    const card = screen.getByRole("button", { name: `查看终端：${storedTask.name}` }).closest(".task-card") as HTMLElement;
    expect(within(card).queryByText(/2026/)).toBeNull();
    expect(within(card).queryByRole("button", { name: "修复绑定" })).toBeNull();
    expect(within(card).queryByRole("button", { name: "再派发" })).toBeNull();
    expect(within(card).getByRole("button", { name: "编辑" }).textContent).toBe("");
    expect(within(card).getByTitle(storedTask.name)).toBeTruthy();
    expect(within(card).getByTitle("派发至 workspace/target")).toBeTruthy();
    expect(within(card).queryByRole("button", { name: "归档" })).toBeNull();
  });

  it("归档提交防重复，失败保留卡片并允许重试，不弹确认", async () => {
    const base = vi.mocked(invoke).getMockImplementation()!;
    let rejectArchive!: (reason: Error) => void;
    const confirm = vi.spyOn(window, "confirm");
    vi.mocked(invoke).mockImplementation((command, args, options) => command === "archive_task"
      ? new Promise((_resolve, reject) => { rejectArchive = reject; }) : base(command, args, options));
    await renderBoard("done");
    const archive = screen.getByRole("button", { name: "归档" });
    fireEvent.click(archive); fireEvent.click(archive);
    expect(vi.mocked(invoke).mock.calls.filter(([cmd]) => cmd === "archive_task")).toHaveLength(1);
    expect(archive.matches(":disabled")).toBe(true);
    rejectArchive(new Error("保存失败"));
    expect((await screen.findByRole("alert")).textContent).toContain("保存失败");
    expect(screen.getByText(storedTask.name)).toBeTruthy();
    expect(archive.matches(":disabled")).toBe(false);
    expect(confirm).not.toHaveBeenCalled(); confirm.mockRestore();
  });

  it("后续启动失败不会隐藏完成清理问题，归档禁用且可重试清理", async () => {
    storedTask.cleanup_required = true;
    storedTask.flow = { session_id: null, operation_id: "restart", kind: "start", state: "failed", error: "binding.identity_changed", pane_id: "p1" };
    await renderBoard("done");
    const archive = screen.getByRole("button", { name: "归档" });
    expect(archive.matches(":disabled")).toBe(true);
    expect(screen.getByText("请先完成窗口清理再归档")).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试关闭窗口" })).toBeTruthy();
    fireEvent.click(archive);
    expect(vi.mocked(invoke).mock.calls.some(([cmd]) => cmd === "archive_task")).toBe(false);
  });

  it("已完成任务点击归档后消失并更新数量，不派发或连接终端", async () => {
    await renderBoard("done");
    expect(screen.getByText("1 / 1 已完成")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "归档" }));
    await waitFor(() => expect(screen.queryByText(storedTask.name)).toBeNull());
    expect(screen.getByText("0 / 0 已完成")).toBeTruthy();
    expect(invoke).toHaveBeenCalledWith("archive_task", { id: storedTask.id });
    expect(sendPrompt).not.toHaveBeenCalled();
    expect(vi.mocked(invoke).mock.calls.some(([cmd]) => cmd === "terminal_open")).toBe(false);
  });
});

async function renderBoard(status: TaskStatus = "todo") {
  storedTask.status = status;
  render(<KanbanBoard project={project} />);
  await screen.findByText(storedTask.name, { selector: ".task-name" });
}

function column(status: TaskStatus) {
  return document.querySelector(`.col-${status}`) as HTMLElement;
}

function dropOn(target: HTMLElement, emptyTransfer = false, withDragStart = true) {
  const card = screen.getAllByText(storedTask.name).find(element => element.closest(".card-wrapper"))!.closest(".card-wrapper")!;
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

function bindTask() {
  storedTask.binding = { state: "valid", operation: null, target: {
    session: "default", workspace_id: "w1", pane_id: "w1:p1", terminal_id: "term1",
    agent: "codex", process_id: "100", title: "A", status: "idle",
  } };
}

function secondTask(): Task {
  return { ...storedTask, id: "task-2", name: "任务 B", status: "in_progress",
    binding: { state: "valid", operation: null, target: { ...storedTask.binding!.target!, pane_id: "w1:p2", terminal_id: "term2" } } };
}

describe("默认终端与任务选择", () => {
  it("启动自动选择第一张开发中任务，手动选择后刷新不抢回或重连", async () => {
    bindTask();
    extraTasks = [secondTask()];
    await renderBoard("in_progress");
    await screen.findByText("已连接");
    expect(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "查看终端：任务 B" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("terminal_open", expect.objectContaining({ taskId: "task-2" })));
    const opened = vi.mocked(invoke).mock.calls.filter(([name]) => name === "terminal_open").length;
    fireEvent.click(within(column("in_progress")).getAllByRole("button", { name: "编辑" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: "保存" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "保存" })).toBeNull());
    expect(screen.getByRole("button", { name: "查看终端：任务 B" }).getAttribute("aria-pressed")).toBe("true");
    expect(vi.mocked(invoke).mock.calls.filter(([name]) => name === "terminal_open")).toHaveLength(opened);
    expect(sendPrompt).not.toHaveBeenCalled();
    expectNoStatusWrite();
  });

  it.each(["done", "todo", "delete"])("选中任务变为 %s 后释放旧连接并选择下一张", async (action) => {
    bindTask(); extraTasks = [secondTask()];
    await renderBoard("in_progress");
    await screen.findByText("已连接");
    const firstOpen = vi.mocked(invoke).mock.calls.find(([name]) => name === "terminal_open")![1] as { connectionId: string };
    if (action === "delete") {
      const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
      fireEvent.click(within(column("in_progress")).getAllByRole("button", { name: "删除" })[0]);
      confirm.mockRestore();
    } else dropOn(column(action as TaskStatus));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("terminal_open", expect.objectContaining({ taskId: "task-2" })));
    expect(invoke).toHaveBeenCalledWith("terminal_close", { connectionId: firstOpen.connectionId });
    expect(screen.getByRole("button", { name: "查看终端：任务 B" }).getAttribute("aria-pressed")).toBe("true");
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("最后一张开发中任务完成后保留空终端", async () => {
    bindTask(); await renderBoard("in_progress"); await screen.findByText("已连接");
    fireEvent.click(screen.getByRole("button", { name: "标记完成" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("暂无开发中的任务"));
    expect(screen.getByRole("complementary", { name: "Herdr 终端" })).toBeTruthy();
    expect(screen.queryByLabelText("终端输入")).toBeNull();
    expect(vi.mocked(invoke).mock.calls.some(([name]) => name === "terminal_close")).toBe(true);
  });

  it("加载期间和没有开发中任务时保留空终端，不连接或派发", async () => {
    const base = vi.mocked(invoke).getMockImplementation()!;
    let finish!: (tasks: Task[]) => void;
    vi.mocked(invoke).mockImplementation((command, args, options) => command === "list_tasks"
      ? new Promise((resolve) => { finish = resolve; }) : base(command, args, options));
    render(<KanbanBoard project={project} />);
    expect(screen.getByText("加载中…")).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Herdr 终端" })).toBeTruthy();
    finish([storedTask]);
    await screen.findByText(storedTask.name, { selector: ".task-name" });
    expect(screen.getByRole("status").textContent).toBe("暂无开发中的任务");
    expect(vi.mocked(invoke).mock.calls.some(([name]) => name === "terminal_open")).toBe(false);
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("首张任务绑定异常仍选中并展示修复入口，不跳到后续任务", async () => {
    bindTask(); extraTasks = [secondTask()]; storedTask.binding = { state: "repair", operation: null, target: null };
    await renderBoard("in_progress");
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("请先修复任务绑定"));
    expect(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }).getAttribute("aria-pressed")).toBe("true");
    expect(vi.mocked(invoke).mock.calls.some(([name]) => name === "terminal_open")).toBe(false);
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("没有项目时仍显示空终端", async () => {
    render(<App />);
    await screen.findByText("从一个项目，开始推进。");
    expect(screen.getByRole("complementary", { name: "Herdr 终端" })).toBeTruthy();
    expect(vi.mocked(invoke).mock.calls.some(([name]) => name === "terminal_open")).toBe(false);
  });

  it("切项目自动选择新项目任务并释放原连接", async () => {
    bindTask(); storedTask.status = "in_progress";
    const other = { ...project, id: "project-2", name: "第二项目" };
    const taskB = { ...secondTask(), project_id: other.id };
    const base = vi.mocked(invoke).getMockImplementation()!;
    vi.mocked(invoke).mockImplementation((command, args, options) => {
      if (command === "list_projects") return Promise.resolve([project, other]);
      if (command === "list_tasks" && (args as { projectId: string }).projectId === other.id) return Promise.resolve([taskB]);
      return base(command, args, options);
    });
    render(<App />); await screen.findByText("已连接");
    const first = vi.mocked(invoke).mock.calls.find(([name]) => name === "terminal_open")![1] as { connectionId: string };
    fireEvent.click(screen.getByRole("button", { name: /^第二项目\s*E:\/fixture$/ }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("terminal_open", expect.objectContaining({ taskId: taskB.id })));
    expect(invoke).toHaveBeenCalledWith("terminal_close", { connectionId: first.connectionId });
    expect(screen.getByRole("button", { name: "查看终端：任务 B" }).getAttribute("aria-pressed")).toBe("true");
  });
});

describe("拖入开发中列", () => {
  it("连接等待期间改变终端尺寸，连接成功后同步最新尺寸", async () => {
    storedTask.binding = { state: "valid", operation: null, target: {
      session: "default", workspace_id: "w1", pane_id: "w1:p1", terminal_id: "term1", agent: "codex", process_id: "100", title: "A", status: "idle",
    } };
    const base = vi.mocked(invoke).getMockImplementation()!;
    let connected!: (value: string) => void;
    let connectionId = "";
    vi.mocked(invoke).mockImplementation((command, args, options) => {
      if (command === "terminal_open") {
        connectionId = (args as Record<string, string>).connectionId;
        return new Promise((resolve) => { connected = resolve; });
      }
      return base(command, args, options);
    });
    await renderBoard("in_progress");
    fireEvent.click(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }));
    await screen.findByText("连接中…");
    expect(invoke).toHaveBeenCalledWith("terminal_open", expect.objectContaining({ cols: 80, rows: 24 }));
    terminalSize.cols = 100; terminalSize.rows = 30;
    connected(connectionId);
    await screen.findByText("已连接");
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("terminal_resize", { connectionId, cols: 100, rows: 30 }));
  });
  it("快速切换后迟到的旧连接不能接收新任务的输入", async () => {
    const target = { session: "default", workspace_id: "w1", pane_id: "w1:p1", terminal_id: "term1", agent: "codex", process_id: "100", title: "A", status: "idle" };
    storedTask.binding = { state: "valid", operation: null, target };
    extraTasks = [{ ...storedTask, id: "task-2", name: "任务 B", status: "in_progress", binding: { state: "valid", operation: null, target: { ...target, pane_id: "w1:p2", terminal_id: "term2" } } }];
    const base = vi.mocked(invoke).getMockImplementation()!;
    let finishA!: (value: string) => void;
    let idA = ""; let idB = "";
    vi.mocked(invoke).mockImplementation((command, args, options) => {
      const input = args as Record<string, string>;
      if (command === "terminal_open") {
        if (input.taskId === "task-1") { idA = input.connectionId; return new Promise((resolve) => { finishA = resolve; }); }
        idB = input.connectionId;
      }
      return base(command, args, options);
    });
    await renderBoard("in_progress");
    fireEvent.click(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }));
    await screen.findByText("连接中…");
    fireEvent.click(screen.getByRole("button", { name: "查看终端：任务 B" }));
    await screen.findByText("已连接");
    finishA(idA);
    fireEvent.input(screen.getByLabelText("终端输入"), { target: { value: "only B" } });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("terminal_input", { connectionId: idB, data: "only B" }));
    expect(invoke).toHaveBeenCalledWith("terminal_close", { connectionId: idA });
    expect(vi.mocked(invoke).mock.calls.some(([name, args]) => name === "terminal_input" && (args as Record<string, string>).connectionId === idA)).toBe(false);
  });
  it("可通过分隔线键盘调整终端宽度", async () => {
    await renderBoard();
    const separator = screen.getByRole("separator", { name: "调整终端宽度" });
    const initial = Number(separator.getAttribute("aria-valuenow"));
    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    expect(Number(separator.getAttribute("aria-valuenow"))).toBe(initial + 24);
  });
  it("旧绑定可以明确修复，修复本身不派发提示词", async () => {
    storedTask.binding = { state: "repair", target: null, operation: null };
    await renderBoard("in_progress");
    fireEvent.click(within(screen.getByRole("complementary", { name: "Herdr 终端" })).getByRole("button", { name: "修复绑定" }));
    fireEvent.change(await screen.findByLabelText("独立 Agent"), { target: { value: agent.pane_id } });
    fireEvent.click(screen.getByRole("button", { name: "保存绑定" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("repair_binding", { taskId: "task-1", paneId: agent.pane_id }));
    expect(sendPrompt).not.toHaveBeenCalled();
  });
  it("选择开发中卡片连接其终端，编辑按钮不会触发重复连接", async () => {
    storedTask.binding = { state: "valid", operation: null, target: {
      session: "default", workspace_id: "w1", pane_id: "w1:p1", terminal_id: "term1",
      agent: "codex", process_id: "100", title: "A", status: "idle",
    } };
    await renderBoard("in_progress");
    fireEvent.click(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }));
    await screen.findByText("已连接");
    expect(invoke).toHaveBeenCalledWith("terminal_open", expect.objectContaining({ taskId: "task-1", connectionId: expect.any(String) }));
    const opened = vi.mocked(invoke).mock.calls.filter(([name]) => name === "terminal_open").length;
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    expect(vi.mocked(invoke).mock.calls.filter(([name]) => name === "terminal_open")).toHaveLength(opened);
    expect(sendPrompt).not.toHaveBeenCalled();
  });
  it("核实未知派发结果只记录确认，不重发提示词", async () => {
    storedTask.binding = { state: "unknown", target: null, operation: {
      id: "op-1", prompt: "一次任务", created_at: "2026-10-24", target: {
        session: "default", workspace_id: "w1", pane_id: "w1:p1", terminal_id: "term1",
        agent: "codex", process_id: "100", title: "A", status: "idle",
      },
    } };
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "核实派发结果" }));
    fireEvent.change(screen.getByLabelText("核实依据"), { target: { value: "已在目标终端确认收到" } });
    fireEvent.click(screen.getByRole("button", { name: "确认已发送" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("resolve_dispatch", {
      taskId: "task-1", operationId: "op-1", sent: true, evidence: "已在目标终端确认收到",
    }));
    expect(sendPrompt).not.toHaveBeenCalled();
  });
  it("其他任务占用的 Agent 不可选择，不能派发", async () => {
    availableAgents = [{ ...agent, occupied_by: "another-task" }];
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    const option = await screen.findByRole("option", { name: /已被其他任务占用/ });
    expect((option as HTMLOptionElement).disabled).toBe(true);
    expect(sendPrompt).not.toHaveBeenCalled();
  });
  it("打开派发弹窗，确认前保留原列和持久化状态", async () => {
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    await screen.findByRole("heading", { name: `派发任务: ${storedTask.name}` });
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    expect(storedTask.status).toBe("todo");
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("取消派发不移动任务、不发送提示词", async () => {
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
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
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    fireEvent.change(await screen.findByRole("combobox", { name: "独立 Agent" }), { target: { value: agent.pane_id } });
    const dialog = screen.getByRole("heading", { name: /派发任务:/ }).closest(".dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "派发" }));
    await waitFor(() => expect(sendPrompt).toHaveBeenCalledExactlyOnceWith({
      taskId: storedTask.id, agentName: agent.pane_id,
      workspace: project.herdr_workspace, promptText: "请修复拖放派发",
      operationId: expect.any(String),
    }));
    expect(storedTask.status).toBe("todo");
    expect(within(column("todo")).getByText(storedTask.name)).toBeTruthy();
    finishDispatch();
    await waitFor(() => expect(within(column("in_progress")).getByText(storedTask.name)).toBeTruthy());
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expect(screen.getByTitle("派发至 fixture/pane-1")).toBeTruthy();
    expect(screen.getByRole("button", { name: `查看终端：${storedTask.name}` }).getAttribute("aria-pressed")).toBe("true");
    expectNoStatusWrite();
  });

  it("派发失败时显示错误，保留弹窗及原任务状态", async () => {
    sendPrompt.mockRejectedValue(new Error("Agent unavailable"));
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    fireEvent.change(await screen.findByRole("combobox", { name: "独立 Agent" }), { target: { value: agent.pane_id } });
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
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
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
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("start_task", expect.objectContaining({ taskId: storedTask.id })));
    expectNoStatusWrite();
  });

  it("已完成任务恢复不发送原提示词，也不读取已失效引用", async () => {
    storedTask.flow = { session_id: "saved-id", operation_id: null, kind: null, state: null, error: "", pane_id: null };
    storedTask.prompt_json = "invalid old JSON";
    await renderBoard("done");
    dropOn(column("in_progress"));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("start_task", { taskId: storedTask.id, operationId: expect.any(String) }));
    expect(vi.mocked(invoke).mock.calls.some(([command]) => command === "read_file_content")).toBe(false);
    await screen.findByText("已连接");
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expectNoStatusWrite();
  });
  it("首次拖入立即自动分配，不重复提交快速拖拽", async () => {
    let finish!: () => void;
    sendPrompt.mockReturnValue(new Promise<void>((resolve) => { finish = resolve; }));
    availableAgents = [];
    await renderBoard();
    dropOn(column("in_progress"));
    dropOn(column("in_progress"));
    await waitFor(() => expect(sendPrompt).toHaveBeenCalledTimes(1));
    expect(invoke).toHaveBeenCalledWith("start_task", { taskId: storedTask.id, operationId: expect.any(String) });
    expect(storedTask.status).toBe("todo");
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    finish();
    await screen.findByText("已连接");
    expect(within(column("in_progress")).getByText(storedTask.name)).toBeTruthy();
  });
  it("自动启动失败保留原列并显示错误", async () => {
    sendPrompt.mockRejectedValue(new Error("herdr.unavailable"));
    await renderBoard(); dropOn(column("in_progress"));
    await screen.findByRole("alert");
    expect(storedTask.status).toBe("todo");
    expect(screen.getByRole("alert").textContent).toContain("无法启动 Herdr");
  });
  it("完成清理失败仍刷新到完成列并显示重试", async () => {
    bindTask();
    const base = vi.mocked(invoke).getMockImplementation()!;
    vi.mocked(invoke).mockImplementation(async (command, args, options) => {
      if (command === "complete_task") {
        storedTask.status = "done";
        storedTask.cleanup_required = true;
        storedTask.flow = { session_id: null, operation_id: "close", kind: "complete", state: "failed", error: "flow.session_missing", pane_id: "w1:p1" };
        return { warning: "flow.session_missing" };
      }
      return base(command, args, options);
    });
    await renderBoard("in_progress");
    fireEvent.click(screen.getByRole("button", { name: "标记完成" }));
    await screen.findByRole("button", { name: "重试关闭窗口" });
    expect(within(column("done")).getByText(storedTask.name)).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("任务已完成");
  });
});

describe("保留其他拖放与派发行为", () => {
  it("启动仍未返回时卡片立即进入开发中且不阻塞新建任务", async () => {
    sendPrompt.mockReturnValue(new Promise(() => {}));
    await renderBoard();
    dropOn(column("in_progress"));
    expect(within(column("in_progress")).getByText(storedTask.name)).toBeTruthy();
    expect(screen.getAllByText("窗口准备中…").length).toBeGreaterThan(0);
    expect(vi.mocked(invoke).mock.calls.some(([command]) => command === "terminal_open")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: /新建任务/ }));
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("受理后重新进入看板保留准备状态，就绪通知不抢回手动选择", async () => {
    const original = vi.mocked(invoke).getMockImplementation()!;
    vi.mocked(invoke).mockImplementation(async (command, args, options) => {
      if (command === "start_task") {
        const input = args as { operationId: string };
        storedTask.flow = { session_id: null, operation_id: input.operationId, kind: "start", state: "pending",
          error: "", pane_id: null, requested_status: "in_progress", stage: "starting_agent" };
        return storedTask.flow;
      }
      return original(command, args, options);
    });
    await renderBoard();
    dropOn(column("in_progress"));
    await screen.findAllByText("正在启动或恢复 Agent…");
    cleanup();
    bindTask();
    extraTasks = [{ ...storedTask, id: "other", name: "其他任务", status: "in_progress", flow: null }];
    storedTask.binding = null;
    await renderBoard();
    expect(within(column("in_progress")).getByText(storedTask.name)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "修复绑定" })).toBeNull();
    expect(screen.queryByRole("button", { name: "派发" })).toBeNull();
    fireEvent.click(screen.getByText("其他任务"));
    await screen.findByText("已连接");
    bindTask(); storedTask.status = "in_progress"; storedTask.flow!.state = "succeeded";
    await act(async () => { for (const callback of flowEvents) callback({ payload: {
      project_id: project.id, task_id: storedTask.id, operation_id: storedTask.flow!.operation_id!
    } }); });
    await waitFor(() => expect(screen.getByRole("complementary").querySelector("strong")!.textContent).toBe("其他任务"));
    expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === "start_task")).toHaveLength(1);
  });

  it("恢复焦点补查遗漏的启动完成事件并自动连接当前任务", async () => {
    storedTask.flow = { session_id: null, operation_id: "pending-start", kind: "start", state: "pending",
      error: "", pane_id: null, stage: "queued", requested_status: "in_progress" };
    await renderBoard();
    expect(screen.getAllByText("窗口准备中…").length).toBeGreaterThan(0);
    bindTask(); storedTask.status = "in_progress"; storedTask.flow.state = "succeeded";
    fireEvent(window, new Event("focus"));
    await screen.findByText("已连接");
    expect(vi.mocked(invoke).mock.calls.filter(([command]) => command === "start_task")).toHaveLength(0);
  });

  it("预览和派发都保留技能调用，不读取技能正文", async () => {
    storedTask.prompt_json = JSON.stringify({ type: "doc", content: [
      { type: "paragraph", content: [
        { type: "text", text: "开始实现 " },
        { type: "mention", attrs: { kind: "skill", label: "to-spec", ref: "C:/skills/to-spec/SKILL.md" } },
      ] },
    ] });
    await renderBoard();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    const select = await screen.findByRole("combobox", { name: "独立 Agent" });
    fireEvent.change(select, { target: { value: agent.pane_id } });
    fireEvent.click(screen.getByRole("button", { name: "预览提示词" }));
    expect(screen.getByText("开始实现 $to-spec")).toBeTruthy();
    const dialog = screen.getByRole("heading", { name: /派发任务:/ }).closest(".dialog") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "派发" }));
    await waitFor(() => expect(sendPrompt).toHaveBeenCalledWith(expect.objectContaining({ promptText: "开始实现 $to-spec" })));
    expect(vi.mocked(invoke).mock.calls.some(([command]) => command === "read_skill_content")).toBe(false);
  });

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
    if (status === "done") expect(invoke).toHaveBeenCalledWith("complete_task", expect.objectContaining({ taskId: storedTask.id }));
    else expect(invoke).toHaveBeenCalledWith("update_task_status", { id: storedTask.id, status });
    expect(screen.queryByRole("heading", { name: /派发任务:/ })).toBeNull();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("有 Agent 时不展示顶部派发栏，仍可从卡片选择 Agent", async () => {
    await renderBoard();
    expect(screen.queryByText("拖拽任务到 Agent 即可选择派发")).toBeNull();
    expect(screen.queryByText(agent.title)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    const select = await screen.findByRole("combobox", { name: "独立 Agent" }) as HTMLSelectElement;
    expect(within(select).getByRole("option", { name: new RegExp(agent.title) })).toBeTruthy();
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("未开发卡片保留首次派发按钮", async () => {
    await renderBoard("todo");
    fireEvent.click(screen.getByRole("button", { name: "派发" }));
    await screen.findByRole("heading", { name: /派发任务:/ });
    expectNoStatusWrite();
    expect(sendPrompt).not.toHaveBeenCalled();
  });
});
