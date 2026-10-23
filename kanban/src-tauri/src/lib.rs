mod commands;
mod db;
mod models;

use commands::DbState;
use rusqlite::Connection;
use std::sync::Mutex;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let db_path = db::db_path();
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).expect("failed to create data directory");
    }
    let conn = Connection::open(&db_path).expect("failed to open kanban.db");
    db::init(&conn).expect("failed to init schema");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(DbState(Mutex::new(conn)))
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
            commands::search_files,
            commands::search_skills,
            commands::read_file_content,
            commands::read_skill_content,
            commands::herdr_list_agents,
            commands::dispatch_to_herdr,
            commands::pick_folder,
            commands::read_cs_tasks,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
