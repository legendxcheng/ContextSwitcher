//! The external CLI boundary. Every request is bounded; arguments never use a shell.
use crate::workflow::{Herdr, SendError, Target};
#[path = "codex_process.rs"]
mod codex_process;
#[cfg(test)]
#[path = "session_isolation_tests.rs"]
mod session_isolation_tests;
use serde_json::Value;
use std::{
    io::Read,
    path::PathBuf,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

#[derive(Clone)]
pub struct Cli {
    pub executable: PathBuf,
    pub session: String,
}

impl Cli {
    pub fn from_env() -> Self {
        let installed = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .map(|p| p.join("Programs/Herdr/bin/herdr.exe"));
        Self {
            executable: std::env::var_os("KANBAN_HERDR_EXECUTABLE")
                .map(PathBuf::from)
                .or_else(|| installed.filter(|p| p.is_file()))
                .unwrap_or_else(|| "herdr".into()),
            session: std::env::var("KANBAN_HERDR_SESSION").unwrap_or_else(|_| "default".into()),
        }
    }
    pub fn command(&self) -> Command {
        let mut cmd = Command::new(&self.executable);
        cmd.args(["--session", &self.session]);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x08000000);
        }
        cmd
    }
    pub fn request(&self, args: &[&str]) -> Result<Value, SendError> {
        let mut child = self
            .command()
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| SendError {
                message: format!("herdr.unavailable: {e}"),
                uncertain: false,
            })?;
        let stdout = child.stdout.take().unwrap();
        let stderr = child.stderr.take().unwrap();
        let read = |stream: Box<dyn Read + Send>| {
            thread::spawn(move || {
                let mut bytes = Vec::new();
                let _ = stream.take(4 * 1024 * 1024).read_to_end(&mut bytes);
                bytes
            })
        };
        let out = read(Box::new(stdout));
        let errors = read(Box::new(stderr));
        let start = Instant::now();
        let timeout = if args.starts_with(&["agent", "start"]) {
            40
        } else {
            12
        };
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Ok(status),
                Ok(None) if start.elapsed() < Duration::from_secs(timeout) => {
                    thread::sleep(Duration::from_millis(20))
                }
                _ => {
                    let _ = child.kill();
                    let _ = child.wait();
                    break Err(());
                }
            }
        };
        let stdout = out.join().unwrap_or_default();
        let stderr = errors.join().unwrap_or_default();
        let status = status.map_err(|_| SendError {
            message: "herdr.timeout".into(),
            uncertain: true,
        })?;
        if !status.success() {
            return Err(SendError {
                message: format!(
                    "herdr.failed: {}",
                    String::from_utf8_lossy(&stderr)
                        .chars()
                        .take(1000)
                        .collect::<String>()
                ),
                uncertain: true,
            });
        }
        // Unlike agent commands, pane send-text intentionally prints nothing
        // after its server acknowledgement. Only this command accepts silence.
        if (args.starts_with(&["pane", "send-text"]) || args.starts_with(&["pane", "close"]))
            && stdout.iter().all(u8::is_ascii_whitespace)
        {
            return Ok(Value::Null);
        }
        let doc: Value = serde_json::from_slice(&stdout).map_err(|_| SendError {
            message: "herdr.invalid_response".into(),
            uncertain: true,
        })?;
        if doc.get("ok") == Some(&Value::Bool(false))
            || doc.get("error").is_some_and(|e| !e.is_null())
        {
            return Err(SendError {
                message: "herdr.failed".into(),
                uncertain: true,
            });
        }
        Ok(doc)
    }
    fn check_target(&self, target: &Target) -> Result<(), SendError> {
        // Revalidate immediately before sending, after the ownership reservation.
        let doc = self
            .json(&["agent", "get", &target.pane_id])
            .map_err(|message| SendError {
                message,
                uncertain: false,
            })?;
        let live = self
            .live_target(
                &target.workspace_id,
                doc.pointer("/result/agent").ok_or(SendError {
                    message: "binding.missing".into(),
                    uncertain: false,
                })?,
            )
            .map_err(|message| SendError {
                message,
                uncertain: false,
            })?;
        if !live.same_identity(target) {
            return Err(SendError {
                message: "binding.identity_changed".into(),
                uncertain: false,
            });
        }
        Ok(())
    }
    fn json(&self, args: &[&str]) -> Result<Value, String> {
        self.request(args).map_err(|e| e.message)
    }
    fn resolve_workspace_id(&self, workspace: &str) -> Result<String, String> {
        let doc = self.json(&["workspace", "list"])?;
        let spaces = doc
            .pointer("/result/workspaces")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        let matches: Vec<_> = spaces
            .iter()
            .filter(|w| w.get("workspace_id").and_then(Value::as_str) == Some(workspace))
            .collect();
        if matches.len() != 1 {
            return Err("binding.workspace_ambiguous".into());
        }
        Ok(field(matches[0], "workspace_id")?.to_string())
    }
    pub fn live_target(&self, workspace_id: &str, agent: &Value) -> Result<Target, String> {
        if field(agent, "workspace_id")? != workspace_id {
            return Err("binding.identity_changed".into());
        }
        let pane = field(agent, "pane_id")?;
        let info = self.json(&["pane", "process-info", "--pane", pane])?;
        let group = info
            .pointer("/result/process_info/foreground_process_group_id")
            .and_then(Value::as_u64)
            .ok_or("binding.identity_unknown")?;
        let shell = info
            .pointer("/result/process_info/shell_pid")
            .and_then(Value::as_u64)
            .ok_or("binding.identity_unknown")?;
        if group == 0 {
            return Err("binding.identity_unknown".into());
        }
        Ok(Target {
            session: self.session.clone(),
            workspace_id: workspace_id.into(),
            pane_id: pane.into(),
            terminal_id: field(agent, "terminal_id")?.into(),
            agent: field(agent, "agent")?.into(),
            process_id: format!("{shell}:{group}"),
            title: agent
                .get("terminal_title_stripped")
                .and_then(Value::as_str)
                .unwrap_or("")
                .into(),
            status: agent
                .get("agent_status")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .into(),
        })
    }
}
fn field<'a>(v: &'a Value, key: &str) -> Result<&'a str, String> {
    v.get(key)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "herdr.invalid_response".into())
}
impl Herdr for Cli {
    fn session(&self) -> &str {
        &self.session
    }
    fn workspaces(&self) -> Result<Vec<crate::projects::Workspace>, String> {
        let doc = self.json(&["workspace", "list"])?;
        let spaces = doc
            .pointer("/result/workspaces")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        let directories = workspace_directories(self.session_file().as_deref()).unwrap_or_default();
        let mut ids = std::collections::HashSet::new();
        spaces
            .iter()
            .map(|w| {
                let id = field(w, "workspace_id")?;
                if !ids.insert(id.to_string()) {
                    return Err("herdr.invalid_response".into());
                }
                Ok(crate::projects::Workspace {
                    id: id.into(),
                    name: field(w, "label")?.into(),
                    directory: directories.get(id).cloned(),
                })
            })
            .collect()
    }
    fn create_workspace(
        &self,
        name: &str,
        cwd: &str,
    ) -> Result<crate::projects::Workspace, SendError> {
        let doc = self.request(&[
            "workspace",
            "create",
            "--label",
            name,
            "--cwd",
            cwd,
            "--no-focus",
        ])?;
        let parse = || {
            let w = doc
                .pointer("/result/workspace")
                .ok_or("herdr.invalid_response")?;
            Ok(crate::projects::Workspace {
                id: field(w, "workspace_id")?.into(),
                name: field(w, "label")?.into(),
                directory: Some(cwd.into()),
            })
        };
        parse().map_err(|message: String| SendError {
            message,
            uncertain: true,
        })
    }
    fn rename_workspace(&self, id: &str, name: &str) -> Result<(), String> {
        self.json(&["workspace", "rename", id, name]).map(|_| ())
    }
    fn available(&self, workspace: &str, cwd: &str) -> Result<Vec<Target>, String> {
        let workspace_id = self.resolve_workspace_id(workspace)?;
        let doc = self.json(&["pane", "list", "--workspace", &workspace_id])?;
        let panes = doc
            .pointer("/result/panes")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        let mut targets = Vec::new();
        for pane in panes {
            let id = field(pane, "pane_id")?;
            if let Ok((target, info)) = self.inspect_pane(&workspace_id, id) {
                let dir = info
                    .get("foreground_cwd")
                    .and_then(Value::as_str)
                    .or_else(|| info.get("cwd").and_then(Value::as_str));
                if dir.is_some_and(|d| same_directory(d, cwd)) && self.ready(&target, &info) {
                    targets.push(target);
                }
            }
        }
        targets.sort_by(|a, b| {
            (a.agent.as_str(), a.pane_id.as_str()).cmp(&(b.agent.as_str(), b.pane_id.as_str()))
        });
        Ok(targets)
    }
    fn create_pane(
        &self,
        workspace: &str,
        cwd: &str,
        label: &str,
        check_current: &dyn Fn() -> Result<(), String>,
    ) -> Result<Target, String> {
        check_current()?;
        if !std::path::Path::new(cwd).is_dir() {
            return Err("flow.directory_missing".into());
        }
        let id = self.resolve_workspace_id(workspace)?;
        check_current()?;
        let doc = self.json(&[
            "tab",
            "create",
            "--workspace",
            &id,
            "--cwd",
            cwd,
            "--label",
            label,
            "--no-focus",
        ])?;
        let pane = doc
            .pointer("/result/root_pane")
            .ok_or("herdr.invalid_response")?;
        let pane_id = field(pane, "pane_id")?;
        // The pane identity is recorded even when shell initialization has not finished.
        Ok(Target {
            session: self.session.clone(),
            workspace_id: id,
            pane_id: pane_id.into(),
            terminal_id: field(pane, "terminal_id")?.into(),
            agent: String::new(),
            process_id: String::new(),
            title: label.into(),
            status: "unknown".into(),
        })
    }
    fn prepare_codex(
        &self,
        target: &Target,
        cwd: &str,
        resume: Option<&str>,
        name: &str,
        check_current: &dyn Fn() -> Result<(), String>,
    ) -> Result<Target, String> {
        check_current()?;
        if let Some(id) = resume {
            uuid::Uuid::parse_str(id).map_err(|_| "flow.session_invalid")?;
        }
        if target.session != self.session {
            return Err("binding.identity_changed".into());
        }
        let (live, info) = self.inspect_pane(&target.workspace_id, &target.pane_id)?;
        if live.terminal_id != target.terminal_id
            || live.agent != target.agent
            || (!target.process_id.is_empty() && !live.same_identity(target))
        {
            return Err("binding.identity_changed".into());
        }
        if live.agent == "codex" {
            if !self.ready(&live, &info) {
                return Err("flow.not_idle".into());
            }
            self.check_target(&live).map_err(|e| e.message)?;
            check_current()?;
            self.json(&["agent", "send-keys", &live.pane_id, "ctrl+u"])?;
            self.send_checked(&live, "/quit", check_current)
                .map_err(|e| e.message)?;
        } else if !live.agent.is_empty() {
            return Err("flow.not_idle".into());
        }
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            check_current()?;
            let (shell, info) = self.inspect_pane(&target.workspace_id, &target.pane_id)?;
            if shell.terminal_id != target.terminal_id {
                return Err("binding.identity_changed".into());
            }
            if shell.agent.is_empty() && self.ready(&shell, &info) {
                break;
            }
            if Instant::now() >= deadline {
                return Err("flow.not_idle".into());
            }
            thread::sleep(Duration::from_millis(150));
        }
        let mut args = vec![
            "agent",
            "start",
            name,
            "--kind",
            "codex",
            "--pane",
            &target.pane_id,
            "--",
            // Hooks must inherit this pane's environment, including on resume.
            // A shared app-server may retain another pane's HERDR_PANE_ID.
            "--no-daemon",
        ];
        if let Some(id) = resume {
            args.extend(["resume", id]);
        }
        args.extend(["-C", cwd]);
        check_current()?;
        self.json(&args)?;
        let (live, info) = self.inspect_pane(&target.workspace_id, &target.pane_id)?;
        if live.terminal_id != target.terminal_id
            || live.agent != "codex"
            || !self.ready(&live, &info)
        {
            return Err("flow.not_idle".into());
        }
        if let Some(expected) = resume {
            let deadline = Instant::now() + Duration::from_secs(5);
            loop {
                if self.session_id(&live)?.as_deref() == Some(expected) {
                    break;
                }
                if Instant::now() >= deadline {
                    return Err("flow.session_mismatch".into());
                }
                thread::sleep(Duration::from_millis(150));
            }
        }
        Ok(live)
    }
    fn session_id(&self, target: &Target) -> Result<Option<String>, String> {
        self.check_target(target).map_err(|e| e.message)?;
        let doc = self.json(&["agent", "get", &target.pane_id])?;
        let agent = doc
            .pointer("/result/agent")
            .ok_or("herdr.invalid_response")?;
        let live = self.live_target(&target.workspace_id, agent)?;
        if !live.same_identity(target) {
            return Err("binding.identity_changed".into());
        }
        if let Some(id) = codex_session_id(agent)? {
            return Ok(Some(id));
        }
        // Codex defers the resume SessionStart hook until the first new input.
        // Before then, accept only our exact, independently observed resume
        // command and unique session write lock in the same live foreground process.
        // Never use a saved ID or another pane's report as evidence.
        if agent.get("interactive_ready").and_then(Value::as_bool) != Some(true) {
            return Ok(None);
        }
        let info = self.json(&["pane", "process-info", "--pane", &target.pane_id])?;
        let id = codex_resume_session(&info, target)?;
        self.check_target(target).map_err(|e| e.message)?;
        Ok(id)
    }
    fn pane_exists(&self, target: &Target) -> Result<bool, String> {
        if target.session != self.session {
            return Err("binding.identity_changed".into());
        }
        let doc = self.json(&["pane", "list", "--workspace", &target.workspace_id])?;
        let panes = doc
            .pointer("/result/panes")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        // Missing IDs are definitive only after a successful list response, never from a CLI error.
        Ok(panes
            .iter()
            .any(|p| p.get("pane_id").and_then(Value::as_str) == Some(&target.pane_id)))
    }
    fn close_pane(
        &self,
        target: &Target,
        check_current: &dyn Fn() -> Result<(), String>,
    ) -> Result<(), String> {
        check_current()?;
        self.check_target(target).map_err(|e| e.message)?;
        check_current()?;
        self.json(&["pane", "close", &target.pane_id])?;
        Ok(())
    }
    fn find_created(&self, workspace: &str, label: &str) -> Result<Option<Target>, String> {
        let id = self.resolve_workspace_id(workspace)?;
        let doc = self.json(&["tab", "list", "--workspace", &id])?;
        let tabs = doc
            .pointer("/result/tabs")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        let matches: Vec<_> = tabs
            .iter()
            .filter(|t| t.get("label").and_then(Value::as_str) == Some(label))
            .collect();
        if matches.is_empty() {
            return Ok(None);
        }
        // Do not reset an ambiguous creation; ask for explicit inspection of the labelled tab.
        Err("flow.close_before_reset".into())
    }
    fn validate(&self, workspace: &str, expected: &Target) -> Result<Target, String> {
        if self.resolve_workspace_id(workspace)? != expected.workspace_id {
            return Err("binding.workspace_ambiguous".into());
        }
        let doc = self.json(&["agent", "get", &expected.pane_id])?;
        let live = self.live_target(
            &expected.workspace_id,
            doc.pointer("/result/agent").ok_or("binding.missing")?,
        )?;
        if live.same_identity(expected) {
            Ok(live)
        } else {
            Err("binding.identity_changed".into())
        }
    }
    fn targets(&self, workspace: &str) -> Result<Vec<Target>, String> {
        let id = self.resolve_workspace_id(workspace)?;
        let doc = self.json(&["agent", "list"])?;
        let agents = doc
            .pointer("/result/agents")
            .and_then(Value::as_array)
            .ok_or("herdr.invalid_response")?;
        Ok(agents
            .iter()
            .filter(|a| a.get("workspace_id").and_then(Value::as_str) == Some(id.as_str()))
            .filter_map(|a| self.live_target(&id, a).ok())
            .collect())
    }
    fn send(&self, target: &Target, prompt: &str) -> Result<(), SendError> {
        self.send_checked(target, prompt, &|| Ok(()))
    }
    fn send_checked(
        &self,
        target: &Target,
        prompt: &str,
        check_current: &dyn Fn() -> Result<(), String>,
    ) -> Result<(), SendError> {
        let check = || {
            check_current().map_err(|message| SendError {
                message,
                uncertain: false,
            })
        };
        check()?;
        // Revalidate immediately before sending, after the ownership reservation.
        self.check_target(target)?;
        #[cfg(windows)]
        if target.agent == "codex" {
            return submit_windows_codex(
                &target.pane_id,
                prompt,
                |args| {
                    check()?;
                    self.request(args).map(|_| ())
                },
                || self.check_target(target),
            );
        }
        check()?;
        self.request(&["agent", "prompt", &target.pane_id, prompt])
            .map(|_| ())
    }
}

