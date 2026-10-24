use crate::terminal::{Output, TerminalManager};
use crate::{models::DispatchRecord, workflow::Workflow};
use std::sync::Arc;
use tauri::{Emitter, State};

#[tauri::command]
pub async fn start_task(
    app: State<'_, Arc<Workflow>>,
    handle: tauri::AppHandle,
    task_id: String,
    operation_id: String,
) -> Result<crate::lifecycle::Flow, String> {
    let app = app.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        app.submit_start(
            &task_id,
            &operation_id,
            Arc::new(move |event| {
                let _ = handle.emit("task-start-changed", event);
            }),
        )
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn complete_task(
    app: State<'_, Arc<Workflow>>,
    manager: State<'_, Arc<TerminalManager>>,
    task_id: String,
    operation_id: String,
) -> Result<crate::lifecycle::Outcome, String> {
    let app = app.inner().clone();
    manager.close_task(&task_id);
    tauri::async_runtime::spawn_blocking(move || app.complete_task(&task_id, &operation_id))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn recover_lifecycle(
    app: State<'_, Arc<Workflow>>,
    task_id: String,
    operation_id: String,
) -> Result<(), String> {
    let app = app.inner().clone();
    tauri::async_runtime::spawn_blocking(move || app.recover_lifecycle(&task_id, &operation_id))
        .await
        .map_err(|e| e.to_string())?
}

#[derive(serde::Serialize)]
pub struct AgentChoice {
    name: String,
    status: String,
    pane_id: String,
    title: String,
    occupied_by: Option<String>,
}

#[tauri::command]
pub async fn herdr_list_agents(
    app: State<'_, Arc<Workflow>>,
    project_id: String,
) -> Result<Vec<AgentChoice>, String> {
    let app = app.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let workspace = crate::projects::project_identity(
            &*app.db.lock().map_err(|e| e.to_string())?,
            &project_id,
            app.herdr.session(),
        )?;
        let targets = app.herdr.targets(&workspace)?;
        let conn = app.db.lock().map_err(|e| e.to_string())?;
        targets
            .into_iter()
            .map(|target| {
                let owner = crate::workflow::pane_owner(&conn, &target)?;
                Ok(AgentChoice {
                    name: target.agent,
                    status: target.status,
                    pane_id: target.pane_id,
                    title: target.title,
                    occupied_by: owner,
                })
            })
            .collect()
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn dispatch_to_herdr(
    app: State<'_, Arc<Workflow>>,
    task_id: String,
    agent_name: String,
    prompt_text: String,
    operation_id: String,
) -> Result<DispatchRecord, String> {
    let app = app.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        app.dispatch(&task_id, &agent_name, &prompt_text, &operation_id)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn resolve_dispatch(
    app: State<'_, Arc<Workflow>>,
    task_id: String,
    operation_id: String,
    sent: bool,
    evidence: String,
) -> Result<(), String> {
    let app = app.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        app.resolve(&task_id, &operation_id, sent, &evidence)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn repair_binding(
    app: State<'_, Arc<Workflow>>,
    manager: State<'_, Arc<TerminalManager>>,
    task_id: String,
    pane_id: String,
) -> Result<(), String> {
    let app = app.inner().clone();
    let manager = manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        app.repair(&task_id, &pane_id)?;
        manager.close_task(&task_id);
        Ok(())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn terminal_open(
    app: State<'_, Arc<Workflow>>,
    manager: State<'_, Arc<TerminalManager>>,
    task_id: String,
    connection_id: String,
    cols: u16,
    rows: u16,
    output: tauri::ipc::Channel<Output>,
) -> Result<String, String> {
    let app = app.inner().clone();
    let manager = manager.inner().clone();
    manager.select(&connection_id, &task_id)?;
    tauri::async_runtime::spawn_blocking(move || {
        let sink = Arc::new(move |packet| output.send(packet).is_ok());
        match manager.open(
            app,
            &crate::herdr::Cli::from_env(),
            &task_id,
            &connection_id,
            cols,
            rows,
            sink,
        ) {
            Ok(()) => Ok(connection_id),
            Err(e) => {
                manager.close(&connection_id);
                Err(e)
            }
        }
    })
    .await
    .map_err(|e| e.to_string())?
}
#[tauri::command]
pub fn terminal_close(manager: State<'_, Arc<TerminalManager>>, connection_id: String) {
    manager.close(&connection_id);
}
#[tauri::command]
pub async fn terminal_input(
    app: State<'_, Arc<Workflow>>,
    manager: State<'_, Arc<TerminalManager>>,
    connection_id: String,
    data: String,
) -> Result<(), String> {
    let app = app.inner().clone();
    let manager = manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || manager.input(&app, &connection_id, &data))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn terminal_scroll(
    app: State<'_, Arc<Workflow>>,
    manager: State<'_, Arc<TerminalManager>>,
    connection_id: String,
    event: crate::terminal::ScrollEvent,
) -> Result<(), String> {
    let app = app.inner().clone();
    let manager = manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || manager.scroll(&app, &connection_id, event))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
pub async fn terminal_resize(
    manager: State<'_, Arc<TerminalManager>>,
    connection_id: String,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    let manager = manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || manager.resize(&connection_id, cols, rows))
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
pub fn terminal_ack(manager: State<'_, Arc<TerminalManager>>, connection_id: String, bytes: usize) {
    manager.ack(&connection_id, bytes);
}
