//! Task/pane ownership and dispatch, shared by the Tauri command boundary.
use crate::models::DispatchRecord;
use rusqlite::{params, Connection, OptionalExtension};
use std::sync::{Arc, Mutex};

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize, PartialEq)]
pub struct Target {
    pub session: String,
    pub workspace_id: String,
    pub pane_id: String,
    pub terminal_id: String,
    pub agent: String,
    pub process_id: String,
    pub title: String,
    pub status: String,
}

pub struct SendError {
    pub message: String,
    pub uncertain: bool,
}

pub trait Herdr: Send + Sync {
    fn available(&self, _workspace: &str, _cwd: &str) -> Result<Vec<Target>, String> {
        Err("flow.unsupported".into())
    }
    fn create_pane(&self, _workspace: &str, _cwd: &str, _label: &str) -> Result<Target, String> {
        Err("flow.unsupported".into())
    }
    fn prepare_codex(
        &self,
        _target: &Target,
        _cwd: &str,
        _resume: Option<&str>,
        _name: &str,
    ) -> Result<Target, String> {
        Err("flow.unsupported".into())
    }
    fn session_id(&self, _target: &Target) -> Result<Option<String>, String> {
        Ok(None)
    }
    fn pane_exists(&self, _target: &Target) -> Result<bool, String> {
        Err("flow.unsupported".into())
    }
    fn close_pane(&self, _target: &Target) -> Result<(), String> {
        Err("flow.unsupported".into())
    }
    fn find_created(&self, _workspace: &str, _label: &str) -> Result<Option<Target>, String> {
        Err("flow.unsupported".into())
    }
    fn targets(&self, workspace: &str) -> Result<Vec<Target>, String>;
    fn validate(&self, workspace: &str, expected: &Target) -> Result<Target, String> {
        self.targets(workspace)?
            .into_iter()
            .find(|t| t.same_identity(expected))
            .ok_or_else(|| "binding.identity_changed".into())
    }
    fn send(&self, target: &Target, prompt: &str) -> Result<(), SendError>;
}

