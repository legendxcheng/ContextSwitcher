import { useCallback, useEffect, useRef, useState } from "react";
import type { Project, WorkspaceOperation } from "./types";
import * as api from "./api";
import { errorText, tr } from "./i18n";

export function useProjectSync() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [operations, setOperations] = useState<WorkspaceOperation[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  const running = useRef<Promise<void> | null>(null);
  const repeat = useRef(false);
  const refresh = useCallback(() => {
    if (running.current) { repeat.current = true; return running.current; }
    const run = async () => {
      do {
        repeat.current = false;
        if (mounted.current) setSyncing(true);
        // Read local state first: a slow or unavailable Herdr never hides local tasks.
        try { const cached = await api.listProjects(); if (mounted.current) setProjects(cached); }
        catch (e) { if (mounted.current) setError(errorText(e)); }
        try {
          const result = await api.syncProjects();
          if (mounted.current && !repeat.current) { setProjects(result.projects); setOperations(result.operations); setError(""); }
        } catch (e) {
          if (mounted.current) setError(`${tr("workspace.offline")} ${errorText(e)}`);
          try { const pending = await api.workspaceOperations(); if (mounted.current) setOperations(pending); } catch { /* Keep last durable operation view. */ }
        }
      } while (repeat.current && mounted.current);
      if (mounted.current) setSyncing(false);
    };
    running.current = run().finally(() => { running.current = null; });
    return running.current;
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const focus = () => { void refresh(); };
    const timer = window.setInterval(() => { if (document.visibilityState === "visible" && !running.current) void refresh(); }, 15000);
    window.addEventListener("focus", focus);
    return () => { mounted.current = false; window.clearInterval(timer); window.removeEventListener("focus", focus); };
  }, [refresh]);
  return { projects, operations, syncing, error, refresh };
}
