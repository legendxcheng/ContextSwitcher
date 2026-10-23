//! The external CLI boundary. Every request is bounded; arguments never use a shell.
use crate::workflow::{Herdr, SendError, Target};
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
            executable: installed
                .filter(|p| p.is_file())
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
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Ok(status),
                Ok(None) if start.elapsed() < Duration::from_secs(12) => {
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
            .filter(|w| w.get("label").and_then(Value::as_str) == Some(workspace))
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
        self.request(&["agent", "prompt", &target.pane_id, prompt])
            .map(|_| ())
    }
}
