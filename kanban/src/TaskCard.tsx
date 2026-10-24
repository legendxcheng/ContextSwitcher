import { useRef, useState } from "react";
import type { Task } from "./types";
import * as api from "./api";
import { notify } from "./Toast";
import { Icon } from "./Icon";
import { errorText, tr } from "./i18n";

interface TaskCardProps {
  task: Task;
  onChanged: () => void;
  onArchived: () => void;
  onEditTask: (id: string | null) => void;
  onDispatchTask: (id: string) => void;
  onRecover?: () => void;
  onSelect?: () => void;
  selected?: boolean;
  busy?: boolean;
  onComplete: () => void;
  onFlowRecover?: () => void;
}

export function TaskCard({ task, onChanged, onArchived, onEditTask, onDispatchTask, onRecover, onSelect, selected, busy, onComplete, onFlowRecover }: TaskCardProps) {
  const archivingRef = useRef(false);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState("");
  const archiveReason = task.binding?.operation ? "dispatch.verify_required"
    : ["pending", "unknown"].includes(task.flow?.state ?? "") ? "flow.verify_required"
    : task.cleanup_required ? "archive.cleanup_required" : "";
  const disabled = !!busy || archiving;
  const controls = {
    onClick: (event: React.MouseEvent) => event.stopPropagation(),
    onKeyDown: (event: React.KeyboardEvent) => event.stopPropagation(),
  };

  async function handleArchive() {
    if (archivingRef.current || busy || archiveReason) return;
    archivingRef.current = true;
    setArchiving(true); setArchiveError("");
    try {
      await api.archiveTask(task.id);
      notify(tr("archive.success"), "success");
      onArchived();
    } catch (error) {
      setArchiveError(errorText(error));
    } finally {
      archivingRef.current = false; setArchiving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`删除任务「${task.name}」？`)) return;
    try { await api.deleteTask(task.id); }
    catch (e) { notify(errorText(e), "error"); return; }
    notify("任务已删除", "info");
    onChanged();
  }

  return (
    <div className={`task-card status-${task.status}${selected ? " selected" : ""}`} onClick={onSelect}>
      <div className="task-heading">
        <div className="task-header" role={onSelect ? "button" : undefined} tabIndex={onSelect ? 0 : undefined}
          aria-label={onSelect ? `${tr("terminal.view")}${task.name}` : undefined} aria-pressed={onSelect ? !!selected : undefined}
          onKeyDown={(event) => { if (onSelect && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onSelect(); } }}>
          <span className="task-name" title={task.name}>{task.name}</span>
        </div>
        <fieldset disabled={disabled} className="task-tools" {...controls}>
          {task.status === "done" && <button className="btn-icon" onClick={handleArchive} disabled={!!archiveReason}
            aria-label={tr("archive.action")} title={tr(archiveReason || "archive.action")}>
            {archiving ? <span className="spinner" /> : <Icon name="archive" />}
          </button>}
          <button onClick={() => onEditTask(task.id)} className="btn-icon" aria-label={tr("task.edit")} title={tr("task.edit")}><Icon name="edit" /></button>
        </fieldset>
      </div>
      <div className="task-footer">
        <span className={`task-priority priority-${task.priority}`} title={task.dispatched_to ? `${tr("task.target")}${task.dispatched_to}` : tr("priority.label")}>
          {tr(`priority.${task.priority}`)}
        </span>
        <fieldset disabled={disabled} className="task-actions" {...controls}>
          {task.status === "todo" && !task.binding?.operation && <button onClick={() => onDispatchTask(task.id)} className="btn-primary">派发<Icon name="arrow" size={13} /></button>}
          {task.status === "in_progress" && <button onClick={onComplete} className="btn-success">标记完成</button>}
          <button onClick={handleDelete} className="btn-icon btn-danger" aria-label={tr("task.delete")} title={tr("task.delete")}><Icon name="trash" /></button>
        </fieldset>
      </div>
      {busy && <p role="status" className="task-notice">{tr("flow.busy")}</p>}
      {task.flow?.error && <p className="error task-notice">{errorText(task.flow.error)}</p>}
      {task.status === "done" && archiveReason && <p className="task-notice">{tr(archiveReason)}</p>}
      {archiveError && <p role="alert" className="error task-notice">{archiveError}</p>}
      {(task.flow?.state === "unknown" || task.cleanup_required || task.binding?.operation) &&
        <fieldset disabled={disabled} className="task-recovery" {...controls}>
          {task.flow?.state === "unknown" && <button className="btn-secondary" onClick={onFlowRecover}>{tr("flow.recover")}</button>}
          {task.cleanup_required && <button className="btn-secondary" onClick={onComplete}>{tr("flow.retry_cleanup")}</button>}
          {task.binding?.state === "unknown" && <button className="btn-secondary" onClick={onRecover}>{tr("dispatch.verify")}</button>}
          {task.binding?.state === "pending" && <button className="btn-ghost" onClick={onChanged}>{tr("dispatch.pending")}</button>}
        </fieldset>}
    </div>
  );
}
