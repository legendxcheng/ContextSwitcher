//! Durable task lifecycle. External calls never hold the SQLite mutex.
use crate::workflow::{binding, pane_owner, Target, Workflow};
use rusqlite::{params, Connection, OptionalExtension};

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct Flow {
    pub session_id: Option<String>,
    pub operation_id: Option<String>,
    pub kind: Option<String>,
    pub state: Option<String>,
    pub error: String,
    pub pane_id: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::workflow::{Herdr, SendError};
    use std::collections::BTreeMap;
    use std::sync::{Arc, Mutex};

    #[derive(Default)]
    struct State {
        panes: BTreeMap<String, (Target, Option<String>)>,
        created: usize,
        prepared: Vec<Option<String>>,
        sent: Vec<String>,
        closed: Vec<String>,
        missing_id: bool,
        close_error: bool,
        close_then_error: bool,
        prepare_error: bool,
        mismatch: bool,
        send_error: bool,
        create_error: bool,
    }
    #[derive(Default)]
    struct Fake(Mutex<State>);
    fn target(id: &str) -> Target {
        Target {
            session: "default".into(),
            workspace_id: "w1".into(),
            pane_id: id.into(),
            terminal_id: format!("term-{id}"),
            agent: "codex".into(),
            process_id: format!("pid-{id}"),
            title: id.into(),
            status: "idle".into(),
        }
    }
    impl Herdr for Fake {
        fn targets(&self, _: &str) -> Result<Vec<Target>, String> {
            Ok(self
                .0
                .lock()
                .unwrap()
                .panes
                .values()
                .map(|(t, _)| t.clone())
                .collect())
        }
        fn available(&self, w: &str, _: &str) -> Result<Vec<Target>, String> {
            Ok(self
                .targets(w)?
                .into_iter()
                .filter(|t| matches!(t.status.as_str(), "idle" | "done"))
                .collect())
        }
        fn create_pane(&self, _: &str, _: &str, _: &str) -> Result<Target, String> {
            let mut s = self.0.lock().unwrap();
            if s.create_error {
                return Err("timeout".into());
            }
            s.created += 1;
            let t = target(&format!("created-{}", s.created));
            s.panes.insert(t.pane_id.clone(), (t.clone(), None));
            Ok(t)
        }
        fn prepare_codex(
            &self,
            t: &Target,
            _: &str,
            resume: Option<&str>,
            _: &str,
        ) -> Result<Target, String> {
            let mut s = self.0.lock().unwrap();
            s.prepared.push(resume.map(str::to_string));
            if s.prepare_error {
                return Err("timeout".into());
            }
            let id = if s.mismatch {
                uuid::Uuid::new_v4().to_string()
            } else {
                resume
                    .map(str::to_string)
                    .unwrap_or_else(|| uuid::Uuid::new_v4().to_string())
            };
            let mut live = t.clone();
            live.process_id = uuid::Uuid::new_v4().to_string();
            s.panes.insert(t.pane_id.clone(), (live.clone(), Some(id)));
            Ok(live)
        }
        fn session_id(&self, t: &Target) -> Result<Option<String>, String> {
            let s = self.0.lock().unwrap();
            let (live, id) = s.panes.get(&t.pane_id).ok_or("binding.missing")?;
            if !live.same_identity(t) {
                return Err("binding.identity_changed".into());
            }
            Ok(if s.missing_id { None } else { id.clone() })
        }
        fn pane_exists(&self, t: &Target) -> Result<bool, String> {
            Ok(self.0.lock().unwrap().panes.contains_key(&t.pane_id))
        }
        fn close_pane(&self, t: &Target) -> Result<(), String> {
            let mut s = self.0.lock().unwrap();
            s.closed.push(t.pane_id.clone());
            if s.close_error {
                return Err("timeout".into());
            }
            s.panes.remove(&t.pane_id);
            if s.close_then_error {
                return Err("timeout".into());
            }
            Ok(())
        }
        fn send(&self, _: &Target, prompt: &str) -> Result<(), SendError> {
            let mut s = self.0.lock().unwrap();
            s.sent.push(prompt.into());
            if s.send_error {
                return Err(SendError {
                    message: "timeout".into(),
                    uncertain: true,
                });
            }
            Ok(())
        }
        fn find_created(&self, _: &str, _: &str) -> Result<Option<Target>, String> {
            Ok(None)
        }
    }
    fn fixture() -> (Workflow, Arc<Fake>) {
        let db = Connection::open_in_memory().unwrap();
        crate::db::init(&db).unwrap();
        db.execute_batch("INSERT INTO projects(id,name,root_path,herdr_workspace,created_at) VALUES ('p1','P1','.','workspace','now'),('p2','P2','.','workspace','now');
            INSERT INTO tasks(id,project_id,name,status,created_at,updated_at) VALUES ('a','p1','A','todo','now','now'),('b','p2','B','todo','now','now');").unwrap();
        let fake = Arc::new(Fake::default());
        (
            Workflow {
                db: Arc::new(Mutex::new(db)),
                herdr: fake.clone(),
            },
            fake,
        )
    }
    fn op() -> String {
        uuid::Uuid::new_v4().to_string()
    }
    fn status(app: &Workflow, task: &str) -> String {
        app.project_context(task).unwrap().2
    }
    fn saved(app: &Workflow, task: &str) -> Option<String> {
        view(&app.db.lock().unwrap(), task).unwrap().session_id
    }

    #[test]
    fn completes_and_resumes_exact_conversation_after_application_reopen_without_replaying() {
        let (app, fake) = fixture();
        app.start_task("a", "original task", &op()).unwrap();
        let session = saved(&app, "a").unwrap();
        assert_eq!(status(&app, "a"), "in_progress");
        assert!(app.complete_task("a", &op()).unwrap().warning.is_none());
        assert_eq!(status(&app, "a"), "done");
        assert!(app.binding("a").unwrap().target.is_none());
        assert_eq!(app.binding("a").unwrap().state, "dormant");
        let path = std::env::temp_dir().join(format!("kanban-flow-{}.db", op()));
        app.db
            .lock()
            .unwrap()
            .execute("VACUUM main INTO ?1", [path.to_str().unwrap()])
            .unwrap();
        drop(app);
        let persisted = Connection::open(&path).unwrap();
        crate::db::init(&persisted).unwrap();
        crate::db::recover_interrupted(&persisted).unwrap();
        let reopened = Workflow {
            db: Arc::new(Mutex::new(persisted)),
            herdr: fake.clone(),
        };
        reopened.start_task("a", "must not send", &op()).unwrap();
        assert_eq!(saved(&reopened, "a"), Some(session.clone()));
        let s = fake.0.lock().unwrap();
        assert_eq!(s.prepared, vec![None, Some(session)]);
        assert_eq!(s.sent, vec!["original task"]);
        assert_eq!(s.created, 2);
        assert_eq!(s.closed.len(), 1);
        drop(s);
        drop(reopened);
        std::fs::remove_file(path).unwrap();
    }
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
    #[test]
    fn repeated_drop_and_same_operation_never_repeat_first_prompt() {
        let (app, fake) = fixture();
        let id = op();
        app.start_task("a", "A", &id).unwrap();
        app.start_task("a", "A", &id).unwrap();
        app.start_task("a", "A", &op()).unwrap();
        assert_eq!(fake.0.lock().unwrap().prepared.len(), 1);
        assert_eq!(fake.0.lock().unwrap().sent, vec!["A"]);
        assert!(app.start_task("b", "B", &id).is_err());
    }
    #[test]
    fn missing_session_preserves_pane_and_completion_can_be_retried() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        fake.0.lock().unwrap().missing_id = true;
        assert!(app.complete_task("a", &op()).unwrap().warning.is_some());
        assert_eq!(status(&app, "a"), "done");
        assert!(app.binding("a").unwrap().target.is_some());
        assert!(fake.0.lock().unwrap().closed.is_empty());
        fake.0.lock().unwrap().missing_id = false;
        app.complete_task("a", &op()).unwrap();
        assert!(app.binding("a").unwrap().target.is_none());
    }
    #[test]
    fn close_timeout_does_not_block_other_tasks_and_retry_does_not_close_again_when_absent() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        fake.0.lock().unwrap().close_then_error = true;
        assert!(app.complete_task("a", &op()).unwrap().warning.is_some());
        assert!(app.start_task("a", "", &op()).is_err());
        app.start_task("b", "B", &op()).unwrap();
        app.complete_task("a", &op()).unwrap();
        assert_eq!(fake.0.lock().unwrap().closed.len(), 1);
        assert!(saved(&app, "a").is_some());
    }
    #[test]
    fn failed_restart_cannot_hide_unfinished_completion_cleanup() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        fake.0
            .lock()
            .unwrap()
            .panes
            .values_mut()
            .next()
            .unwrap()
            .0
            .process_id = "replacement".into();
        assert!(app.complete_task("a", &op()).unwrap().warning.is_some());
        assert!(app.start_task("a", "", &op()).is_err());
        assert_eq!(status(&app, "a"), "done");
        assert_eq!(
            crate::tasks::archive(&mut app.db.lock().unwrap(), "a").unwrap_err(),
            "archive.cleanup_required"
        );
        assert!(fake.0.lock().unwrap().closed.is_empty());
    }

    #[test]
    fn replaced_process_is_never_closed() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        fake.0
            .lock()
            .unwrap()
            .panes
            .values_mut()
            .next()
            .unwrap()
            .0
            .process_id = "replacement".into();
        assert!(app.complete_task("a", &op()).unwrap().warning.is_some());
        assert!(fake.0.lock().unwrap().closed.is_empty());
    }
    #[test]
    fn incorrect_resumed_identity_does_not_overwrite_saved_session() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        app.complete_task("a", &op()).unwrap();
        let original = saved(&app, "a");
        fake.0.lock().unwrap().mismatch = true;
        assert!(app.start_task("a", "", &op()).is_err());
        assert_eq!(saved(&app, "a"), original);
        assert_eq!(fake.0.lock().unwrap().sent.len(), 1);
    }
    #[test]
    fn uncertain_prompt_is_reconciled_through_existing_dispatch_evidence_without_resend() {
        let (app, fake) = fixture();
        fake.0.lock().unwrap().send_error = true;
        let id = op();
        assert!(app.start_task("a", "A", &id).is_err());
        assert!(app.start_task("a", "A", &op()).is_err());
        assert!(app.recover_lifecycle("a", &id).is_err());
        app.resolve(
            "a",
            &format!("{id}:dispatch"),
            true,
            "Observed task A in pane",
        )
        .unwrap();
        app.recover_lifecycle("a", &id).unwrap();
        assert_eq!(status(&app, "a"), "in_progress");
        assert_eq!(fake.0.lock().unwrap().sent, vec!["A"]);
    }
    #[test]
    fn failed_start_requires_pane_absence_before_releasing_reservation() {
        let (app, fake) = fixture();
        fake.0.lock().unwrap().prepare_error = true;
        let id = op();
        assert!(app.start_task("a", "A", &id).is_err());
        assert!(app.recover_lifecycle("a", &id).is_err());
        assert!(ensure_idle(&app.db.lock().unwrap(), "a", None).is_err());
        fake.0.lock().unwrap().panes.clear();
        app.recover_lifecycle("a", &id).unwrap();
        fake.0.lock().unwrap().prepare_error = false;
        app.start_task("a", "A", &op()).unwrap();
        assert_eq!(fake.0.lock().unwrap().sent, vec!["A"]);
    }
    #[test]
    fn restart_marks_pending_launch_unknown_and_never_automatically_replays_it() {
        let (app, fake) = fixture();
        let id = op();
        app.begin_flow("a", &id, "start").unwrap();
        crate::db::recover_interrupted(&app.db.lock().unwrap()).unwrap();
        assert!(app.start_task("a", "A", &op()).is_err());
        app.recover_lifecycle("a", &id).unwrap();
        app.start_task("a", "A", &op()).unwrap();
        assert_eq!(fake.0.lock().unwrap().sent, vec!["A"]);
    }
    #[test]
    fn no_prompt_fails_without_creating_and_legacy_tasks_require_repair() {
        let (app, fake) = fixture();
        assert!(app.start_task("a", "", &op()).is_err());
        app.db
            .lock()
            .unwrap()
            .execute("UPDATE tasks SET dispatched_to='old/pane' WHERE id='b'", [])
            .unwrap();
        assert!(app.start_task("b", "B", &op()).is_err());
        assert_eq!(fake.0.lock().unwrap().created, 0);
    }

    #[test]
    fn resume_commit_failure_recovers_by_exact_session_without_sending() {
        let (app, fake) = fixture();
        app.start_task("a", "A", &op()).unwrap();
        app.complete_task("a", &op()).unwrap();
        app.db.lock().unwrap().execute_batch("CREATE TRIGGER fail_resume BEFORE UPDATE OF status ON tasks WHEN new.status='in_progress' BEGIN SELECT RAISE(FAIL,'disk failure'); END;").unwrap();
        let id = op();
        assert!(app.start_task("a", "", &id).is_err());
        assert_eq!(status(&app, "a"), "done");
        app.db
            .lock()
            .unwrap()
            .execute_batch("DROP TRIGGER fail_resume")
            .unwrap();
        crate::db::recover_interrupted(&app.db.lock().unwrap()).unwrap();
        app.recover_lifecycle("a", &id).unwrap();
        assert_eq!(status(&app, "a"), "in_progress");
        assert_eq!(fake.0.lock().unwrap().sent, vec!["A"]);
    }

    #[test]
    fn late_recovery_cannot_release_a_newer_operations_binding() {
        let (app, _) = fixture();
        let old = op();
        app.begin_flow("a", &old, "start").unwrap();
        app.end_flow(&old, "failed", "").unwrap();
        let new = op();
        app.begin_flow("a", &new, "start").unwrap();
        app.reserve_target("a", &new, &target("new-pane")).unwrap();
        assert!(app.reserve_target("a", &old, &target("old-pane")).is_err());
        assert!(app.activate("a", &old, &target("old-pane")).is_err());
        assert_eq!(
            app.binding("a").unwrap().target.unwrap().pane_id,
            "new-pane"
        );
    }
}
#[derive(Default, Debug, serde::Serialize)]
pub struct Outcome {
    pub warning: Option<String>,
}
fn err(e: impl std::fmt::Display) -> String {
    e.to_string()
}
fn now() -> String {
    chrono::Utc::now().to_rfc3339()
}

