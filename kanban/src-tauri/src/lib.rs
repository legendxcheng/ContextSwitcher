mod commands;
mod db;
mod herdr;
mod lifecycle;
mod models;
mod tasks;
mod terminal;
mod work_commands;
mod workflow;

use commands::DbState;
use rusqlite::Connection;
use std::sync::{Arc, Mutex};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let db_path = db::db_path();
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).expect("failed to create data directory");
    }
    let _database_guard =
        db::lock_database(&db_path).expect("another Kanban instance is using this database");
    let conn = Connection::open(&db_path).expect("failed to open kanban.db");
    db::init(&conn).expect("failed to init schema");

    db::recover_interrupted(&conn).expect("failed to recover dispatch operations");
    let conn = Arc::new(Mutex::new(conn));
    let workflow = Arc::new(workflow::Workflow {
        db: conn.clone(),
        herdr: Arc::new(herdr::Cli::from_env()),
    });
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(DbState(conn))
        .manage(workflow)
        .manage(Arc::new(terminal::TerminalManager::default()))
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                use tauri::Manager;
                window.state::<Arc<terminal::TerminalManager>>().close_all();
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::list_projects,
            commands::create_project,
            commands::update_project,
            commands::delete_project,
            commands::list_tasks,
            commands::create_task,
            commands::update_task,
            commands::update_task_status,
            commands::delete_task,
            commands::archive_task,
            commands::search_files,
            commands::search_skills,
            commands::read_file_content,
            commands::read_skill_content,
            work_commands::herdr_list_agents,
            work_commands::start_task,
            work_commands::complete_task,
            work_commands::recover_lifecycle,
            work_commands::dispatch_to_herdr,
            work_commands::resolve_dispatch,
            work_commands::repair_binding,
            work_commands::terminal_open,
            work_commands::terminal_close,
            work_commands::terminal_input,
            work_commands::terminal_resize,
            work_commands::terminal_ack,
            commands::pick_folder,
            commands::read_cs_tasks,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
