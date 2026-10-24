use super::*;

#[test]
fn reuses_unoccupied_idle_pane_with_fresh_session_but_skips_busy_targets() {
    let (app, fake) = fixture();
    let idle = target("idle");
    let mut busy = target("busy");
    busy.status = "working".into();
    fake.0.lock().unwrap().panes.extend([
        (idle.pane_id.clone(), (idle, Some(op()))),
        (busy.pane_id.clone(), (busy, None)),
    ]);
    app.start_task("a", "A", &op()).unwrap();
    app.start_task("b", "B", &op()).unwrap();
    let s = fake.0.lock().unwrap();
    assert_eq!(s.created, 1);
    assert_eq!(s.prepared, vec![None, None]);
    assert_eq!(app.binding("a").unwrap().target.unwrap().pane_id, "idle");
    assert_ne!(app.binding("b").unwrap().target.unwrap().pane_id, "idle");
}

#[test]
fn concurrent_projects_claim_distinct_panes() {
    let (app, fake) = fixture();
    let idle = target("idle");
    fake.0
        .lock()
        .unwrap()
        .panes
        .insert("idle".into(), (idle, None));
    std::thread::scope(|scope| {
        let a = scope.spawn(|| app.start_task("a", "A", &op()));
        let b = scope.spawn(|| app.start_task("b", "B", &op()));
        a.join().unwrap().unwrap();
        b.join().unwrap().unwrap();
    });
    assert_ne!(
        app.binding("a").unwrap().target.unwrap().pane_id,
        app.binding("b").unwrap().target.unwrap().pane_id
    );
    assert_eq!(fake.0.lock().unwrap().sent.len(), 2);
}
