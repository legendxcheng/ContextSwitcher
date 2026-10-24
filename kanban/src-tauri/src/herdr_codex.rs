//! Codex startup, exact session recovery and guarded prompt submission.
use super::{Cli, codex_process, field};
use crate::workflow::{Herdr, SendError, Target};
use serde_json::Value;
use std::{
    thread,
    time::{Duration, Instant},
};

impl Cli {
    pub(super) fn prepare_codex_session(
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
    pub(super) fn read_codex_session(&self, target: &Target) -> Result<Option<String>, String> {
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
    pub(super) fn send_prompt_checked(
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
    pub(super) fn inspect_pane(
        &self,
        workspace: &str,
        pane: &str,
    ) -> Result<(Target, Value), String> {
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
    pub(super) fn ready(&self, target: &Target, info: &Value) -> bool {
        if target.agent.is_empty() {
            return target.status == "idle";
        }
        target.agent == "codex"
            && matches!(target.status.as_str(), "idle" | "done")
            && info.get("interactive_ready").and_then(Value::as_bool) == Some(true)
            && info.get("launch_pending").and_then(Value::as_bool) != Some(true)
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