impl Cli {
    fn session_file(&self) -> Option<PathBuf> {
        if let Some(path) = std::env::var_os("KANBAN_HERDR_SESSION_FILE") {
            return Some(path.into());
        }
        // Never mix another session's IDs with default's persisted directory metadata.
        if self.session != "default" || std::env::var_os("HERDR_CONFIG_PATH").is_some() {
            return None;
        }
        std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .map(|p| p.join("herdr/session.json"))
    }
}
fn workspace_directories(
    path: Option<&std::path::Path>,
) -> Option<std::collections::HashMap<String, String>> {
    let file = std::fs::File::open(path?).ok()?;
    if file.metadata().ok()?.len() > 8 * 1024 * 1024 {
        return None;
    }
    let doc: Value = serde_json::from_reader(file.take(8 * 1024 * 1024)).ok()?;
    if doc.get("version")?.as_u64()? != 3 {
        return None;
    }
    let mut result = std::collections::HashMap::new();
    let mut ids = std::collections::HashSet::new();
    for workspace in doc.get("workspaces")?.as_array()? {
        let id = workspace.get("id")?.as_str()?;
        if !ids.insert(id) {
            return None;
        }
        if let Some(cwd) = workspace
            .get("identity_cwd")
            .and_then(Value::as_str)
            .filter(|d| std::path::Path::new(d).is_dir())
        {
            result.insert(id.into(), cwd.into());
        }
    }
    Some(result)
}