pub fn ensure_idle(db: &Connection, task: &str, own: Option<&str>) -> Result<(), String> {
    crate::tasks::ensure_active(db, task)?;
    let active: Option<String> = db.query_row(
        "SELECT id FROM lifecycle_operations WHERE task_id=?1 AND state IN ('pending','unknown')",
        [task], |r| r.get(0)).optional().map_err(err)?;
    if active.as_deref().is_some_and(|id| Some(id) != own) {
        return Err("flow.verify_required".into());
    }
    Ok(())
}

fn ensure_operation(db: &Connection, task: &str, id: &str) -> Result<(), String> {
    ensure_idle(db, task, Some(id))?;
    let active: bool = db.query_row("SELECT EXISTS(SELECT 1 FROM lifecycle_operations WHERE id=?1 AND task_id=?2 AND state IN ('pending','unknown'))",params![id,task],|r|r.get(0)).map_err(err)?;
    if !active {
        return Err("dispatch.operation_conflict".into());
    }
    Ok(())
}
pub fn view(db: &Connection, task: &str) -> Result<Flow, String> {
    let session_id = db
        .query_row(
            "SELECT codex_session_id FROM task_sessions WHERE task_id=?1",
            [task],
            |r| r.get(0),
        )
        .optional()
        .map_err(err)?;
    let mut flow = Flow {
        session_id,
        operation_id: None,
        kind: None,
        state: None,
        error: String::new(),
        pane_id: None,
    };
    let op: Option<(String,String,String,String,Option<String>)> = db.query_row(
        "SELECT id,kind,state,error,target_json FROM lifecycle_operations WHERE task_id=?1 ORDER BY rowid DESC LIMIT 1",
        [task], |r|Ok((r.get(0)?,r.get(1)?,r.get(2)?,r.get(3)?,r.get(4)?))).optional().map_err(err)?;
    if let Some((id, kind, state, error, json)) = op {
        flow.operation_id = Some(id);
        flow.kind = Some(kind);
        flow.state = Some(state);
        flow.error = error;
        flow.pane_id = json
            .map(|s| serde_json::from_str::<Target>(&s))
            .transpose()
            .map_err(err)?
            .map(|t| t.pane_id);
    }
    Ok(flow)
}

