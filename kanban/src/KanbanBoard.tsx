import { useState, useEffect, useRef } from "react";
import type { Task, Project, TaskStatus, HerdrAgent } from "./types";
import { TaskCard } from "./TaskCard";
import { DispatchDialog } from "./DispatchDialog";
import { TaskFormDialog } from "./TaskFormDialog";
import * as api from "./api";
import { notify } from "./Toast";
import { Icon, type IconName } from "./Icon";
import { DispatchRecovery } from "./DispatchRecovery";
import { TerminalPanel } from "./TerminalPanel";
import { BindingDialog } from "./BindingDialog";
import { tr, errorText } from "./i18n";
import { resolveMentions } from "./dispatchUtils";

interface KanbanBoardProps {
  project: Project;
  onNewTaskShortcut?: () => void;
}

const COLUMNS: { status: TaskStatus; label: string; emptyIcon: IconName; emptyText: string; hint: string }[] = [
  { status: "todo", label: "未开发", emptyIcon: "circle", emptyText: "暂无待办任务", hint: "task.empty_hint" },
  { status: "in_progress", label: "开发中", emptyIcon: "progress", emptyText: "没有进行中的任务", hint: "派发给 Agent，让任务开始推进" },
  { status: "done", label: "完成", emptyIcon: "check", emptyText: "还没有完成的任务", hint: "完成的每一步，都会留在这里" },
];