impl Cli {
    fn inspect_pane(&self, workspace: &str, pane: &str) -> Result<(Target, Value), String> {
        let doc = self.json(&["pane", "get", pane])?;
        let mut info = doc
            .pointer("/result/pane")
            .ok_or("herdr.invalid_response")?
            .clone();
        if info.get("agent").and_then(Value::as_str).is_some() {
            let doc = self.json(&["agent", "get", pane])?;
            info = doc
                .pointer("/result/agent")
                .ok_or("herdr.invalid_response")?
                .clone();
            return Ok((self.live_target(workspace, &info)?, info));
        }
        if field(&info, "workspace_id")? != workspace {
            return Err("binding.identity_changed".into());
        }
        let process = self.json(&["pane", "process-info", "--pane", pane])?;
        let p = process
            .pointer("/result/process_info")
            .ok_or("herdr.invalid_response")?;
        let shell = p.get("shell_pid").and_then(Value::as_u64).unwrap_or(0);
        let group = p
            .get("foreground_process_group_id")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let shell_ready = shell != 0 && shell == group;
        Ok((
            Target {
                session: self.session.clone(),
                workspace_id: workspace.into(),
                pane_id: pane.into(),
                terminal_id: field(&info, "terminal_id")?.into(),
                agent: String::new(),
                process_id: format!("{shell}:{group}"),
                title: String::new(),
                status: if shell_ready { "idle" } else { "unknown" }.into(),
            },
            info,
        ))
    }
    fn ready(&self, target: &Target, info: &Value) -> bool {
        if target.agent.is_empty() {
            return target.status == "idle";
        }
        target.agent == "codex"
            && matches!(target.status.as_str(), "idle" | "done")
            && info.get("interactive_ready").and_then(Value::as_bool) == Some(true)
            && info.get("launch_pending").and_then(Value::as_bool) != Some(true)
    }
}
fn same_directory(a: &str, b: &str) -> bool {
    match (std::fs::canonicalize(a), std::fs::canonicalize(b)) {
        (Ok(a), Ok(b)) => a == b,
        _ => false,
    }
}
fn codex_session_id(agent: &Value) -> Result<Option<String>, String> {
    let Some(session) = agent.get("agent_session").filter(|s| !s.is_null()) else {
        return Ok(None);
    };
    if session.get("agent").and_then(Value::as_str) != Some("codex")
        || session.get("kind").and_then(Value::as_str) != Some("id")
    {
        return Ok(None);
    };
    let id = field(session, "value")?;
    uuid::Uuid::parse_str(id).map_err(|_| "flow.session_invalid")?;
    Ok(Some(id.into()))
}

