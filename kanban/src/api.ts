import { invoke, Channel } from "@tauri-apps/api/core";
import type {
  Project, Task, FileEntry, SkillEntry, HerdrAgent, DispatchRecord, CsTask,
} from "./types";

// Projects
export const listProjects = () => invoke<Project[]>("list_projects");
export const createProject = (
  name: string, root_path: string, herdr_workspace: string, cs_task_id?: string | null,
) => invoke<Project>("create_project", { name, rootPath: root_path, herdrWorkspace: herdr_workspace, csTaskId: cs_task_id ?? null });
export const updateProject = (
  id: string, name: string, root_path: string, herdr_workspace: string, cs_task_id?: string | null,
) => invoke<void>("update_project", { id, name, rootPath: root_path, herdrWorkspace: herdr_workspace, csTaskId: cs_task_id ?? null });
export const deleteProject = (id: string) => invoke<void>("delete_project", { id });

// Tasks
export const listTasks = (projectId: string) => invoke<Task[]>("list_tasks", { projectId });
export const createTask = (projectId: string, name: string) =>
  invoke<Task>("create_task", { projectId, name });
export const updateTask = (id: string, name: string, promptJson: string) =>
  invoke<void>("update_task", { id, name, promptJson });
export const updateTaskStatus = (id: string, status: string) =>
  invoke<void>("update_task_status", { id, status });
export const deleteTask = (id: string) => invoke<void>("delete_task", { id });

// Discovery
export const searchFiles = (rootPath: string, query: string) =>
  invoke<FileEntry[]>("search_files", { rootPath, query });
export const searchSkills = (query: string) => invoke<SkillEntry[]>("search_skills", { query });
export const readFileContent = (absPath: string) =>
  invoke<string>("read_file_content", { absPath });
export const readSkillContent = (skillMdPath: string) =>
  invoke<string>("read_skill_content", { skillMdPath });

// Herdr
export const herdrListAgents = (workspace: string) =>
  invoke<HerdrAgent[]>("herdr_list_agents", { workspace });
export const dispatchToHerdr = (
  taskId: string, agentName: string, workspace: string, promptText: string, operationId: string,
) => invoke<DispatchRecord>("dispatch_to_herdr", {
  taskId, agentName, workspace, promptText, operationId,
});
export const resolveDispatch = (taskId: string, operationId: string, sent: boolean, evidence: string) =>
  invoke<void>("resolve_dispatch", { taskId, operationId, sent, evidence });
export const repairBinding = (taskId: string, paneId: string) => invoke<void>("repair_binding", { taskId, paneId });
export interface TerminalOutput { kind: "data" | "closed"; data: number[]; message: string }
export const openTerminal = (taskId: string, connectionId: string, cols: number, rows: number, onOutput: (packet: TerminalOutput) => void) => {
  const output = new Channel<TerminalOutput>();
  output.onmessage = onOutput;
  return invoke<string>("terminal_open", { taskId, connectionId, cols, rows, output });
};
export const closeTerminal = (connectionId: string) => invoke<void>("terminal_close", { connectionId });
export const inputTerminal = (connectionId: string, data: string) => invoke<void>("terminal_input", { connectionId, data });
export const resizeTerminal = (connectionId: string, cols: number, rows: number) => invoke<void>("terminal_resize", { connectionId, cols, rows });
export const ackTerminal = (connectionId: string, bytes: number) => invoke<void>("terminal_ack", { connectionId, bytes });

// ContextSwitcher
export const readCsTasks = () => invoke<CsTask[]>("read_cs_tasks");

// Native folder picker (returns null if cancelled)
export const pickFolder = () => invoke<string | null>("pick_folder");
