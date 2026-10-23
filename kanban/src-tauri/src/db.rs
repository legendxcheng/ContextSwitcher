use rusqlite::{Connection, Result};
use std::path::PathBuf;

/// Keep this guard alive until shutdown, so restart recovery cannot race a sender.
pub fn lock_database(path: &std::path::Path) -> std::io::Result<std::fs::File> {
    let file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path.with_extension("lock"))?;
    fs2::FileExt::try_lock_exclusive(&file)?;
    Ok(file)
}

pub fn db_path() -> PathBuf {
    // Allows isolated desktop acceptance runs without touching personal tasks.
    if let Some(path) = std::env::var_os("KANBAN_DATA_DIR") {
        return PathBuf::from(path).join("kanban.db");
    }
    let data_dir = std::env::var("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    data_dir.join("herdr-kanban").join("kanban.db")
}

pub fn init(conn: &Connection) -> Result<()> {
    conn.execute_batch("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=3000;")?;
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            root_path TEXT NOT NULL,
            herdr_workspace TEXT NOT NULL,
            cs_task_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo',
            prompt_json TEXT NOT NULL DEFAULT '{}',
            prompt_snapshot TEXT,
            dispatched_at TEXT,
            dispatched_to TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
    ",
    )?;
    // migrate: silently ignored if column already exists
    let _ = conn.execute_batch("ALTER TABLE projects ADD COLUMN cs_task_id TEXT;");
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS task_bindings (
            task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
            session TEXT NOT NULL, pane_id TEXT NOT NULL, target_json TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('valid','reserved')),
            UNIQUE(session,pane_id)
        );
        INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);",
    )?;
    conn.execute_batch("CREATE TABLE IF NOT EXISTS dispatch_operations (
        id TEXT PRIMARY KEY, task_id TEXT NOT NULL, workspace TEXT NOT NULL,
        target_json TEXT NOT NULL, prompt TEXT NOT NULL, created_at TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('pending','unknown','sent','not_sent')),
        had_binding INTEGER NOT NULL, evidence TEXT NOT NULL DEFAULT ''
    );
    CREATE UNIQUE INDEX IF NOT EXISTS one_pending_dispatch ON dispatch_operations(task_id) WHERE state IN ('pending','unknown');
    INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);")?;
    Ok(())
}

/// Only called once when opening the application, never during a live command.
pub fn recover_interrupted(conn: &Connection) -> Result<()> {
    conn.execute(
        "UPDATE dispatch_operations SET state='unknown' WHERE state='pending'",
        [],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn another_instance_cannot_recover_a_live_databases_dispatches() {
        let path = std::env::temp_dir().join(format!("kanban-{}.db", uuid::Uuid::new_v4()));
        let first = super::lock_database(&path).unwrap();
        assert!(super::lock_database(&path).is_err());
        drop(first);
        let restarted = super::lock_database(&path).unwrap();
        drop(restarted);
        std::fs::remove_file(path.with_extension("lock")).unwrap();
    }
}