fn codex_resume_session(doc: &Value, target: &Target) -> Result<Option<String>, String> {
    let info = doc
        .pointer("/result/process_info")
        .ok_or("herdr.invalid_response")?;
    let shell = info["shell_pid"]
        .as_u64()
        .ok_or("binding.identity_unknown")?;
    let group = info["foreground_process_group_id"]
        .as_u64()
        .ok_or("binding.identity_unknown")?;
    if target.agent != "codex"
        || info["pane_id"].as_str() != Some(&target.pane_id)
        || group == 0
        || format!("{shell}:{group}") != target.process_id
    {
        return Err("binding.identity_changed".into());
    }
    let processes = info["foreground_processes"]
        .as_array()
        .ok_or("herdr.invalid_response")?;
    let candidates: Vec<_> = processes
        .iter()
        .filter(|p| p["pid"].as_u64() == Some(group))
        .collect();
    let [process] = candidates.as_slice() else {
        return Ok(None);
    };
    let Some(argv) = process["argv"]
        .as_array()
        .and_then(|a| a.iter().map(Value::as_str).collect::<Option<Vec<_>>>())
    else {
        return Ok(None);
    };
    let [exe, "--no-daemon", "resume", id, "-C", cwd] = argv.as_slice() else {
        return Ok(None);
    };
    let name = exe.rsplit(['/', '\\']).next().unwrap_or("");
    if !matches!(name.to_ascii_lowercase().as_str(), "codex" | "codex.exe") || cwd.is_empty() {
        return Ok(None);
    }
    uuid::Uuid::parse_str(id).map_err(|_| "flow.session_invalid")?;
    if codex_process::owns_only_session(group, id) {
        Ok(Some((*id).into()))
    } else {
        Err("flow.session_mismatch".into())
    }
}