impl Workflow {
    fn project_context(&self, task: &str) -> Result<(String, String, String), String> {
        self.db.lock().map_err(err)?.query_row(
            "SELECT p.herdr_workspace,p.root_path,t.status FROM tasks t JOIN projects p ON p.id=t.project_id WHERE t.id=?1",
            [task], |r|Ok((r.get(0)?,r.get(1)?,r.get(2)?))).map_err(err)
    }
    fn begin_flow(&self, task: &str, id: &str, kind: &str) -> Result<bool, String> {
        if uuid::Uuid::parse_str(id).is_err() {
            return Err("dispatch.operation_required".into());
        }
        let mut db = self.db.lock().map_err(err)?;
        let tx = db.transaction().map_err(err)?;
        crate::tasks::ensure_active(&tx, task)?;
        let old: Option<(String, String, String)> = tx
            .query_row(
                "SELECT task_id,kind,state FROM lifecycle_operations WHERE id=?1",
                [id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .optional()
            .map_err(err)?;
        if let Some((owner, old_kind, state)) = old {
            if owner != task || old_kind != kind {
                return Err("dispatch.operation_conflict".into());
            }
            return if state == "succeeded" {
                Ok(false)
            } else {
                Err("flow.verify_required".into())
            };
        }
        // A close interrupted by process death can be retried after rechecking the exact pane.
        if kind == "complete" {
            tx.execute("UPDATE lifecycle_operations SET state='failed' WHERE task_id=?1 AND kind='complete' AND state='unknown'",[task]).map_err(err)?;
        }
        ensure_idle(&tx, task, None)?;
        if binding(&tx, task)?.operation.is_some() {
            return Err("dispatch.verify_required".into());
        }
        tx.execute("INSERT INTO lifecycle_operations(id,task_id,kind,state,created_at) VALUES (?1,?2,?3,'pending',?4)",params![id,task,kind,now()]).map_err(err)?;
        tx.commit().map_err(err)?;
        Ok(true)
    }
    fn end_flow(&self, id: &str, state: &str, error: &str) -> Result<(), String> {
        self.db
            .lock()
            .map_err(err)?
            .execute(
                "UPDATE lifecycle_operations SET state=?2,error=?3 WHERE id=?1",
                params![id, state, error],
            )
            .map_err(err)?;
        Ok(())
    }
    fn reserve_target(&self, task: &str, op: &str, target: &Target) -> Result<(), String> {
        let mut db = self.db.lock().map_err(err)?;
        let tx = db.transaction().map_err(err)?;
        ensure_operation(&tx, task, op)?;
        if pane_owner(&tx, target)?.is_some_and(|owner| owner != task) {
            return Err("binding.occupied".into());
        }
        let json = serde_json::to_string(target).map_err(err)?;
        tx.execute("INSERT INTO task_bindings(task_id,session,pane_id,target_json,state) VALUES (?1,?2,?3,?4,'reserved') ON CONFLICT(task_id) DO UPDATE SET session=excluded.session,pane_id=excluded.pane_id,target_json=excluded.target_json,state='reserved'", params![task,target.session,target.pane_id,json]).map_err(err)?;
        tx.execute(
            "UPDATE lifecycle_operations SET target_json=?2 WHERE id=?1",
            params![op, json],
        )
        .map_err(err)?;
        tx.commit().map_err(err)
    }
    fn save_session(
        &self,
        task: &str,
        target: &Target,
        cwd: &str,
        expected: Option<&str>,
    ) -> Result<Option<String>, String> {
        let id = self.herdr.session_id(target)?;
        if expected.is_some() && id.as_deref() != expected {
            return Err("flow.session_mismatch".into());
        }
        if let Some(ref id) = id {
            if uuid::Uuid::parse_str(id).is_err() {
                return Err("flow.session_invalid".into());
            }
            self.db.lock().map_err(err)?.execute("INSERT INTO task_sessions(task_id,codex_session_id,cwd,updated_at) VALUES (?1,?2,?3,?4) ON CONFLICT(task_id) DO UPDATE SET codex_session_id=excluded.codex_session_id,cwd=excluded.cwd,updated_at=excluded.updated_at",params![task,id,cwd,now()]).map_err(err)?;
        }
        Ok(id)
    }
    fn activate(&self, task: &str, op: &str, target: &Target) -> Result<(), String> {
        let mut db = self.db.lock().map_err(err)?;
        let tx = db.transaction().map_err(err)?;
        ensure_operation(&tx, task, op)?;
        tx.execute(
            "UPDATE task_bindings SET state='valid',target_json=?2 WHERE task_id=?1",
            params![task, serde_json::to_string(target).map_err(err)?],
        )
        .map_err(err)?;
        tx.execute(
            "UPDATE tasks SET status='in_progress',updated_at=?2 WHERE id=?1",
            params![task, now()],
        )
        .map_err(err)?;
        tx.execute(
            "UPDATE lifecycle_operations SET state='succeeded',error='' WHERE id=?1",
            [op],
        )
        .map_err(err)?;
        tx.commit().map_err(err)
    }
    pub fn start_task(&self, task: &str, prompt: &str, op: &str) -> Result<Outcome, String> {
        let (workspace, cwd, _) = self.project_context(task)?;
        if !self.begin_flow(task, op, "start")? {
            return Ok(Outcome::default());
        }
        let mut touched = false;
        let result = (|| {
            let b = self.binding(task)?;
            let saved = view(&*self.db.lock().map_err(err)?, task)?.session_id;
            // A retained task pane (e.g. completion without a session ID) still owns its conversation.
            if let Some(target) = b.target {
                if self.herdr.pane_exists(&target)? {
                    let live = self.herdr.validate(&workspace, &target)?;
                    if live.agent != "codex" {
                        return Err("flow.codex_required".into());
                    }
                    self.save_session(task, &live, &cwd, None)?;
                    self.activate(task, op, &live)?;
                    return Ok(Outcome::default());
                }
                if saved.is_none() {
                    return Err("flow.session_missing".into());
                }
                self.db
                    .lock()
                    .map_err(err)?
                    .execute("DELETE FROM task_bindings WHERE task_id=?1", [task])
                    .map_err(err)?;
            } else if b.state == "repair" && saved.is_none() {
                return Err("binding.repair_required".into());
            }
            if saved.is_none() && prompt.trim().is_empty() {
                return Err("dispatch.empty".into());
            }
            let mut selected = None;
            for candidate in self.herdr.available(&workspace, &cwd)? {
                match self.reserve_target(task, op, &candidate) {
                    Ok(()) => {
                        selected = Some(candidate);
                        break;
                    }
                    Err(e) if e == "binding.occupied" => continue,
                    Err(e) => return Err(e),
                }
            }
            let target = match selected {
                Some(target) => target,
                None => {
                    // Persisted operation UUID is also the tab label for crash reconciliation.
                    touched = true;
                    let target =
                        self.herdr
                            .create_pane(&workspace, &cwd, &format!("kanban-{op}"))?;
                    self.reserve_target(task, op, &target)?;
                    target
                }
            };
            touched = true;
            let live = self.herdr.prepare_codex(
                &target,
                &cwd,
                saved.as_deref(),
                &format!("kb-{}", &op.replace('-', "")[..24]),
            )?;
            self.reserve_target(task, op, &live)?;
            self.save_session(task, &live, &cwd, saved.as_deref())?;
            self.db
                .lock()
                .map_err(err)?
                .execute(
                    "UPDATE task_bindings SET state='valid' WHERE task_id=?1",
                    [task],
                )
                .map_err(err)?;
            if saved.is_none() {
                self.dispatch_inner(
                    task,
                    &live.pane_id,
                    prompt,
                    &format!("{op}:dispatch"),
                    Some(op),
                )?;
                // Some integrations only report an ID after the first prompt.
                let _ = self.save_session(task, &live, &cwd, None);
            }
            self.activate(task, op, &live)?;
            Ok(Outcome::default())
        })();
        if let Err(ref e) = result {
            self.end_flow(op, if touched { "unknown" } else { "failed" }, e)?;
        }
        result
    }
    pub fn complete_task(&self, task: &str, op: &str) -> Result<Outcome, String> {
        let (workspace, cwd, _) = self.project_context(task)?;
        if !self.begin_flow(task, op, "complete")? {
            return Ok(Outcome::default());
        }
        // Completion is a business decision, independent from external cleanup success.
        self.db
            .lock()
            .map_err(err)?
            .execute(
                "UPDATE tasks SET status='done',updated_at=?2 WHERE id=?1",
                params![task, now()],
            )
            .map_err(err)?;
        let mut close_attempted = false;
        let result = (|| {
            if let Some(target) = self.binding(task)?.target {
                self.reserve_target(task, op, &target)?;
                if self.herdr.pane_exists(&target)? {
                    let live = self.herdr.validate(&workspace, &target)?;
                    if live.agent != "codex" {
                        return Err("flow.codex_required".into());
                    }
                    // Refresh from this exact live occupant; an old saved ID is not sufficient.
                    self.save_session(task, &live, &cwd, None)?
                        .ok_or("flow.session_missing")?;
                    close_attempted = true;
                    self.herdr.close_pane(&live)?;
                    if self.herdr.pane_exists(&live)? {
                        return Err("flow.close_pending".into());
                    }
                }
                self.db
                    .lock()
                    .map_err(err)?
                    .execute("DELETE FROM task_bindings WHERE task_id=?1", [task])
                    .map_err(err)?;
            }
            Ok::<_, String>(())
        })();
        match result {
            Ok(()) => {
                self.end_flow(op, "succeeded", "")?;
                Ok(Outcome::default())
            }
            Err(error) => {
                // Keep ownership, but allow a deliberate cleanup retry or reconnect to this task.
                self.db
                    .lock()
                    .map_err(err)?
                    .execute(
                        "UPDATE task_bindings SET state='valid' WHERE task_id=?1",
                        [task],
                    )
                    .map_err(err)?;
                self.end_flow(
                    op,
                    if close_attempted { "unknown" } else { "failed" },
                    &error,
                )?;
                Ok(Outcome {
                    warning: Some(error),
                })
            }
        }
    }
    /// Reconcile without sending, starting or closing anything. An unresolved launch may only
    /// be released after its exact pane is gone, or its already-confirmed dispatch is committed.
    pub fn recover_lifecycle(&self, task: &str, op: &str) -> Result<(), String> {
        let (workspace, _, _) = self.project_context(task)?;
        let flow = view(&*self.db.lock().map_err(err)?, task)?;
        if flow.operation_id.as_deref() != Some(op) || flow.state.as_deref() != Some("unknown") {
            return Err("dispatch.operation_conflict".into());
        }
        if flow.kind.as_deref() == Some("complete") {
            return Err("flow.retry_cleanup".into());
        }
        let b = self.binding(task)?;
        if b.operation.is_some() {
            return Err("dispatch.verify_required".into());
        }
        let sent: bool = self
            .db
            .lock()
            .map_err(err)?
            .query_row(
                "SELECT EXISTS(SELECT 1 FROM dispatch_operations WHERE id=?1 AND state='sent')",
                [format!("{op}:dispatch")],
                |r| r.get(0),
            )
            .map_err(err)?;
        if sent {
            return self.end_flow(op, "succeeded", "");
        }
        let prior: bool = self
            .db
            .lock()
            .map_err(err)?
            .query_row(
                "SELECT dispatched_at IS NOT NULL FROM tasks WHERE id=?1",
                [task],
                |r| r.get(0),
            )
            .map_err(err)?;
        if prior {
            if let (Some(expected), Some(old)) = (flow.session_id, b.target.as_ref()) {
                if let Some(live) = self.herdr.targets(&workspace)?.into_iter().find(|t| {
                    t.pane_id == old.pane_id
                        && t.terminal_id == old.terminal_id
                        && t.session == old.session
                }) {
                    if self.herdr.session_id(&live)?.as_deref() == Some(expected.as_str()) {
                        self.reserve_target(task, op, &live)?;
                        return self.activate(task, op, &live);
                    }
                }
            }
        }
        let target = match b.target {
            Some(t) => Some(t),
            None => self
                .herdr
                .find_created(&workspace, &format!("kanban-{op}"))?,
        };
        if let Some(target) = target {
            if self.herdr.pane_exists(&target)? {
                return Err("flow.close_before_reset".into());
            }
        }
        let mut db = self.db.lock().map_err(err)?;
        let tx = db.transaction().map_err(err)?;
        ensure_operation(&tx, task, op)?;
        tx.execute("DELETE FROM task_bindings WHERE task_id=?1", [task])
            .map_err(err)?;
        // A session created before an unsent first prompt must not make the next start skip it.
        let prior: bool = tx
            .query_row(
                "SELECT dispatched_at IS NOT NULL FROM tasks WHERE id=?1",
                [task],
                |r| r.get(0),
            )
            .map_err(err)?;
        if !prior {
            tx.execute("DELETE FROM task_sessions WHERE task_id=?1", [task])
                .map_err(err)?;
        }
        tx.execute("UPDATE lifecycle_operations SET state='failed',error='',evidence='Exact launch pane absent; no confirmed prompt' WHERE id=?1",[op]).map_err(err)?;
        tx.commit().map_err(err)
    }
}