export function KanbanBoard({ project }: KanbanBoardProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [creatingTask, setCreatingTask] = useState(false);
  const [dragOverCol, setDragOverCol] = useState<TaskStatus | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const draggingIdRef = useRef<string | null>(null);
  const dragFromControl = useRef(false);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [agents, setAgents] = useState<HerdrAgent[]>([]);
  const [dragOverAgent, setDragOverAgent] = useState<string | null>(null);
  const [pendingDispatch, setPendingDispatch] = useState<{ task: Task; paneId: string } | null>(null);
  const [recoveringTaskId, setRecoveringTaskId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [repairingTaskId, setRepairingTaskId] = useState<string | null>(null);
  const activeFlows = useRef(new Set<string>());
  const [busyTasks, setBusyTasks] = useState(new Set<string>());
  const [flowError, setFlowError] = useState("");
  const selectedTask = tasks.find((task) => task.id === selectedTaskId && task.status === "in_progress") ?? null;
  const suppressClick = useRef(false);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const resizing = useRef(false);
  const widthAdjusted = useRef(false);
  const [terminalWidth, setTerminalWidth] = useState<number | null>(null);
  const [maximumWidth, setMaximumWidth] = useState(800);
  const loadSequence = useRef(0);
  const agentSequence = useRef(0);
  useEffect(() => {
    if (!workspaceRef.current) return;
    const observer = new ResizeObserver(() => {
      const width = workspaceRef.current?.clientWidth ?? 0;
      if (width) {
        const max = Math.max(280, width - 328);
        const appWidth = workspaceRef.current?.closest(".app")?.clientWidth ?? window.innerWidth;
        const defaultWidth = Math.max(280, Math.min(max, appWidth / 3));
        setMaximumWidth(max);
        setTerminalWidth((current) => widthAdjusted.current && current !== null ? Math.min(current, max) : defaultWidth);
      }
    });
    observer.observe(workspaceRef.current);
    return () => observer.disconnect();
  }, []);
  const setWidth = (width: number) => {
    widthAdjusted.current = true;
    setTerminalWidth(Math.max(280, Math.min(maximumWidth, width)));
  };

  // Pre-fetch agents for drag-to-dispatch chips
  useEffect(() => {
    if (!project.herdr_workspace) return;
    refreshAgents();
    return () => { ++agentSequence.current; };
  }, [project.herdr_workspace]);

  async function refreshAgents() {
    const sequence = ++agentSequence.current;
    try {
      const items = await api.herdrListAgents(project.herdr_workspace);
      if (sequence === agentSequence.current) setAgents(items);
    } catch { if (sequence === agentSequence.current) setAgents([]); }
  }

  async function handleAgentDrop(e: React.DragEvent, agent: HerdrAgent) {
    e.preventDefault();
    setDragOverAgent(null);
    // Use ref as primary source — dataTransfer.getData can return empty on WebView2
    const taskId = draggingIdRef.current ?? e.dataTransfer.getData("taskId");
    if (!taskId) return;
    const task = tasks.find((t) => t.id === taskId);
    if (!task || activeFlows.current.has(taskId)) return;
    setPendingDispatch({ task, paneId: agent.pane_id });
  }

  async function load() {
    const sequence = ++loadSequence.current;
    setLoading(true);
    try {
      const t = await api.listTasks(project.id);
      if (sequence === loadSequence.current) {
        setTasks(t);
        setSelectedTaskId((current) => t.some((task) => task.id === current && task.status === "in_progress")
          ? current : t.find((task) => task.status === "in_progress")?.id ?? null);
      }
    } catch (e) {
      if (sequence === loadSequence.current) notify(errorText(e), "error");
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }

  useEffect(() => { load(); return () => { ++loadSequence.current; }; }, [project.id]);

  function handleArchived(id: string) {
    // Archive already committed: a failed list refresh must not resurrect this card.
    ++loadSequence.current;
    setTasks((current) => current.filter((task) => task.id !== id));
    setEditingTaskId((current) => current === id ? null : current);
    setSelectedTaskId((current) => current === id ? null : current);
    setRepairingTaskId((current) => current === id ? null : current);
    setRecoveringTaskId((current) => current === id ? null : current);
    setPendingDispatch((current) => current?.task.id === id ? null : current);
    load(); refreshAgents();
  }

  // Keyboard shortcut: N opens the same form as the toolbar action.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.key === "n" &&
        !e.ctrlKey && !e.metaKey && !e.altKey &&
        !document.querySelector(".dialog-overlay") &&
        !(document.activeElement instanceof HTMLElement && document.activeElement.closest(".terminal-panel")) &&
        !(document.activeElement instanceof HTMLElement && document.activeElement.isContentEditable) &&
        !(document.activeElement instanceof HTMLInputElement) &&
        !(document.activeElement instanceof HTMLSelectElement) &&
        !(document.activeElement instanceof HTMLTextAreaElement)
      ) {
        setCreatingTask(true);
        e.preventDefault();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  async function handleDrop(e: React.DragEvent, targetStatus: TaskStatus) {
    e.preventDefault();
    const taskId = draggingIdRef.current ?? e.dataTransfer.getData("taskId");
    setDragOverCol(null);
    setDraggingId(null);
    draggingIdRef.current = null;
    if (!taskId) return;
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === targetStatus) return;
    await moveTask(task, targetStatus);
  }

  async function moveTask(task: Task, status: TaskStatus) {
    if (activeFlows.current.has(task.id)) return;
    activeFlows.current.add(task.id);
    setBusyTasks(new Set(activeFlows.current));
    setFlowError("");
    try {
      const result = status === "in_progress"
        ? await api.startTask(task.id, task.flow?.session_id || task.binding?.target ? "" : await resolveMentions(JSON.parse(task.prompt_json), project.root_path), crypto.randomUUID())
        : await api.updateTaskStatus(task.id, status);
      if (result?.warning) setFlowError(`${tr("flow.cleanup_warning")} ${errorText(result.warning)}`);
      await load();
      if (status === "in_progress") setSelectedTaskId(task.id);
    } catch (e) {
      setFlowError(errorText(e));
      await load();
    } finally {
      activeFlows.current.delete(task.id);
      setBusyTasks(new Set(activeFlows.current));
    }
  }

  async function recoverFlow(task: Task) {
    if (!task.flow?.operation_id || activeFlows.current.has(task.id)) return;
    if (task.flow.kind === "complete") { await moveTask(task, "done"); return; }
    activeFlows.current.add(task.id); setBusyTasks(new Set(activeFlows.current));
    try { await api.recoverLifecycle(task.id, task.flow.operation_id); setFlowError(""); }
    catch (e) { setFlowError(errorText(e)); }
    finally { activeFlows.current.delete(task.id); setBusyTasks(new Set(activeFlows.current)); await load(); }
  }

  return (
    <div className="kanban-board board-workspace" ref={workspaceRef} style={terminalWidth === null ? undefined : { "--terminal-width": `${terminalWidth}px` } as React.CSSProperties} onDragOver={(e) => e.preventDefault()}>
      <div className="board-main">
        {loading && tasks.length === 0 ? <div className="board-loading"><span className="spinner" /><span>加载中…</span></div> : <>
        <div className="workspace-bar">
          <h1 className="workspace-project" title={project.name}>{project.name}</h1>
          <span className="breadcrumb-sep">/</span>
          <span className="workspace-current" title={project.herdr_workspace}>{project.herdr_workspace}</span>
          <span className="board-meta">
            <Icon name="folder" />
            <span className="project-path" title={project.root_path}>{project.root_path}</span>
          </span>
        </div>
        <div className="board-content">
          {flowError && <p role="alert" className="error">{flowError}</p>}
          <div className="board-toolbar">
            <div className="board-view"><Icon name="board" /><h2>任务看板</h2><span className="toolbar-count">{tasks.length}</span></div>
            <div className="board-toolbar-actions">
              <span className="board-summary">{tasks.filter((task) => task.status === "done").length} / {tasks.length} 已完成</span>
              <button className="btn-primary" onClick={() => setCreatingTask(true)}><Icon name="plus" />新建任务<kbd>N</kbd></button>
            </div>
          </div>
          {agents.length > 0 && (
            <div
              className={`agent-dispatch-bar${draggingId ? " is-dragging" : ""}`}
              onDragOver={(e) => e.preventDefault()}
            >
              <span className="agent-bar-label"><Icon name="terminal" />Agent</span>
              {agents.map((agent) => (
                <div
                  key={agent.pane_id}
                  className={`agent-chip${dragOverAgent === agent.pane_id ? " drag-over" : ""}${pendingDispatch ? " disabled" : ""}`}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverAgent(agent.pane_id); }}
                  onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverAgent(null); }}
                  onDrop={(e) => { e.preventDefault(); e.stopPropagation(); handleAgentDrop(e, agent); }}
                >
                  <span className="agent-chip-status" data-status={agent.status} style={{ pointerEvents: "none" }} />
                  <span className="agent-chip-title" style={{ pointerEvents: "none" }}>{agent.title || agent.name}</span>
                </div>
              ))}
              <span className="agent-bar-hint">拖拽任务到 Agent 即可选择派发</span>
            </div>
          )}
          <div className="kanban-columns">
          {COLUMNS.map(({ status, label, emptyIcon, emptyText, hint }) => {
            const col = tasks.filter((t) => t.status === status);
            return (
              <div
                key={status}
                className={`kanban-col col-${status}${dragOverCol === status ? " drag-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragOverCol(status); }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                    setDragOverCol(null);
                  }
                }}
                onDrop={(e) => handleDrop(e, status)}
              >
                <div className="col-header">
                  <span className="col-title"><Icon name={emptyIcon} />{label}</span>
                  <span className="col-count">{col.length}</span>
                </div>
                {col.length === 0 ? (
                  <div className="col-empty">
                    <span className="col-empty-icon"><Icon name={emptyIcon} size={22} /></span>
                    <span className="col-empty-text">{emptyText}</span>
                    <span className="col-empty-hint">{status === "todo" ? tr(hint) : hint}</span>
                  </div>
                ) : (
                  <div className="col-cards">
                    {col.map((task) => (
                      <div
                        key={task.id}
                        draggable={!busyTasks.has(task.id)}
                        onPointerDownCapture={(event) => {
                          dragFromControl.current = event.target instanceof Element && !!event.target.closest("button, input, select, textarea");
                        }}
                        onDragStart={(e) => {
                          if (dragFromControl.current) { e.preventDefault(); e.stopPropagation(); return; }
                          e.dataTransfer.setData("taskId", task.id);
                          e.dataTransfer.effectAllowed = "move";
                          draggingIdRef.current = task.id;
                          setDraggingId(task.id);
                        }}
                        onDragEnd={() => { draggingIdRef.current = null; setDraggingId(null); suppressClick.current = true; setTimeout(() => { suppressClick.current = false; }, 0); }}
                        onDragOver={(e) => e.preventDefault()}
                        className={`card-wrapper${draggingId === task.id ? " dragging" : ""}`}
                      >
                        <TaskCard
                          task={task}
                          busy={busyTasks.has(task.id)}
                          onComplete={() => moveTask(task, "done")}
                          onFlowRecover={() => recoverFlow(task)}
                          onChanged={load}
                          onArchived={() => handleArchived(task.id)}
                          onRecover={() => setRecoveringTaskId(task.id)}
                          selected={selectedTaskId === task.id}
                          onSelect={task.status === "in_progress" ? () => { if (!suppressClick.current) setSelectedTaskId(task.id); } : undefined}
                          onEditTask={setEditingTaskId}
                          onDispatchTask={(id) => {
                            const t = tasks.find((x) => x.id === id);
                            if (t) setPendingDispatch({ task: t, paneId: "" });
                          }}
                        />
                      </div>
                    ))}
                  </div>
                )}

              </div>
            );
          })}
          </div>
        </div>
        </>}
      </div>
      <div role="separator" tabIndex={0} aria-label={tr("terminal.adjust_width")} aria-orientation="vertical"
        aria-valuemin={280} aria-valuemax={maximumWidth} aria-valuenow={terminalWidth ?? window.innerWidth / 3} className="terminal-splitter"
        onKeyDown={(e) => { if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); setWidth((terminalWidth ?? window.innerWidth / 3) + (e.key === "ArrowLeft" ? 24 : -24)); } }}
        onPointerDown={(e) => { resizing.current = true; e.currentTarget.setPointerCapture(e.pointerId); e.preventDefault(); }}
        onPointerMove={(e) => { if (resizing.current && workspaceRef.current) setWidth(workspaceRef.current.getBoundingClientRect().right - e.clientX); }}
        onPointerUp={() => { resizing.current = false; }} onLostPointerCapture={() => { resizing.current = false; }} />
      <TerminalPanel task={selectedTask} onRepair={selectedTask ? () => {
        if (selectedTask.binding?.operation) setRecoveringTaskId(selectedTask.id);
        else setRepairingTaskId(selectedTask.id);
      } : undefined} />
      {creatingTask && <TaskFormDialog project={project} onClose={() => setCreatingTask(false)} onSaved={load} />}
      {pendingDispatch && (
        <DispatchDialog
          key={pendingDispatch.task.id}
          task={tasks.find((task) => task.id === pendingDispatch.task.id) ?? pendingDispatch.task}
          project={project}
          preselectedPaneId={pendingDispatch.paneId || undefined}
          onClose={() => setPendingDispatch(null)}
          onDispatched={() => { setPendingDispatch(null); load(); }}
          onRefresh={load}
        />
      )}
      {recoveringTaskId && (() => {
        const task = tasks.find((task) => task.id === recoveringTaskId);
        return task ? <DispatchRecovery key={task.id} task={task} onClose={() => setRecoveringTaskId(null)} onSaved={() => { setRecoveringTaskId(null); load(); }} /> : null;
      })()}
      {repairingTaskId && (() => {
        const task = tasks.find((task) => task.id === repairingTaskId);
        return task ? <BindingDialog key={task.id} task={task} project={project} onClose={() => setRepairingTaskId(null)} onSaved={() => { setRepairingTaskId(null); load(); }} /> : null;
      })()}
      {editingTaskId && (() => {
        const t = tasks.find((x) => x.id === editingTaskId);
        return t ? (
          <TaskFormDialog
            key={t.id}
            task={t}
            project={project}
            onClose={() => setEditingTaskId(null)}
            onSaved={() => { setEditingTaskId(null); load(); }}
          />
        ) : null;
      })()}
    </div>
  );
}