// Windows Codex buffers pasted characters and can interpret Enter as a newline.
// A non-character key flushes that buffer synchronously before Enter. Do not also
// call agent prompt here: its scheduled Enter would create a second submission.
#[cfg(any(windows, test))]
fn submit_windows_codex(
    pane: &str,
    prompt: &str,
    mut request: impl FnMut(&[&str]) -> Result<(), SendError>,
    revalidate: impl FnOnce() -> Result<(), SendError>,
) -> Result<(), SendError> {
    request(&["pane", "send-text", pane, prompt])?;
    // Text may already be in the composer. Any later failure is uncertain, even
    // if the next CLI could not start; retain the reservation and never replay.
    let uncertain = |mut error: SendError| {
        error.uncertain = true;
        error
    };
    revalidate().map_err(uncertain)?;
    request(&["agent", "send-keys", pane, "right", "enter"]).map_err(uncertain)
}

#[cfg(test)]
mod tests {

    #[test]
    fn workspace_directory_metadata_is_versioned_and_never_uses_pane_cwd() {
        let path =
            std::env::temp_dir().join(format!("kanban-directories-{}.json", uuid::Uuid::new_v4()));
        let cwd = std::env::current_dir()
            .unwrap()
            .to_string_lossy()
            .to_string();
        let data = serde_json::json!({"version":3,"workspaces":[
            {"id":"w1","identity_cwd":cwd},
            {"id":"w2","panes":[{"cwd":cwd}]},
            {"id":"w3","identity_cwd":"Z:/kanban-nonexistent-directory"}
        ]});
        std::fs::write(&path, data.to_string()).unwrap();
        let dirs = super::workspace_directories(Some(&path)).unwrap();
        assert_eq!(dirs.len(), 1);
        assert_eq!(dirs["w1"], cwd);
        let mut incompatible = data.clone();
        incompatible["version"] = 4.into();
        std::fs::write(&path, incompatible.to_string()).unwrap();
        assert!(super::workspace_directories(Some(&path)).is_none());
        std::fs::write(&path, "{broken").unwrap();
        assert!(super::workspace_directories(Some(&path)).is_none());
        std::fs::remove_file(&path).unwrap();
        assert!(super::workspace_directories(Some(&path)).is_none());
        assert!(super::workspace_directories(None).is_none());
    }
    use super::*;

