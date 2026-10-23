import { useState, useEffect, useRef } from "react";
import type { Task, Project, TaskStatus, HerdrAgent } from "./types";
import { TaskCard } from "./TaskCard";
import { DispatchDialog } from "./DispatchDialog";
import { TaskEditPanel } from "./TaskEditPanel";
import * as api from "./api";
import { notify } from "./Toast";
import { Icon, type IconName } from "./Icon";
import { DispatchRecovery } from "./DispatchRecovery";
import { TerminalPanel } from "./TerminalPanel";
import { BindingDialog } from "./BindingDialog";
import { tr, errorText } from "./i18n";

interface KanbanBoardProps {
  project: Project;
  onNewTaskShortcut?: () => void;
}

const COLUMNS: { status: TaskStatus; label: string; emptyIcon: IconName; emptyText: string; hint: string }[] = [
  { status: "todo", label: "未开发", emptyIcon: "circle", emptyText: "暂无待办任务", hint: "在下方添加你的下一个想法" },
  { status: "in_progress", label: "开发中", emptyIcon: "progress", emptyText: "没有进行中的任务", hint: "派发给 Agent，让任务开始推进" },
  { status: "done", label: "完成", emptyIcon: "check", emptyText: "还没有完成的任务", hint: "完成的每一步，都会留在这里" },
];

