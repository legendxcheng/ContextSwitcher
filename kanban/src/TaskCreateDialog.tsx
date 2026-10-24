import { useRef, useState } from "react";
import type { Task, TaskPriority } from "./types";
import { PrioritySelect } from "./PrioritySelect";
import { createTask } from "./api";
import { errorText, tr } from "./i18n";

export function TaskCreateDialog({ projectId, onClose, onCreated }: {
  projectId: string; onClose: () => void; onCreated: (task: Task) => void;
}) {
  const [name, setName] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("normal");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || submitting.current) return;
    submitting.current = true; setSaving(true); setError("");
    try { onCreated(await createTask(projectId, name.trim(), priority)); }
    catch (reason) { setError(errorText(reason)); }
    finally { submitting.current = false; setSaving(false); }
  }

  return <div className="dialog-overlay" onMouseDown={() => { if (!saving) onClose(); }}>
    <form className="dialog" role="dialog" aria-modal="true" aria-label={tr("task.create")}
      onMouseDown={(event) => event.stopPropagation()} onSubmit={submit}
      onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); if (!saving) onClose(); } }}>
      <h3>{tr("task.create")}</h3>
      <div className="dialog-section">
        <label className="field-label" htmlFor="new-task-name">{tr("task.new_name")}</label>
        <input id="new-task-name" className="field-input" autoFocus value={name} disabled={saving}
          onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="dialog-section">
        <label className="field-label" htmlFor="new-task-priority">{tr("priority.label")}</label>
        <PrioritySelect id="new-task-priority" label={tr("priority.new_task")} value={priority} onChange={setPriority} disabled={saving} />
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="dialog-actions">
        <button type="button" className="btn-secondary" disabled={saving} onClick={onClose}>{tr("common.cancel")}</button>
        <button type="submit" className="btn-primary" disabled={saving || !name.trim()} aria-label={tr("task.add")}>
          {saving && <span className="spinner" />}{tr("task.add")}
        </button>
      </div>
    </form>
  </div>;
}
