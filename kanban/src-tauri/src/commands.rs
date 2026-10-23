use crate::models::{CsTask, DispatchRecord, Project, Task, TaskStatus};
use chrono::Utc;
use rusqlite::{params, Connection};
use rfd;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::State;
use uuid::Uuid;
use walkdir::WalkDir;

pub struct DbState(pub Mutex<Connection>);

// ── Projects ──────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn list_projects(state: State<DbState>) -> Result<Vec<Project>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT id, name, root_path, herdr_workspace, cs_task_id, created_at FROM projects ORDER BY created_at")
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |row| {
            Ok(Project {
                id: row.get(0)?,
                name: row.get(1)?,
                root_path: row.get(2)?,
                herdr_workspace: row.get(3)?,
                cs_task_id: row.get(4)?,
                created_at: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn create_project(
    state: State<DbState>,
    name: String,
    root_path: String,
    herdr_workspace: String,
    cs_task_id: Option<String>,
) -> Result<Project, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let p = Project {
        id: Uuid::new_v4().to_string(),
        name,
        root_path,
        herdr_workspace,
        cs_task_id,
        created_at: Utc::now().to_rfc3339(),
    };
    conn.execute(
        "INSERT INTO projects (id, name, root_path, herdr_workspace, cs_task_id, created_at) VALUES (?1,?2,?3,?4,?5,?6)",
        params![p.id, p.name, p.root_path, p.herdr_workspace, p.cs_task_id, p.created_at],
    )
    .map_err(|e| e.to_string())?;
    Ok(p)
}

#[tauri::command]
pub fn update_project(
    state: State<DbState>,
    id: String,
    name: String,
    root_path: String,
    herdr_workspace: String,
    cs_task_id: Option<String>,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE projects SET name=?1, root_path=?2, herdr_workspace=?3, cs_task_id=?4 WHERE id=?5",
        params![name, root_path, herdr_workspace, cs_task_id, id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn delete_project(state: State<DbState>, id: String) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM projects WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

fn row_to_task(row: &rusqlite::Row) -> rusqlite::Result<Task> {
    let status_str: String = row.get(3)?;
    Ok(Task {
        id: row.get(0)?,
        project_id: row.get(1)?,
        name: row.get(2)?,
        status: TaskStatus::from_str(&status_str),
        prompt_json: row.get(4)?,
        prompt_snapshot: row.get(5)?,
        dispatched_at: row.get(6)?,
        dispatched_to: row.get(7)?,
        created_at: row.get(8)?,
        updated_at: row.get(9)?,
    })
}

#[tauri::command]
pub fn list_tasks(state: State<DbState>, project_id: String) -> Result<Vec<Task>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT id,project_id,name,status,prompt_json,prompt_snapshot,
                    dispatched_at,dispatched_to,created_at,updated_at
             FROM tasks WHERE project_id=?1 ORDER BY created_at",
        )
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map(params![project_id], row_to_task)
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn create_task(
    state: State<DbState>,
    project_id: String,
    name: String,
) -> Result<Task, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let now = Utc::now().to_rfc3339();
    let task = Task {
        id: Uuid::new_v4().to_string(),
        project_id,
        name,
        status: TaskStatus::Todo,
        prompt_json: "{}".into(),
        prompt_snapshot: None,
        dispatched_at: None,
        dispatched_to: None,
        created_at: now.clone(),
        updated_at: now.clone(),
    };
    conn.execute(
        "INSERT INTO tasks (id,project_id,name,status,prompt_json,created_at,updated_at)
         VALUES (?1,?2,?3,?4,?5,?6,?7)",
        params![
            task.id, task.project_id, task.name,
            task.status.as_str(), task.prompt_json,
            task.created_at, task.updated_at
        ],
    )
    .map_err(|e| e.to_string())?;
    Ok(task)
}

#[tauri::command]
pub fn update_task(
    state: State<DbState>,
    id: String,
    name: String,
    prompt_json: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "UPDATE tasks SET name=?1, prompt_json=?2, updated_at=?3 WHERE id=?4",
        params![name, prompt_json, now, id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn update_task_status(
    state: State<DbState>,
    id: String,
    status: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "UPDATE tasks SET status=?1, updated_at=?2 WHERE id=?3",
        params![status, now, id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn delete_task(state: State<DbState>, id: String) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM tasks WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

// ── File & Skill Discovery ────────────────────────────────────────────────────

#[derive(serde::Serialize)]
pub struct FileEntry {
    pub rel_path: String,
    pub abs_path: String,
}

#[tauri::command]
pub fn search_files(root_path: String, query: String) -> Result<Vec<FileEntry>, String> {
    let root = Path::new(&root_path);
    if !root.exists() {
        return Err(format!("Path does not exist: {root_path}"));
    }
    let q = query.to_lowercase();
    let mut results: Vec<FileEntry> = WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .filter(|e| {
            // skip common noise dirs
            !e.path().components().any(|c| {
                matches!(c.as_os_str().to_string_lossy().as_ref(),
                    "node_modules" | ".git" | "target" | "__pycache__" | ".venv" | "dist" | "build"
                )
            })
        })
        .filter(|e| {
            let name = e.file_name().to_string_lossy().to_lowercase();
            q.is_empty() || name.contains(&q)
        })
        .take(50)
        .map(|e| {
            let abs = e.path().to_string_lossy().replace('\\', "/");
            let rel = e
                .path()
                .strip_prefix(root)
                .unwrap_or(e.path())
                .to_string_lossy()
                .replace('\\', "/");
            FileEntry { rel_path: rel, abs_path: abs }
        })
        .collect();
    results.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    Ok(results)
}

#[derive(serde::Serialize)]
pub struct SkillEntry {
    pub name: String,
    pub description: String,
    pub skill_md_path: String,
}

/// Search for SKILL.md files under the Claude plugins / skills directory.
/// Reads the description from frontmatter `description:` line.
#[tauri::command]
pub fn search_skills(query: String) -> Result<Vec<SkillEntry>, String> {
    // Skills live under ~/.claude — use USERPROFILE on Windows, HOME elsewhere.
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_default();
    let base = PathBuf::from(&home).join(".claude");
    let q = query.to_lowercase();
    let mut results: Vec<SkillEntry> = Vec::new();

    for entry in WalkDir::new(&base)
        .follow_links(false)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_name().to_string_lossy() == "SKILL.md")
    {
        let path = entry.path();
        let content = std::fs::read_to_string(path).unwrap_or_default();
        let name = extract_frontmatter_field(&content, "name")
            .unwrap_or_else(|| path.parent().and_then(|p| p.file_name()).map(|n| n.to_string_lossy().into_owned()).unwrap_or_default());
        let description = extract_frontmatter_field(&content, "description").unwrap_or_default();

        if q.is_empty() || name.to_lowercase().contains(&q) || description.to_lowercase().contains(&q) {
            results.push(SkillEntry {
                name,
                description,
                skill_md_path: path.to_string_lossy().replace('\\', "/"),
            });
        }
        if results.len() >= 30 {
            break;
        }
    }
    Ok(results)
}

fn extract_frontmatter_field(content: &str, field: &str) -> Option<String> {
    let prefix = format!("{field}:");
    content.lines()
        .skip_while(|l| *l != "---")
        .skip(1)
        .take_while(|l| *l != "---")
        .find(|l| l.trim_start().starts_with(&prefix))
        .map(|l| l.trim_start().trim_start_matches(&prefix).trim().trim_matches('"').to_string())
}

// ── Read file contents (for @ expansion preview) ──────────────────────────────

#[tauri::command]
pub fn read_file_content(abs_path: String) -> Result<String, String> {
    std::fs::read_to_string(&abs_path).map_err(|e| format!("{abs_path}: {e}"))
}

#[tauri::command]
pub fn read_skill_content(skill_md_path: String) -> Result<String, String> {
    std::fs::read_to_string(&skill_md_path).map_err(|e| format!("{skill_md_path}: {e}"))
}

// ── Herdr integration ─────────────────────────────────────────────────────────

#[derive(serde::Serialize)]
pub struct HerdrAgent {
    pub name: String,
    pub status: String,
    pub pane_id: String,
    pub title: String,
}

/// Run `herdr agent list` and parse the JSON output into agent entries.
/// Filters to agents whose workspace label matches `workspace` (case-insensitive).
#[tauri::command]
pub fn herdr_list_agents(workspace: String) -> Result<Vec<HerdrAgent>, String> {
    let output = std::process::Command::new("herdr")
        .args(["agent", "list"])
        .output()
        .map_err(|e| format!("herdr not found: {e}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() && stdout.trim().is_empty() {
        return Err(format!("herdr agent list failed: {stderr}"));
    }

    // herdr agent list outputs a single JSON line:
    // {"id":"cli:agent:list","result":{"agents":[{...}],...}}
    // Each agent has: agent, agent_status, pane_id, terminal_title_stripped, workspace_id
    // We also need the workspace label from herdr workspace list to filter by name.
    // Simpler: filter by cwd basename matching workspace label, or return all and let UI filter.
    // We match workspace label against the terminal_title_stripped suffix " | <label>" pattern,
    // or against cwd basename. We fetch workspace list to map workspace_id → label.
    let doc: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("parse herdr agent list: {e}"))?;
    let agents_arr = doc
        .get("result")
        .and_then(|r| r.get("agents"))
        .and_then(|a| a.as_array())
        .ok_or_else(|| "herdr agent list: missing result.agents".to_string())?;

    // Fetch workspace list to map workspace_id → label
    let ws_map = fetch_workspace_label_map();

    let ws_lower = workspace.to_lowercase();
    let result: Vec<HerdrAgent> = agents_arr.iter().filter_map(|a| {
        let pane_id = a.get("pane_id")?.as_str()?.to_string();
        let agent_type = a.get("agent").and_then(|v| v.as_str()).unwrap_or("?").to_string();
        let status = a.get("agent_status").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
        let title = a.get("terminal_title_stripped").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let workspace_id = a.get("workspace_id").and_then(|v| v.as_str()).unwrap_or("").to_string();

        // Filter by workspace label if provided
        if !ws_lower.is_empty() {
            let label = ws_map.get(&workspace_id).map(|s| s.to_lowercase()).unwrap_or_default();
            let cwd = a.get("cwd").and_then(|v| v.as_str()).unwrap_or("");
            let cwd_basename = cwd.replace('\\', "/").split('/').last().unwrap_or("").to_lowercase();
            if !label.contains(&ws_lower) && !cwd_basename.contains(&ws_lower) {
                return None;
            }
        }

        Some(HerdrAgent {
            name: agent_type,
            status,
            pane_id,
            title,
        })
    }).collect();

    Ok(result)
}

fn fetch_workspace_label_map() -> std::collections::HashMap<String, String> {
    let output = std::process::Command::new("herdr")
        .args(["workspace", "list"])
        .output();
    let Ok(out) = output else { return Default::default() };
    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let Ok(doc) = serde_json::from_str::<serde_json::Value>(&stdout) else { return Default::default() };
    let Some(arr) = doc.get("result").and_then(|r| r.get("workspaces")).and_then(|a| a.as_array()) else {
        return Default::default();
    };
    arr.iter().filter_map(|w| {
        let id = w.get("workspace_id")?.as_str()?.to_string();
        let label = w.get("label")?.as_str()?.to_string();
        Some((id, label))
    }).collect()
}

/// Dispatch a resolved prompt to a Herdr agent via `herdr agent prompt`.
/// `agent_name` is the pane_id (e.g. "w3:p2") returned by herdr_list_agents.
#[tauri::command]
pub fn dispatch_to_herdr(
    state: State<DbState>,
    task_id: String,
    agent_name: String,   // actually the pane_id used as TARGET
    workspace: String,
    prompt_text: String,
) -> Result<DispatchRecord, String> {
    // Guard: do not allow empty prompt
    if prompt_text.trim().is_empty() {
        return Err("Prompt is empty".into());
    }

    let output = std::process::Command::new("herdr")
        .args(["agent", "prompt", &agent_name, &prompt_text])
        .output()
        .map_err(|e| format!("herdr not found: {e}"))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(format!("herdr agent prompt failed: {stderr}"));
    }

    let now = Utc::now().to_rfc3339();
    let target = format!("{workspace}/{agent_name}");

    // Update task: status → in_progress, store snapshot and dispatch info
    {
        let conn = state.0.lock().map_err(|e| e.to_string())?;
        conn.execute(
            "UPDATE tasks SET status='in_progress', prompt_snapshot=?1, dispatched_at=?2, dispatched_to=?3, updated_at=?4 WHERE id=?5",
            params![prompt_text, now, target, now, task_id],
        )
        .map_err(|e| e.to_string())?;
    }

    Ok(DispatchRecord {
        task_id,
        target_workspace: workspace,
        target_agent: agent_name,
        prompt_snapshot: prompt_text,
        dispatched_at: now,
    })
}

// ── ContextSwitcher integration ───────────────────────────────────────────────

/// Open a native folder picker. Returns the chosen absolute path, or null if cancelled.
#[tauri::command]
pub fn pick_folder() -> Result<Option<String>, String> {
    let folder = rfd::FileDialog::new()
        .set_title("选择本地目录")
        .pick_folder();
    Ok(folder.map(|p| p.to_string_lossy().replace('\\', "/")))
}

/// Read ContextSwitcher tasks.json from %APPDATA%\ContextSwitcher\tasks.json
/// and return a slim list for the project-link picker.
#[tauri::command]
pub fn read_cs_tasks() -> Result<Vec<CsTask>, String> {
    let appdata = std::env::var("APPDATA")
        .map_err(|_| "APPDATA not set".to_string())?;
    let path = PathBuf::from(appdata)
        .join("ContextSwitcher")
        .join("tasks.json");

    if !path.exists() {
        return Ok(vec![]);
    }

    let raw = std::fs::read_to_string(&path)
        .map_err(|e| format!("read tasks.json: {e}"))?;
    let doc: serde_json::Value = serde_json::from_str(&raw)
        .map_err(|e| format!("parse tasks.json: {e}"))?;

    let tasks = doc.get("tasks")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "tasks.json missing 'tasks' array".to_string())?;

    let result: Vec<CsTask> = tasks.iter().filter_map(|t| {
        let id = t.get("id")?.as_str()?.to_string();
        let name = t.get("name")?.as_str()?.to_string();
        let status = t.get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("todo")
            .to_string();
        // herdr workspace is nested under herdr_binding.label in v1.4+ format
        let herdr_workspace = t.get("herdr_binding")
            .and_then(|b| b.get("label"))
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string());
        Some(CsTask { id, name, status, herdr_workspace })
    }).collect();

    Ok(result)
}
