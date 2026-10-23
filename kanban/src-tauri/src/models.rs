use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub root_path: String,
    pub herdr_workspace: String,
    /// Linked ContextSwitcher task id (optional)
    pub cs_task_id: Option<String>,
    pub created_at: String,
}

/// Slim view of a ContextSwitcher task for the project-link picker
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CsTask {
    pub id: String,
    pub name: String,
    pub status: String,
    pub herdr_workspace: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Todo,
    InProgress,
    Done,
}

impl TaskStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            TaskStatus::Todo => "todo",
            TaskStatus::InProgress => "in_progress",
            TaskStatus::Done => "done",
        }
    }
    pub fn from_str(s: &str) -> Self {
        match s {
            "in_progress" => TaskStatus::InProgress,
            "done" => TaskStatus::Done,
            _ => TaskStatus::Todo,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Task {
    pub id: String,
    pub project_id: String,
    pub name: String,
    pub status: TaskStatus,
    /// Tiptap JSON string for the prompt content
    pub prompt_json: String,
    /// Resolved plain text snapshot (expanded @ and $) — set at dispatch time
    pub prompt_snapshot: Option<String>,
    pub dispatched_at: Option<String>,
    pub dispatched_to: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DispatchRecord {
    pub task_id: String,
    pub target_workspace: String,
    pub target_agent: String,
    pub prompt_snapshot: String,
    pub dispatched_at: String,
}
