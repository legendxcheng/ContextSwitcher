use crate::models::{Project, Task, TaskPriority};
use chrono::Utc;
use rfd;
use rusqlite::{Connection, params};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tauri::State;
use uuid::Uuid;
use walkdir::WalkDir;

pub struct DbState(pub Arc<Mutex<Connection>>);

// ── Projects ──────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn list_projects(state: State<DbState>) -> Result<Vec<Project>, String> {
    crate::projects::list(&*state.0.lock().map_err(|e| e.to_string())?)
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
    prompt_json: Option<String>,
) -> Result<Task, String> {
    let conn = state.0.lock().map_err(|e| e.to_string())?;
    crate::tasks::create(
        &conn,
        &project_id,
        &name,
        priority,
        prompt_json.as_deref().unwrap_or("{}"),
    )
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
