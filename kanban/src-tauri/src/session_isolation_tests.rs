//! Opt-in regression at the task lifecycle boundary, using the real CLI adapter.
//! Prepare an empty, isolated workspace with the Codex integration installed.
use crate::{herdr::Cli, models::TaskPriority, tasks, workflow::Workflow};
use rusqlite::{Connection, params};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

fn operation() -> String {
    uuid::Uuid::new_v4().to_string()
}

#[test]
#[ignore = "requires a dedicated Herdr workspace and isolated Codex home; starts and closes test panes"]
fn live_tasks_keep_distinct_sessions_through_completion_and_resume() {
    let name = std::env::var("KANBAN_LIVE_WORKSPACE").expect("explicit workspace required");
    assert!(name.starts_with("kanban-acceptance-"));
    let cwd = std::env::var("KANBAN_LIVE_CWD").expect("explicit test directory required");
    let path = std::env::temp_dir().join(format!("kanban-session-{}.db", operation()));
    let app = Workflow {
        db: Arc::new(Mutex::new(Connection::open(&path).unwrap())),
        herdr: Arc::new(Cli::from_env()),
    };
    let spaces = app.herdr.workspaces().unwrap();
    let matches: Vec<_> = spaces.iter().filter(|w| w.name == name).collect();
    assert_eq!(matches.len(), 1, "acceptance workspace must be unambiguous");
    let workspace = &matches[0].id;
    assert!(
        app.herdr.targets(workspace).unwrap().is_empty(),
        "use an empty workspace"
    );
    // Herdr removes a workspace when its last pane closes. Keep a shell with
    // another cwd so it is never selected as a task pane during this test.
    let keepalive_cwd = std::env::temp_dir();
    assert_ne!(std::path::Path::new(&cwd), keepalive_cwd);
    app.herdr
        .create_pane(
            workspace,
            keepalive_cwd.to_str().unwrap(),
            "kanban-acceptance-keepalive",
        )
        .unwrap();
    let ids = {
        let db = app.db.lock().unwrap();
        crate::db::init(&db).unwrap();
        db.execute("INSERT INTO projects(id,name,root_path,herdr_workspace,created_at,herdr_session,workspace_id,sync_status) VALUES ('test','test',?1,?2,'now',?3,?4,'ready')",
            params![cwd, name, app.herdr.session(), workspace]).unwrap();
        ["A", "B"].map(|name| {
            tasks::create(&db, "test", name, TaskPriority::Normal, "{}")
                .unwrap()
                .id
        })
    };
    let mut targets = Vec::new();
    let mut sessions = Vec::new();
    for id in &ids {
        app.start_task(
            id,
            "Reply only READY. Do not run commands or edit files.",
            &operation(),
        )
        .unwrap();
        let target = app.binding(id).unwrap().target.unwrap();
        let deadline = Instant::now() + Duration::from_secs(10);
        let session = loop {
            if let Some(session) = app.herdr.session_id(&target).unwrap() {
                break session;
            }
            assert!(
                Instant::now() < deadline,
                "task pane {} did not receive its session ID",
                target.pane_id
            );
            std::thread::sleep(Duration::from_millis(200));
        };
        targets.push(target);
        sessions.push(session);
    }
    assert_ne!(targets[0].pane_id, targets[1].pane_id);
    assert_ne!(sessions[0], sessions[1]);
    // Starting B must not replace A's report with B's session.
    assert_eq!(
        app.herdr.session_id(&targets[0]).unwrap(),
        Some(sessions[0].clone())
    );
    for (index, id) in ids.iter().enumerate() {
        assert!(
            app.complete_task(id, &operation())
                .unwrap()
                .warning
                .is_none()
        );
        assert!(!app.herdr.pane_exists(&targets[index]).unwrap());
        if index == 0 {
            assert!(app.herdr.pane_exists(&targets[1]).unwrap());
        }
    }
    drop(app);
    let conn = Connection::open(&path).unwrap();
    crate::db::init(&conn).unwrap();
    crate::db::recover_interrupted(&conn).unwrap();
    let app = Workflow {
        db: Arc::new(Mutex::new(conn)),
        herdr: Arc::new(Cli::from_env()),
    };
    for (index, id) in ids.iter().enumerate() {
        app.start_task(id, "MUST_NOT_BE_SENT_ON_RESUME", &operation())
            .unwrap();
        let target = app.binding(id).unwrap().target.unwrap();
        assert_eq!(
            app.herdr.session_id(&target).unwrap(),
            Some(sessions[index].clone())
        );
        assert!(
            app.complete_task(id, &operation())
                .unwrap()
                .warning
                .is_none()
        );
        assert!(!app.herdr.pane_exists(&target).unwrap());
    }
    let listed = tasks::list(&app.db.lock().unwrap(), "test").unwrap();
    for task in listed {
        let index = ids.iter().position(|id| id == &task.id).unwrap();
        assert_eq!(task.status, crate::models::TaskStatus::Done);
        assert!(!task.cleanup_required);
        assert_eq!(task.flow.unwrap().session_id, Some(sessions[index].clone()));
        assert_eq!(
            task.prompt_snapshot.as_deref(),
            Some("Reply only READY. Do not run commands or edit files.")
        );
    }
    drop(app);
    std::fs::remove_file(path).unwrap();
}