export function KanbanBoard({ project }: KanbanBoardProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTaskName, setNewTaskName] = useState("");
  const [adding, setAdding] = useState(false);
  const [dragOverCol, setDragOverCol] = useState<TaskStatus | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const draggingIdRef = useRef<string | null>(null);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [agents, setAgents] = useState<HerdrAgent[]>([]);
  const [dragOverAgent, setDragOverAgent] = useState<string | null>(null);
  const [pendingDispatch, setPendingDispatch] = useState<{ task: Task; paneId: string } | null>(null);
  const [recoveringTaskId, setRecoveringTaskId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [repairingTaskId, setRepairingTaskId] = useState<string | null>(null);
  const selectedTask = tasks.find((task) => task.id === selectedTaskId && task.status === "in_progress") ?? null;
  const suppressClick = useRef(false);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const resizing = useRef(false);
  const [terminalWidth, setTerminalWidth] = useState(300);
  const [maximumWidth, setMaximumWidth] = useState(800);
  const loadSequence = useRef(0);
  useEffect(() => {
    if (!workspaceRef.current) return;
    const observer = new ResizeObserver(() => {
      const width = workspaceRef.current?.clientWidth ?? 0;
      if (width) {
        const max = Math.max(280, width - 220);
        setMaximumWidth(max); setTerminalWidth((current) => Math.min(current, max));
      }
    });
    observer.observe(workspaceRef.current);
    return () => observer.disconnect();
  }, [loading]);
  useEffect(() => {
    if (selectedTaskId && !tasks.some((task) => task.id === selectedTaskId && task.status === "in_progress")) setSelectedTaskId(null);
  }, [tasks, selectedTaskId]);
  const setWidth = (width: number) => setTerminalWidth(Math.max(280, Math.min(maximumWidth, width)));

  // Pre-fetch agents for drag-to-dispatch chips
  useEffect(() => {
    if (!project.herdr_workspace) return;
    let active = true;
    api.herdrListAgents(project.herdr_workspace)
      .then((items) => { if (active) setAgents(items); })
      .catch(() => { if (active) setAgents([]); });
    return () => { active = false; };
  }, [project.herdr_workspace]);

  async function handleAgentDrop(e: React.DragEvent, agent: HerdrAgent) {
    e.preventDefault();
    setDragOverAgent(null);
    // Use ref as primary source — dataTransfer.getData can return empty on WebView2
    const taskId = draggingIdRef.current ?? e.dataTransfer.getData("taskId");
    if (!taskId) return;
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    setPendingDispatch({ task, paneId: agent.pane_id });
  }

  async function load() {
    const sequence = ++loadSequence.current;
    setLoading(true);
    try {
      const t = await api.listTasks(project.id);
      if (sequence === loadSequence.current) setTasks(t);
    } catch (e) {
      if (sequence === loadSequence.current) notify(errorText(e), "error");
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }

  useEffect(() => { load(); return () => { ++loadSequence.current; }; }, [project.id]);

  // Keyboard shortcut: N to focus the new-task input
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.key === "n" &&
        !e.ctrlKey && !e.metaKey && !e.altKey &&
        !(document.activeElement instanceof HTMLElement && document.activeElement.closest(".terminal-panel")) &&
        !(document.activeElement instanceof HTMLElement && document.activeElement.isContentEditable) &&
        !(document.activeElement instanceof HTMLInputElement) &&
        !(document.activeElement instanceof HTMLTextAreaElement)
      ) {
        document.getElementById("new-task-input")?.focus();
        e.preventDefault();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  async function handleAddTask() {
    const name = newTaskName.trim();
    if (!name) return;
    setAdding(true);
    try {
      const newTask = await api.createTask(project.id, name);
      setNewTaskName("");
      await load();
      setEditingTaskId(newTask.id);
    } catch (e) {
      notify(String(e), "error");
    } finally {
      setAdding(false);
    }
  }

  async function handleDrop(e: React.DragEvent, targetStatus: TaskStatus) {
    e.preventDefault();
    const taskId = draggingIdRef.current ?? e.dataTransfer.getData("taskId");
    setDragOverCol(null);
    setDraggingId(null);
    draggingIdRef.current = null;
    if (!taskId) return;
    const task = tasks.find((t) => t.id === taskId);
    if (!task || task.status === targetStatus) return;
    if (targetStatus === "in_progress") {
      // Enter development only after dispatch succeeds; cancel/failure keeps the
      // original status. The dispatch command persists the status and metadata.
      setPendingDispatch({ task, paneId: "" });
      return;
    }
    try { await api.updateTaskStatus(taskId, targetStatus); await load(); }
    catch (e) { notify(errorText(e), "error"); }
  }

  if (loading && tasks.length === 0) {
    return (
      <div className="board-loading">
        <span className="spinner" />
        <span>加载中…</span>
      </div>
    );
  }

  return (
    <div className="kanban-board" onDragOver={(e) => e.preventDefault()}>
      <div className="board-toolbar">
        <div className="board-view"><Icon name="board" /><h2>任务看板</h2><span className="toolbar-count">{tasks.length}</span></div>
        <div className="board-toolbar-actions">
          <span className="board-summary">{tasks.filter((task) => task.status === "done").length} / {tasks.length} 已完成</span>
          <button className="btn-primary" onClick={() => document.getElementById("new-task-input")?.focus()}><Icon name="plus" />新建任务<kbd>N</kbd></button>
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
      <div className="board-workspace" ref={workspaceRef} style={{ "--terminal-width": `${terminalWidth}px` } as React.CSSProperties}>
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
                <span className="col-empty-hint">{hint}</span>
              </div>
            ) : (
              <div className="col-cards">
                {col.map((task) => (
                  <div
                    key={task.id}
                    draggable
                    onDragStart={(e) => {
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
                      project={project}
                      onChanged={load}
                      onRecover={() => setRecoveringTaskId(task.id)}
                      onRepair={() => setRepairingTaskId(task.id)}
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
            {status === "todo" && (
              <div className="col-add">
                <input
                  id="new-task-input"
                  value={newTaskName}
                  onChange={(e) => setNewTaskName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleAddTask();
                    if (e.key === "Escape") { setNewTaskName(""); (e.target as HTMLInputElement).blur(); }
                  }}
                  placeholder="添加一个新任务…"
                  aria-label="新任务名称"
                  className="new-task-input"
                />
                <button
                  onClick={handleAddTask}
                  disabled={adding || !newTaskName.trim()}
                  className="btn-primary"
                  aria-label="添加任务"
                >
                  {adding ? <span className="spinner" /> : <Icon name="plus" />}
                </button>
              </div>
            )}
          </div>
        );
      })}
      </div>
      <div role="separator" tabIndex={0} aria-label={tr("terminal.adjust_width")} aria-orientation="vertical"
        aria-valuemin={280} aria-valuemax={maximumWidth} aria-valuenow={terminalWidth} className="terminal-splitter"
        onKeyDown={(e) => { if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); setWidth(terminalWidth + (e.key === "ArrowLeft" ? 24 : -24)); } }}
        onPointerDown={(e) => { resizing.current = true; e.currentTarget.setPointerCapture(e.pointerId); e.preventDefault(); }}
        onPointerMove={(e) => { if (resizing.current && workspaceRef.current) setWidth(workspaceRef.current.getBoundingClientRect().right - e.clientX); }}
        onPointerUp={() => { resizing.current = false; }} onLostPointerCapture={() => { resizing.current = false; }} />
      <TerminalPanel task={selectedTask} onRepair={selectedTask ? () => {
        if (selectedTask.binding?.operation) setRecoveringTaskId(selectedTask.id);
        else setRepairingTaskId(selectedTask.id);
      } : undefined} />
      </div>
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
          <TaskEditPanel
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