pub struct Workflow {
    pub db: Arc<Mutex<Connection>>,
    pub herdr: Arc<dyn Herdr>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Operation {
    pub id: String,
    pub task_id: String,
    pub workspace: String,
    pub target: Target,
    pub prompt: String,
    pub created_at: String,
    pub state: String,
    pub had_binding: bool,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Binding {
    pub state: String,
    pub target: Option<Target>,
    pub operation: Option<Operation>,
}

impl Target {
    pub fn same_identity(&self, other: &Self) -> bool {
        self.session == other.session
            && self.workspace_id == other.workspace_id
            && self.pane_id == other.pane_id
            && self.terminal_id == other.terminal_id
            && self.agent == other.agent
            && self.process_id == other.process_id
    }
}

fn operation_row(r: &rusqlite::Row) -> rusqlite::Result<Operation> {
    let json: String = r.get(3)?;
    let target = serde_json::from_str(&json).map_err(|e| {
        rusqlite::Error::FromSqlConversionFailure(3, rusqlite::types::Type::Text, Box::new(e))
    })?;
    Ok(Operation {
        id: r.get(0)?,
        task_id: r.get(1)?,
        workspace: r.get(2)?,
        target,
        prompt: r.get(4)?,
        created_at: r.get(5)?,
        state: r.get(6)?,
        had_binding: r.get(7)?,
    })
}
const OP_SELECT: &str = "SELECT id,task_id,workspace,target_json,prompt,created_at,state,had_binding FROM dispatch_operations";

pub fn binding(conn: &Connection, task: &str) -> Result<Binding, String> {
    let operation = conn
        .query_row(
            &format!("{OP_SELECT} WHERE task_id=?1 AND state IN ('pending','unknown')"),
            [task],
            operation_row,
        )
        .optional()
        .map_err(err)?;
    let stored: Option<(String, String)> = conn
        .query_row(
            "SELECT target_json,state FROM task_bindings WHERE task_id=?1",
            [task],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .optional()
        .map_err(err)?;
    let target = stored
        .as_ref()
        .map(|(json, _)| serde_json::from_str(json))
        .transpose()
        .map_err(err)?;
    let state = if let Some(ref op) = operation {
        op.state.clone()
    } else if let Some((_, ref state)) = stored {
        state.clone()
    } else {
        let legacy: bool = conn
            .query_row(
                "SELECT status='in_progress' OR dispatched_to IS NOT NULL FROM tasks WHERE id=?1",
                [task],
                |r| r.get(0),
            )
            .map_err(err)?;
        let saved: bool = conn
            .query_row(
                "SELECT EXISTS(SELECT 1 FROM task_sessions WHERE task_id=?1)",
                [task],
                |r| r.get(0),
            )
            .map_err(err)?;
        if saved {
            "dormant".into()
        } else if legacy {
            "repair".into()
        } else {
            "unbound".into()
        }
    };
    Ok(Binding {
        state,
        target,
        operation,
    })
}

pub fn pane_owner(conn: &Connection, target: &Target) -> Result<Option<String>, String> {
    conn.query_row(
        "SELECT task_id FROM task_bindings WHERE session=?1 AND pane_id=?2",
        params![target.session, target.pane_id],
        |r| r.get(0),
    )
    .optional()
    .map_err(err)
}
fn ensure_available(conn: &Connection, target: &Target, task: &str) -> Result<(), String> {
    if pane_owner(conn, target)?
        .as_deref()
        .is_some_and(|owner| owner != task)
    {
        Err("binding.occupied".into())
    } else {
        Ok(())
    }
}

impl Workflow {
    pub fn repair(&self, task: &str, pane: &str) -> Result<(), String> {
        let workspace = self.workspace(task)?;
        let target = self
            .herdr
            .targets(&workspace)?
            .into_iter()
            .find(|t| t.pane_id == pane)
            .ok_or("binding.missing")?;
        let mut conn = self.db.lock().map_err(err)?;
        let tx = conn.transaction().map_err(err)?;
        crate::lifecycle::ensure_idle(&tx, task, None)?;
        if binding(&tx, task)?.operation.is_some() {
            return Err("dispatch.verify_required".into());
        }
        ensure_available(&tx, &target, task)?;
        tx.execute("INSERT INTO task_bindings(task_id,session,pane_id,target_json,state) VALUES (?1,?2,?3,?4,'valid') ON CONFLICT(task_id) DO UPDATE SET session=excluded.session,pane_id=excluded.pane_id,target_json=excluded.target_json,state='valid'",
            params![task,target.session,pane,serde_json::to_string(&target).map_err(err)?]).map_err(err)?;
        tx.commit().map_err(err)
    }
    fn workspace(&self, task: &str) -> Result<String, String> {
        let db = self.db.lock().map_err(err)?;
        crate::tasks::ensure_active(&db, task)?;
        db.query_row(
            "SELECT p.herdr_workspace FROM tasks t JOIN projects p ON p.id=t.project_id WHERE t.id=?1",
            [task],|r|r.get(0)).map_err(err)
    }
    pub fn binding(&self, task: &str) -> Result<Binding, String> {
        binding(&*self.db.lock().map_err(err)?, task)
    }
    pub fn target(&self, task: &str, require_developing: bool) -> Result<Target, String> {
        crate::lifecycle::ensure_idle(&*self.db.lock().map_err(err)?, task, None)?;
        let b = self.binding(task)?;
        if b.state != "valid" {
            return Err("binding.repair_required".into());
        }
        if require_developing {
            let status: String = self
                .db
                .lock()
                .map_err(err)?
                .query_row("SELECT status FROM tasks WHERE id=?1", [task], |r| r.get(0))
                .map_err(err)?;
            if status != "in_progress" {
                return Err("binding.not_developing".into());
            }
        }
        let target = b.target.ok_or("binding.repair_required")?;
        self.herdr.validate(&self.workspace(task)?, &target)
    }
    pub fn dispatch(
        &self,
        task: &str,
        pane: &str,
        prompt: &str,
        operation: &str,
    ) -> Result<DispatchRecord, String> {
        self.dispatch_inner(task, pane, prompt, operation, None)
    }
    pub(crate) fn dispatch_inner(
        &self,
        task: &str,
        pane: &str,
        prompt: &str,
        operation: &str,
        lifecycle: Option<&str>,
    ) -> Result<DispatchRecord, String> {
        if prompt.trim().is_empty() {
            return Err("dispatch.empty".into());
        }
        if operation.is_empty() {
            return Err("dispatch.operation_required".into());
        }
        let workspace = self.workspace(task)?;
        // A durable operation ID makes retries safe even after an app restart.
        if let Some(op) = self
            .db
            .lock()
            .map_err(err)?
            .query_row(
                &format!("{OP_SELECT} WHERE id=?1"),
                [operation],
                operation_row,
            )
            .optional()
            .map_err(err)?
        {
            if op.task_id != task || op.target.pane_id != pane || op.prompt != prompt {
                return Err("dispatch.operation_conflict".into());
            }
            return if op.state == "sent" {
                Ok(record(&op))
            } else {
                Err("dispatch.verify_required".into())
            };
        }
        let target = self
            .herdr
            .targets(&workspace)?
            .into_iter()
            .find(|t| t.pane_id == pane)
            .ok_or("binding.missing")?;
        let op;
        {
            let mut conn = self.db.lock().map_err(err)?;
            let tx = conn.transaction().map_err(err)?;
            crate::lifecycle::ensure_idle(&tx, task, lifecycle)?;
            let b = binding(&tx, task)?;
            if b.operation.is_some() {
                return Err("dispatch.verify_required".into());
            }
            if b.state == "repair" {
                return Err("binding.repair_required".into());
            }
            if b.target
                .as_ref()
                .is_some_and(|old| !old.same_identity(&target))
            {
                return Err("binding.repair_required".into());
            }
            ensure_available(&tx, &target, task)?;
            op = Operation {
                id: operation.into(),
                task_id: task.into(),
                workspace,
                target: target.clone(),
                prompt: prompt.into(),
                created_at: chrono::Utc::now().to_rfc3339(),
                state: "pending".into(),
                had_binding: b.target.is_some(),
            };
            let json = serde_json::to_string(&target).map_err(err)?;
            tx.execute("INSERT INTO task_bindings(task_id,session,pane_id,target_json,state) VALUES (?1,?2,?3,?4,'reserved') ON CONFLICT(task_id) DO UPDATE SET state='reserved'",
                params![task,target.session,pane,json]).map_err(|_|"binding.occupied".to_string())?;
            tx.execute("INSERT INTO dispatch_operations(id,task_id,workspace,target_json,prompt,created_at,state,had_binding) VALUES (?1,?2,?3,?4,?5,?6,'pending',?7)",
                params![op.id,task,op.workspace,json,prompt,op.created_at,op.had_binding]).map_err(|_|"dispatch.verify_required".to_string())?;
            tx.commit().map_err(err)?;
        }
        match self.herdr.send(&target, prompt) {
            Ok(()) => match self.finish(&op, true, "") {
                Ok(()) => Ok(record(&op)),
                Err(_) => {
                    self.mark_unknown(&op.id);
                    Err("dispatch.verify_required".into())
                }
            },
            Err(error) if error.uncertain => {
                self.mark_unknown(&op.id);
                Err(format!("dispatch.verify_required: {}", error.message))
            }
            Err(error) => {
                self.finish(&op, false, &error.message)?;
                Err(error.message)
            }
        }
    }
    fn mark_unknown(&self, id: &str) {
        if let Ok(conn) = self.db.lock() {
            let _ = conn.execute(
                "UPDATE dispatch_operations SET state='unknown' WHERE id=?1 AND state='pending'",
                [id],
            );
        }
    }
    pub fn resolve(
        &self,
        task: &str,
        operation: &str,
        sent: bool,
        evidence: &str,
    ) -> Result<(), String> {
        if evidence.trim().len() < 3 {
            return Err("dispatch.evidence_required".into());
        }
        let op = self
            .binding(task)?
            .operation
            .ok_or("dispatch.operation_conflict")?;
        if op.id != operation || op.state != "unknown" {
            return Err("dispatch.operation_conflict".into());
        }
        // This records an explicit user's observation, never an inferred send result.
        self.finish(&op, sent, evidence.trim())
    }
    fn finish(&self, op: &Operation, sent: bool, evidence: &str) -> Result<(), String> {
        let mut conn = self.db.lock().map_err(err)?;
        let tx = conn.transaction().map_err(err)?;
        let changed = tx.execute("UPDATE dispatch_operations SET state=?1,evidence=?2 WHERE id=?3 AND state IN ('pending','unknown')",
            params![if sent {"sent"} else {"not_sent"},evidence,op.id]).map_err(err)?;
        if changed != 1 {
            return Err("dispatch.operation_conflict".into());
        }
        if sent {
            if tx.execute("UPDATE tasks SET status='in_progress',prompt_snapshot=?1,dispatched_at=?2,dispatched_to=?3,updated_at=?2 WHERE id=?4",
                params![op.prompt,op.created_at,format!("{}/{}",op.workspace,op.target.pane_id),op.task_id]).map_err(err)? != 1 { return Err("binding.missing".into()); }
            tx.execute(
                "UPDATE task_bindings SET state='valid' WHERE task_id=?1",
                [&op.task_id],
            )
            .map_err(err)?;
        } else if op.had_binding {
            tx.execute(
                "UPDATE task_bindings SET state='valid' WHERE task_id=?1",
                [&op.task_id],
            )
            .map_err(err)?;
        } else {
            tx.execute("DELETE FROM task_bindings WHERE task_id=?1", [&op.task_id])
                .map_err(err)?;
        }
        tx.commit().map_err(err)
    }
}
fn record(op: &Operation) -> DispatchRecord {
    DispatchRecord {
        task_id: op.task_id.clone(),
        target_workspace: op.workspace.clone(),
        target_agent: op.target.pane_id.clone(),
        prompt_snapshot: op.prompt.clone(),
        dispatched_at: op.created_at.clone(),
    }
}

fn err(error: impl std::fmt::Display) -> String {
    error.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Default)]
    struct FakeHerdr {
        sent: Mutex<Vec<String>>,
        uncertain: Mutex<bool>,
        unavailable: Mutex<bool>,
        replaced: Mutex<bool>,
    }
    impl Herdr for FakeHerdr {
        fn targets(&self, _: &str) -> Result<Vec<Target>, String> {
            Ok(vec![
                Target {
                    session: "default".into(),
                    workspace_id: "w1".into(),
                    pane_id: "w1:p1".into(),
                    terminal_id: "term-a".into(),
                    agent: "codex".into(),
                    process_id: "100".into(),
                    title: "Agent A".into(),
                    status: "idle".into(),
                },
                Target {
                    session: "default".into(),
                    workspace_id: "w1".into(),
                    pane_id: "w1:p2".into(),
                    terminal_id: "term-b".into(),
                    agent: "codex".into(),
                    process_id: "200".into(),
                    title: "Agent B".into(),
                    status: "idle".into(),
                },
            ])
        }
        fn validate(&self, workspace: &str, expected: &Target) -> Result<Target, String> {
            if *self.replaced.lock().unwrap() {
                return Err("binding.identity_changed".into());
            }
            self.targets(workspace)?
                .into_iter()
                .find(|t| t.same_identity(expected))
                .ok_or("binding.missing".into())
        }
        fn send(&self, _: &Target, prompt: &str) -> Result<(), SendError> {
            if *self.unavailable.lock().unwrap() {
                return Err(SendError {
                    message: "herdr.unavailable".into(),
                    uncertain: false,
                });
            }
            self.sent.lock().unwrap().push(prompt.into());
            if *self.uncertain.lock().unwrap() {
                Err(SendError {
                    message: "timeout".into(),
                    uncertain: true,
                })
            } else {
                Ok(())
            }
        }
    }
    fn fixture() -> (Workflow, Arc<FakeHerdr>) {
        let db = Connection::open_in_memory().unwrap();
        crate::db::init(&db).unwrap();
        db.execute_batch("INSERT INTO projects(id,name,root_path,herdr_workspace,created_at) VALUES ('p1','One','.','one','now'),('p2','Two','.','one','now');
            INSERT INTO tasks(id,project_id,name,status,created_at,updated_at) VALUES ('a','p1','A','todo','now','now'),('b','p2','B','todo','now','now');").unwrap();
        let herdr = Arc::new(FakeHerdr::default());
        (
            Workflow {
                db: Arc::new(Mutex::new(db)),
                herdr: herdr.clone(),
            },
            herdr,
        )
    }
    #[test]
    fn failed_archive_rolls_back_the_card_and_binding_then_retry_can_succeed() {
        let (app, external) = fixture();
        app.dispatch("a", "w1:p1", "Task A", "op-a").unwrap();
        let mut db = app.db.lock().unwrap();
        db.execute_batch("UPDATE tasks SET status='done' WHERE id='a';
            CREATE TRIGGER fail_archive BEFORE DELETE ON task_bindings BEGIN SELECT RAISE(ABORT,'disk failure'); END;").unwrap();
        assert!(crate::tasks::archive(&mut db, "a").is_err());
        assert_eq!(crate::tasks::list(&db, "p1").unwrap().len(), 1);
        assert_eq!(binding(&db, "a").unwrap().target.unwrap().pane_id, "w1:p1");
        db.execute_batch("DROP TRIGGER fail_archive").unwrap();
        crate::tasks::archive(&mut db, "a").unwrap();
        assert!(crate::tasks::list(&db, "p1").unwrap().is_empty());
        assert_eq!(*external.sent.lock().unwrap(), vec!["Task A"]);
    }

    #[test]
    fn archive_and_dispatch_are_mutually_exclusive() {
        let (app, external) = fixture();
        app.db
            .lock()
            .unwrap()
            .execute("UPDATE tasks SET status='done' WHERE id='a'", [])
            .unwrap();
        let gate = std::sync::Barrier::new(2);
        let (archived, dispatched) = std::thread::scope(|scope| {
            let archive = scope.spawn(|| {
                gate.wait();
                crate::tasks::archive(&mut app.db.lock().unwrap(), "a")
            });
            let dispatch = scope.spawn(|| {
                gate.wait();
                app.dispatch("a", "w1:p1", "Once", "race")
            });
            (archive.join().unwrap(), dispatch.join().unwrap())
        });
        assert_ne!(archived.is_ok(), dispatched.is_ok());
        if archived.is_ok() {
            assert!(crate::tasks::list(&app.db.lock().unwrap(), "p1")
                .unwrap()
                .is_empty());
            assert!(external.sent.lock().unwrap().is_empty());
        } else {
            assert_eq!(
                crate::tasks::list(&app.db.lock().unwrap(), "p1").unwrap()[0].status,
                crate::models::TaskStatus::InProgress
            );
            assert_eq!(*external.sent.lock().unwrap(), vec!["Once"]);
        }
    }

    #[test]
    fn archive_releases_ownership_for_the_next_task_and_rejects_late_activation() {
        let (app, external) = fixture();
        app.dispatch("a", "w1:p1", "Task A", "op-a").unwrap();
        {
            let mut db = app.db.lock().unwrap();
            db.execute("UPDATE tasks SET status='done' WHERE id='a'", [])
                .unwrap();
            crate::tasks::archive(&mut db, "a").unwrap();
        }
        assert_eq!(app.repair("a", "w1:p1").unwrap_err(), "task.archived");
        assert_eq!(
            app.dispatch("a", "w1:p1", "late", "op-late").unwrap_err(),
            "task.archived"
        );
        assert_eq!(
            app.start_task("a", "late", &uuid::Uuid::new_v4().to_string())
                .unwrap_err(),
            "task.archived"
        );
        assert_eq!(app.target("a", true).unwrap_err(), "task.archived");
        app.dispatch("b", "w1:p1", "Task B", "op-b").unwrap();
        assert_eq!(*external.sent.lock().unwrap(), vec!["Task A", "Task B"]);
    }

    #[test]
    fn a_pane_cannot_receive_another_projects_task() {
        let (app, external) = fixture();
        assert_eq!(
            app.dispatch("a", "w1:p1", "Task A", "op-a")
                .unwrap()
                .target_agent,
            "w1:p1"
        );
        assert_eq!(
            app.dispatch("b", "w1:p1", "Task B", "op-b").unwrap_err(),
            "binding.occupied"
        );
        assert_eq!(*external.sent.lock().unwrap(), vec!["Task A"]);
    }
    #[test]
    fn a_known_unsent_failure_releases_only_the_new_reservation() {
        let (app, external) = fixture();
        *external.unavailable.lock().unwrap() = true;
        assert!(app.dispatch("a", "w1:p1", "First", "failed").is_err());
        assert_eq!(app.binding("a").unwrap().state, "unbound");
        *external.unavailable.lock().unwrap() = false;
        app.dispatch("b", "w1:p1", "B", "succeeds").unwrap();
        *external.unavailable.lock().unwrap() = true;
        assert!(app.dispatch("b", "w1:p1", "Again", "failed-again").is_err());
        assert_eq!(app.binding("b").unwrap().state, "valid");
        assert_eq!(*external.sent.lock().unwrap(), vec!["B"]);
    }
    #[test]
    fn a_successful_send_with_failed_commit_remains_recoverable_without_replay() {
        let (app, external) = fixture();
        app.db.lock().unwrap().execute_batch("CREATE TRIGGER fail_finish BEFORE UPDATE OF status ON tasks BEGIN SELECT RAISE(ABORT,'disk failure'); END;").unwrap();
        assert_eq!(
            app.dispatch("a", "w1:p1", "Once", "op").unwrap_err(),
            "dispatch.verify_required"
        );
        assert_eq!(app.binding("a").unwrap().state, "unknown");
        assert!(app.dispatch("b", "w1:p1", "Never", "other").is_err());
        app.db
            .lock()
            .unwrap()
            .execute_batch("DROP TRIGGER fail_finish")
            .unwrap();
        app.resolve("a", "op", true, "Observed Once in target pane")
            .unwrap();
        assert_eq!(app.binding("a").unwrap().state, "valid");
        assert_eq!(*external.sent.lock().unwrap(), vec!["Once"]);
    }
    #[test]
    fn a_replaced_agent_cannot_be_used_until_explicit_repair() {
        let (app, external) = fixture();
        app.dispatch("a", "w1:p1", "A", "op").unwrap();
        *external.replaced.lock().unwrap() = true;
        assert_eq!(
            app.target("a", true).unwrap_err(),
            "binding.identity_changed"
        );
        assert_eq!(*external.sent.lock().unwrap(), vec!["A"]);
    }
    #[test]
    fn closing_a_task_cancels_its_pending_attachment_before_spawning() {
        let (app, _) = fixture();
        app.dispatch("a", "w1:p1", "A", "op").unwrap();
        let manager = crate::terminal::TerminalManager::default();
        manager.select("late", "a").unwrap();
        manager.close_task("a");
        let cli = crate::herdr::Cli {
            executable: "not-a-real-herdr".into(),
            session: "default".into(),
        };
        assert_eq!(
            manager
                .open(Arc::new(app), &cli, "a", "late", 80, 24, Arc::new(|_| true))
                .unwrap_err(),
            "terminal.stale"
        );
    }
    #[test]
    fn repeating_the_same_operation_does_not_resend_but_a_new_dispatch_can_continue() {
        let (app, external) = fixture();
        app.dispatch("a", "w1:p1", "First", "op-1").unwrap();
        app.dispatch("a", "w1:p1", "First", "op-1").unwrap();
        app.dispatch("a", "w1:p1", "Continue", "op-2").unwrap();
        assert_eq!(*external.sent.lock().unwrap(), vec!["First", "Continue"]);
    }
    #[test]
    fn uncertain_send_requires_evidence_and_recovery_never_replays_the_prompt() {
        let (app, external) = fixture();
        *external.uncertain.lock().unwrap() = true;
        assert!(app.dispatch("a", "w1:p1", "Once", "op-1").is_err());
        assert_eq!(app.binding("a").unwrap().state, "unknown");
        assert!(app.dispatch("a", "w1:p1", "Once", "op-2").is_err());
        assert!(app.resolve("a", "op-1", true, "").is_err());
        app.resolve("a", "op-1", true, "Confirmed in the target terminal")
            .unwrap();
        assert_eq!(app.binding("a").unwrap().state, "valid");
        assert_eq!(*external.sent.lock().unwrap(), vec!["Once"]);
    }
    #[test]
    fn concurrent_projects_cannot_both_dispatch_to_one_pane() {
        let (app, external) = fixture();
        let app = Arc::new(app);
        let barrier = Arc::new(std::sync::Barrier::new(2));
        let handles: Vec<_> = ["a", "b"]
            .into_iter()
            .map(|task| {
                let app = app.clone();
                let barrier = barrier.clone();
                std::thread::spawn(move || {
                    barrier.wait();
                    app.dispatch(task, "w1:p1", task, task).is_ok()
                })
            })
            .collect();
        assert_eq!(
            handles
                .into_iter()
                .map(|h| usize::from(h.join().unwrap()))
                .sum::<usize>(),
            1
        );
        assert_eq!(external.sent.lock().unwrap().len(), 1);
    }
    #[test]
    fn interrupted_operations_survive_reopen_and_can_be_resolved_without_resending() {
        let (app, external) = fixture();
        *external.uncertain.lock().unwrap() = true;
        assert!(app.dispatch("a", "w1:p1", "Once", "op-1").is_err());
        // Simulate a crash between send and result persistence, then application startup.
        app.db
            .lock()
            .unwrap()
            .execute(
                "UPDATE dispatch_operations SET state='pending' WHERE id='op-1'",
                [],
            )
            .unwrap();
        crate::db::init(&app.db.lock().unwrap()).unwrap();
        crate::db::recover_interrupted(&app.db.lock().unwrap()).unwrap();
        let reopened = Workflow {
            db: app.db.clone(),
            herdr: app.herdr.clone(),
        };
        assert_eq!(reopened.binding("a").unwrap().state, "unknown");
        reopened
            .resolve("a", "op-1", false, "Target inspected; prompt absent")
            .unwrap();
        assert_eq!(reopened.binding("a").unwrap().state, "unbound");
        assert_eq!(*external.sent.lock().unwrap(), vec!["Once"]);
    }
    #[test]
    fn legacy_shared_targets_require_explicit_unique_repairs_without_sending() {
        let (app, external) = fixture();
        app.db
            .lock()
            .unwrap()
            .execute(
                "UPDATE tasks SET status='in_progress',dispatched_to='one/w1:p1'",
                [],
            )
            .unwrap();
        assert_eq!(app.binding("a").unwrap().state, "repair");
        assert_eq!(app.binding("b").unwrap().state, "repair");
        assert!(app.target("a", true).is_err());
        app.repair("a", "w1:p1").unwrap();
        assert_eq!(app.repair("b", "w1:p1").unwrap_err(), "binding.occupied");
        app.repair("b", "w1:p2").unwrap();
        assert_eq!(app.target("a", true).unwrap().pane_id, "w1:p1");
        assert_eq!(app.target("b", true).unwrap().pane_id, "w1:p2");
        assert!(external.sent.lock().unwrap().is_empty());
    }
    #[test]
    #[ignore = "requires an explicitly prepared isolated Herdr acceptance workspace"]
    fn live_dispatch_and_exclusive_binding() {
        let workspace =
            std::env::var("KANBAN_LIVE_WORKSPACE").expect("explicit acceptance workspace required");
        assert!(workspace.starts_with("kanban-acceptance-"));
        let (mut app, _) = fixture();
        app.herdr = Arc::new(crate::herdr::Cli::from_env());
        app.db
            .lock()
            .unwrap()
            .execute("UPDATE projects SET herdr_workspace=?1", [&workspace])
            .unwrap();
        let targets = app.herdr.targets(&workspace).unwrap();
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
        app.db
            .lock()
            .unwrap()
            .execute("UPDATE projects SET herdr_workspace=?1", [&workspace])
            .unwrap();
        let pane = app.herdr.targets(&workspace).unwrap()[0].pane_id.clone();
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
}