    #[test]
    fn codex_submit_flushes_paste_before_one_enter() {
        let mut calls = Vec::new();
        submit_windows_codex(
            "w1:p1",
            "line one\nline two",
            |args| {
                calls.push(args.iter().map(|s| s.to_string()).collect::<Vec<_>>());
                Ok(())
            },
            || Ok(()),
        )
        .unwrap_or_else(|e| panic!("{}", e.message));
        assert_eq!(
            calls,
            vec![
                vec!["pane", "send-text", "w1:p1", "line one\nline two"],
                vec!["agent", "send-keys", "w1:p1", "right", "enter"],
            ]
        );
    }

    #[test]
    fn codex_failure_after_paste_is_uncertain_and_never_replayed() {
        let mut count = 0;
        let error = submit_windows_codex(
            "w1:p1",
            "once",
            |_| {
                count += 1;
                if count == 1 {
                    Ok(())
                } else {
                    Err(SendError {
                        message: "could not start CLI".into(),
                        uncertain: false,
                    })
                }
            },
            || Ok(()),
        )
        .unwrap_err();
        assert!(error.uncertain);
        assert_eq!(count, 2);
    }

    #[test]
    fn codex_identity_change_after_paste_prevents_enter_and_requires_verification() {
        let mut count = 0;
        let error = submit_windows_codex(
            "w1:p1",
            "once",
            |_| {
                count += 1;
                Ok(())
            },
            || {
                Err(SendError {
                    message: "binding.identity_changed".into(),
                    uncertain: false,
                })
            },
        )
        .unwrap_err();
        assert!(error.uncertain);
        assert_eq!(count, 1);
    }
}
