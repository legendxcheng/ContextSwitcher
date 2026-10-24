use super::*;

#[test]
#[ignore = "requires an explicitly prepared isolated Herdr acceptance workspace"]
fn live_dispatch_and_exclusive_binding() {
    let workspace =
        std::env::var("KANBAN_LIVE_WORKSPACE").expect("explicit acceptance workspace required");
    assert!(workspace.starts_with("kanban-acceptance-"));
    let (mut app, _) = fixture();
    app.herdr = Arc::new(crate::herdr::Cli::from_env());
    let spaces = app.herdr.workspaces().unwrap();
    let selected: Vec<_> = spaces.iter().filter(|w| w.name == workspace).collect();
    assert_eq!(selected.len(), 1);
    let workspace_id = &selected[0].id;
    app.db
        .lock()
        .unwrap()
        .execute(
            "UPDATE projects SET workspace_id=?1,herdr_session=?2",
            params![workspace_id, app.herdr.session()],
        )
        .unwrap();
    let targets = app.herdr.targets(workspace_id).unwrap();
    let pane = &targets.first().expect("isolated agent required").pane_id;
    let reply = format!(
        "KANBAN_ACCEPT_{}",
        &uuid::Uuid::new_v4().simple().to_string()[..8]
    );
    app.dispatch(
        "a",
        pane,
        &format!("Reply only {reply}. Do not run commands or edit files. Ignore the following padding.\n{}", "padding ".repeat(1450)),
        "live-op",
    )
    .unwrap();
    assert_eq!(app.binding("a").unwrap().state, "valid");
    assert_eq!(
        app.dispatch("b", pane, "SHOULD_NOT_SEND", "live-other")
            .unwrap_err(),
        "binding.occupied"
    );
    // A successful CLI response alone does not prove Enter submitted the
    // prompt. Keep a real terminal attached and require the agent's reply.
    let cli = crate::herdr::Cli::from_env();
    let app = Arc::new(app);
    let manager = crate::terminal::TerminalManager::default();
    manager.select("submit-check", "a").unwrap();
    manager
        .open(app, &cli, "a", "submit-check", 100, 30, Arc::new(|_| true))
        .unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(45);
    let mut last_output = String::new();
    let mut replied = false;
    while std::time::Instant::now() < deadline {
        let output = cli
            .command()
            .args([
                "agent", "read", pane, "--source", "visible", "--lines", "12",
            ])
            .output()
            .unwrap();
        last_output = String::from_utf8_lossy(&output.stdout).into_owned();
        if last_output.contains(&format!("• {reply}")) {
            replied = true;
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(300));
    }
    manager.close("submit-check");
    assert!(
        replied,
        "prompt was not submitted or no reply arrived: {last_output}"
    );
}

#[test]
#[ignore = "requires an explicitly prepared isolated Herdr acceptance workspace"]
fn live_terminal_attachment_input_resize_and_safe_detach() {
    let workspace =
        std::env::var("KANBAN_LIVE_WORKSPACE").expect("explicit acceptance workspace required");
    assert!(workspace.starts_with("kanban-acceptance-"));
    let (mut app, _) = fixture();
    let cli = crate::herdr::Cli::from_env();
    app.herdr = Arc::new(cli.clone());
    let spaces = app.herdr.workspaces().unwrap();
    let selected: Vec<_> = spaces.iter().filter(|w| w.name == workspace).collect();
    assert_eq!(selected.len(), 1);
    let workspace_id = &selected[0].id;
    app.db
        .lock()
        .unwrap()
        .execute(
            "UPDATE projects SET workspace_id=?1,herdr_session=?2",
            params![workspace_id, app.herdr.session()],
        )
        .unwrap();
    let pane = app.herdr.targets(workspace_id).unwrap()[0].pane_id.clone();
    app.dispatch(
        "a",
        &pane,
        "Reply only KANBAN_ATTACH_READY. Do not run commands or edit files.",
        "live-attach",
    )
    .unwrap();
    let app = Arc::new(app);
    let manager = crate::terminal::TerminalManager::default();
    let (tx, rx) = std::sync::mpsc::channel();
    manager.select("view-a", "a").unwrap();
    manager
        .open(
            app.clone(),
            &cli,
            "a",
            "view-a",
            80,
            24,
            Arc::new(move |output| tx.send(output).is_ok()),
        )
        .unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
    let mut bytes = Vec::new();
    while std::time::Instant::now() < deadline && bytes.len() < 100 {
        let Ok(packet) = rx.recv_timeout(std::time::Duration::from_secs(1)) else {
            continue;
        };
        assert_ne!(
            packet.kind,
            "closed",
            "{}; output={}",
            packet.message,
            String::from_utf8_lossy(&bytes)
        );
        manager.ack("view-a", packet.data.len());
        bytes.extend(packet.data);
    }
    assert!(
        bytes.len() > 100,
        "no real terminal content: {}",
        String::from_utf8_lossy(&bytes)
    );
    manager.resize("view-a", 100, 30).unwrap();
    // A harmless unsent draft tests the keyboard path without another model turn.
    manager.input(&app, "view-a", "KANBAN_INPUT_PROBE").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(500));
    manager
        .input(&app, "view-a", &"\u{7f}".repeat("KANBAN_INPUT_PROBE".len()))
        .unwrap();
    manager.close("view-a");
    assert!(
        app.target("a", true).is_ok(),
        "detaching must preserve the real agent"
    );
    assert!(manager.input(&app, "view-a", "MUST_NOT_ARRIVE").is_err());
}
