import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import * as api from "./api";
import type { Task } from "./types";
import { tr, errorText } from "./i18n";

export function TerminalPanel({ task, onRepair }: { task: Task | null; onRepair?: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState("terminal.empty");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const identity = JSON.stringify(task?.binding?.target);
  const bindingState = task?.binding?.state;
  useEffect(() => {
    setError("");
    if (!task || !host.current) { setState("terminal.empty"); return; }
    if (bindingState !== "valid") { setState("binding.repair_required"); return; }
    const connectionId = crypto.randomUUID();
    let active = true;
    let connected = false;
    let ended = false;
    let pendingInput = "";
    let writing = false;
    let inputTimer: ReturnType<typeof setTimeout> | undefined;
    const terminal = new Terminal({ cursorBlink: true, scrollback: 3000, fontSize: 13,
      fontFamily: "Cascadia Mono, Consolas, monospace", convertEol: false,
      theme: { background: "#111111", foreground: "#e5e5e5", cursor: "#3ecf8e" } });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(host.current);
    fit.fit();
    terminal.options.disableStdin = true;
    setState("terminal.connecting");
    function fail(e: unknown) {
      if (!active) return;
      ended = true; connected = false; pendingInput = "";
      terminal.options.disableStdin = true;
      setState("terminal.disconnected"); setError(errorText(e));
      void api.closeTerminal(connectionId).catch(() => {});
    }
    async function flushInput() {
      if (!active || !connected || writing || !pendingInput) return;
      const data = pendingInput; pendingInput = ""; writing = true;
      try { await api.inputTerminal(connectionId, data); }
      catch (e) { fail(e); }
      finally { writing = false; if (active && connected && pendingInput) void flushInput(); }
    }
    const dataListener = terminal.onData((data) => {
      if (!active || !connected) return;
      if (new TextEncoder().encode(pendingInput + data).length > 65536) { fail("terminal.input_limit"); return; }
      pendingInput += data;
      clearTimeout(inputTimer); inputTimer = setTimeout(() => void flushInput(), 10);
    });
    const resizeListener = terminal.onResize(({ cols, rows }) => {
      if (active && connected) void api.resizeTerminal(connectionId, cols, rows).catch(fail);
    });
    const observer = new ResizeObserver(() => { if (active) fit.fit(); });
    observer.observe(host.current);
    void api.openTerminal(task.id, connectionId, terminal.cols, terminal.rows, (packet) => {
      if (!active || ended) return;
      if (packet.kind === "closed") { fail(packet.message); return; }
      // Output can arrive before the invoke result. It belongs to this connection.
      connected = true;
      terminal.write(new Uint8Array(packet.data), () => {
        if (active && !ended) void api.ackTerminal(connectionId, packet.data.length).catch(fail);
      });
    }).then(() => {
      if (!active || ended) { void api.closeTerminal(connectionId).catch(() => {}); return; }
      connected = true; terminal.options.disableStdin = false; setState("terminal.connected");
      fit.fit();
      // fit may already have run during connect, without an active resize channel.
      void api.resizeTerminal(connectionId, terminal.cols, terminal.rows).catch(fail);
    }).catch(fail);
    return () => {
      active = false; connected = false; clearTimeout(inputTimer); pendingInput = "";
      observer.disconnect(); dataListener.dispose(); resizeListener.dispose(); terminal.dispose();
      void api.closeTerminal(connectionId).catch(() => {});
    };
  // Reconnect only when the selected identity/state changes, not on list refreshes.
  }, [task?.id, identity, bindingState, attempt]);

  return <aside className="terminal-panel" aria-label={tr("terminal.label")}>
    <header className="terminal-header"><strong>{task?.name ?? tr("terminal.label")}</strong><span role="status">{tr(state)}</span></header>
    {!task && <p className="terminal-hint">{tr("terminal.empty")}</p>}
    {task && state !== "terminal.connected" && <div className="terminal-feedback">
      {error && <p role="alert">{error}</p>}
      {state !== "terminal.connecting" && <div className="task-actions">
        {bindingState === "valid" && <button className="btn-secondary" onClick={() => setAttempt((n) => n + 1)}>{tr("terminal.reconnect")}</button>}
        {onRepair && <button className="btn-ghost" onClick={onRepair}>{tr("binding.repair")}</button>}
      </div>}
    </div>}
    <div ref={host} className="terminal-host" onKeyDown={(e) => e.stopPropagation()} />
  </aside>;
}
