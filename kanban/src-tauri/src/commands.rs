use crate::models::{CsTask, Project, Task, TaskPriority};
use chrono::Utc;
use rfd;
use rusqlite::{params, Connection};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tauri::State;
use uuid::Uuid;
use walkdir::WalkDir;

pub struct DbState(pub Arc<Mutex<Connection>>);

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
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())
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
    let active: bool = conn.query_row("SELECT EXISTS(SELECT 1 FROM lifecycle_operations o JOIN tasks t ON t.id=o.task_id WHERE t.project_id=?1 AND o.state IN ('pending','unknown'))",[&id],|r|r.get(0)).map_err(|e|e.to_string())?;
    if active {
        return Err("flow.verify_required".into());
    }
    conn.execute(
        "UPDATE projects SET name=?1, root_path=?2, herdr_workspace=?3, cs_task_id=?4 WHERE id=?5",
        params![name, root_path, herdr_workspace, cs_task_id, id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn delete_project(
    state: State<DbState>,
    terminals: State<Arc<crate::terminal::TerminalManager>>,
    id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    let active: bool = conn.query_row("SELECT EXISTS(SELECT 1 FROM lifecycle_operations o JOIN tasks t ON t.id=o.task_id WHERE t.project_id=?1 AND o.state IN ('pending','unknown'))",[&id],|r|r.get(0)).map_err(|e|e.to_string())?;
    if active {
        return Err("flow.verify_required".into());
    }
    let pending: bool = conn.query_row("SELECT EXISTS(SELECT 1 FROM dispatch_operations o JOIN tasks t ON t.id=o.task_id WHERE t.project_id=?1 AND o.state IN ('pending','unknown'))",[&id],|r|r.get(0)).map_err(|e|e.to_string())?;
    if pending {
        return Err("dispatch.verify_required".into());
    }
    let ids = conn
        .prepare("SELECT id FROM tasks WHERE project_id=?1")
        .map_err(|e| e.to_string())?
        .query_map([&id], |r| r.get::<_, String>(0))
        .map_err(|e| e.to_string())?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM projects WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    drop(conn);
    for task in ids {
        terminals.close_task(&task);
    }
    Ok(())
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn list_tasks(state: State<DbState>, project_id: String) -> Result<Vec<Task>, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::tasks::list(&conn, &project_id)
}

#[tauri::command]
pub fn create_task(
    state: State<DbState>,
    project_id: String,
    name: String,
    priority: TaskPriority,
) -> Result<Task, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::tasks::create(&conn, &project_id, &name, priority)
}

#[tauri::command]
pub fn update_task(
    state: State<DbState>,
    id: String,
    name: String,
    prompt_json: String,
    priority: TaskPriority,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::tasks::update(&conn, &id, &name, &prompt_json, priority)
}

#[tauri::command]
pub async fn update_task_status(
    state: State<'_, DbState>,
    app: State<'_, Arc<crate::workflow::Workflow>>,
    terminals: State<'_, Arc<crate::terminal::TerminalManager>>,
    id: String,
    status: String,
) -> Result<crate::lifecycle::Outcome, String> {
    if status == "done" {
        let app = app.inner().clone();
        terminals.close_task(&id);
        return tauri::async_runtime::spawn_blocking(move || {
            app.complete_task(&id, &Uuid::new_v4().to_string())
        })
        .await
        .map_err(|e| e.to_string())?;
    }
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::lifecycle::ensure_idle(&conn, &id, None)?;
    if !matches!(status.as_str(), "todo" | "done") {
        return Err("dispatch.required".into());
    }
    if crate::workflow::binding(&conn, &id)?.operation.is_some() {
        return Err("dispatch.verify_required".into());
    }
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "UPDATE tasks SET status=?1, updated_at=?2 WHERE id=?3",
        params![status, now, id],
    )
    .map_err(|e| e.to_string())?;
    drop(conn);
    terminals.close_task(&id);
    Ok(crate::lifecycle::Outcome::default())
}

#[tauri::command]
pub fn archive_task(
    state: State<DbState>,
    terminals: State<Arc<crate::terminal::TerminalManager>>,
    id: String,
) -> Result<(), String> {
    let mut conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::tasks::archive(&mut conn, &id)?;
    drop(conn);
    terminals.close_task(&id);
    Ok(())
}

#[tauri::command]
pub fn delete_task(
    state: State<DbState>,
    terminals: State<Arc<crate::terminal::TerminalManager>>,
    id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::lifecycle::ensure_idle(&conn, &id, None)?;
    if crate::workflow::binding(&conn, &id)?.operation.is_some() {
        return Err("dispatch.verify_required".into());
    }
    conn.execute("DELETE FROM tasks WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    drop(conn);
    terminals.close_task(&id);
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
                matches!(
                    c.as_os_str().to_string_lossy().as_ref(),
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
            FileEntry {
                rel_path: rel,
                abs_path: abs,
            }
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
        let name = extract_frontmatter_field(&content, "name").unwrap_or_else(|| {
            path.parent()
                .and_then(|p| p.file_name())
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_default()
        });
        let description = extract_frontmatter_field(&content, "description").unwrap_or_default();

        if q.is_empty()
            || name.to_lowercase().contains(&q)
            || description.to_lowercase().contains(&q)
        {
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
    content
        .lines()
        .skip_while(|l| *l != "---")
        .skip(1)
        .take_while(|l| *l != "---")
        .find(|l| l.trim_start().starts_with(&prefix))
        .map(|l| {
            l.trim_start()
                .trim_start_matches(&prefix)
                .trim()
                .trim_matches('"')
                .to_string()
        })
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
    let appdata = std::env::var("APPDATA").map_err(|_| "APPDATA not set".to_string())?;
    let path = PathBuf::from(appdata)
        .join("ContextSwitcher")
        .join("tasks.json");

    if !path.exists() {
        return Ok(vec![]);
    }

    let raw = std::fs::read_to_string(&path).map_err(|e| format!("read tasks.json: {e}"))?;
    let doc: serde_json::Value =
        serde_json::from_str(&raw).map_err(|e| format!("parse tasks.json: {e}"))?;

    let tasks = doc
        .get("tasks")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "tasks.json missing 'tasks' array".to_string())?;

    let result: Vec<CsTask> = tasks
        .iter()
        .filter_map(|t| {
            let id = t.get("id")?.as_str()?.to_string();
            let name = t.get("name")?.as_str()?.to_string();
            let status = t
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("todo")
                .to_string();
            // herdr workspace is nested under herdr_binding.label in v1.4+ format
            let herdr_workspace = t
                .get("herdr_binding")
                .and_then(|b| b.get("label"))
                .and_then(|v| v.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| s.to_string());
            Some(CsTask {
                id,
                name,
                status,
                herdr_workspace,
            })
        })
        .collect();

    Ok(result)
}
