import type { Task, Project } from "./types";
import * as api from "./api";
import { notify } from "./Toast";
import { Icon } from "./Icon";

interface TaskCardProps {
  task: Task;
  project: Project;
  onChanged: () => void;
  onEditTask: (id: string | null) => void;
  onDispatchTask: (id: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  todo: "未开发",
  in_progress: "开发中",
  done: "完成",
};

export function TaskCard({ task, project, onChanged, onEditTask, onDispatchTask }: TaskCardProps) {
  void project;

  async function handleMarkDone() {
    await api.updateTaskStatus(task.id, "done");
    notify("已标记完成", "success");
    onChanged();
  }

  async function handleDelete() {
    if (!confirm(`删除任务「${task.name}」？`)) return;
    await api.deleteTask(task.id);
    notify("任务已删除", "info");
    onChanged();
  }

  return (
    <div className={`task-card status-${task.status}`}>
      <div className="task-header">
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
      <div className="task-actions">
        <button onClick={() => onEditTask(task.id)} className="btn-ghost">编辑</button>
        {task.status === "todo" && (
          <button onClick={() => onDispatchTask(task.id)} className="btn-primary">派发<Icon name="arrow" size={13} /></button>
        )}
        {task.status === "in_progress" && (
          <>
            <button onClick={() => onDispatchTask(task.id)} className="btn-ghost">再派发</button>
            <button onClick={handleMarkDone} className="btn-success">标记完成</button>
          </>
        )}
        <button onClick={handleDelete} className="btn-danger">删除</button>
      </div>
    </div>
  );
}
