import type { Task, Project } from "./types";
import * as api from "./api";
import { notify } from "./Toast";
import { Icon } from "./Icon";
import { errorText, tr } from "./i18n";

interface TaskCardProps {
  task: Task;
  project: Project;
  onChanged: () => void;
  onEditTask: (id: string | null) => void;
  onDispatchTask: (id: string) => void;
  onRecover?: () => void;
  onSelect?: () => void;
  selected?: boolean;
  onRepair?: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  todo: "未开发",
  in_progress: "开发中",
  done: "完成",
};

export function TaskCard({ task, project, onChanged, onEditTask, onDispatchTask, onRecover, onSelect, selected, onRepair }: TaskCardProps) {
  void project;

  async function handleMarkDone() {
    try { await api.updateTaskStatus(task.id, "done"); }
    catch (e) { notify(errorText(e), "error"); return; }
    notify("已标记完成", "success");
    onChanged();
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
      <div className="task-header" role={onSelect ? "button" : undefined} tabIndex={onSelect ? 0 : undefined}
        aria-label={onSelect ? `${tr("terminal.view")}${task.name}` : undefined} aria-pressed={onSelect ? !!selected : undefined}
        onKeyDown={(e) => { if (onSelect && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onSelect(); } }}>
        <span className="task-name">{task.name}</span>
        <span className={`task-status-badge badge-${task.status}`}>
          {STATUS_LABEL[task.status]}
        </span>
      </div>
      {task.dispatched_to && (
        <div className="task-meta">
          派发至 <code>{task.dispatched_to}</code>
          {task.dispatched_at && (
            <span> · {new Date(task.dispatched_at).toLocaleString()}</span>
          )}
        </div>
      )}
      <div className="task-actions" onClick={(e) => e.stopPropagation()}>
        {task.binding && !task.binding.operation && task.binding.state !== "unbound" && <button className="btn-ghost" onClick={onRepair}>{tr("binding.repair")}</button>}
        {task.binding?.state === "unknown" && <button className="btn-secondary" onClick={onRecover}>{tr("dispatch.verify")}</button>}
        {task.binding?.state === "pending" && <button className="btn-ghost" onClick={onChanged}>{tr("dispatch.pending")}</button>}
        <button onClick={() => onEditTask(task.id)} className="btn-ghost">编辑</button>
        {task.status === "todo" && !task.binding?.operation && (
          <button onClick={() => onDispatchTask(task.id)} className="btn-primary">派发<Icon name="arrow" size={13} /></button>
        )}
        {task.status === "in_progress" && (
          <>
            <button disabled={!!task.binding?.operation} onClick={() => onDispatchTask(task.id)} className="btn-ghost">再派发</button>
            <button onClick={handleMarkDone} className="btn-success">标记完成</button>
          </>
        )}
        <button onClick={handleDelete} className="btn-danger">删除</button>
      </div>
    </div>
  );
}
