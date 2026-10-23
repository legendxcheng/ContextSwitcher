export type TaskStatus = "todo" | "in_progress" | "done";

export interface Project {
  id: string;
  name: string;
  root_path: string;
  herdr_workspace: string;
  cs_task_id: string | null;
  created_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  name: string;
  status: TaskStatus;
  prompt_json: string;
  prompt_snapshot: string | null;
  dispatched_at: string | null;
  dispatched_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface FileEntry {
  rel_path: string;
  abs_path: string;
}

export interface SkillEntry {
  name: string;
  description: string;
  skill_md_path: string;
}

export interface HerdrAgent {
  name: string;
  status: string;
  pane_id: string;
  title: string;
}

export interface DispatchRecord {
  task_id: string;
  target_workspace: string;
  target_agent: string;
  prompt_snapshot: string;
  dispatched_at: string;
}

// Slim view of a ContextSwitcher task for the project-link picker
export interface CsTask {
  id: string;
  name: string;
  status: string;
  herdr_workspace: string | null;
}

// Tiptap mention node stored inside prompt_json
export interface MentionAttrs {
  kind: "file" | "skill";
  label: string;
  ref: string;
}
