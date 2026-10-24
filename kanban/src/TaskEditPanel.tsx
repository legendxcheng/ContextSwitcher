import { useState, useEffect, useCallback } from "react";
import type { Task, Project } from "./types";
import { PromptEditor } from "./PromptEditor";
import * as api from "./api";
import { notify } from "./Toast";
import { PrioritySelect } from "./PrioritySelect";
import { tr } from "./i18n";

interface TaskEditPanelProps {
  task: Task;
  project: Project;
  onClose: () => void;
  onSaved: () => void;
}

export function TaskEditPanel({ task, project, onClose, onSaved }: TaskEditPanelProps) {
  const [name, setName] = useState(task.name);
  const [promptJson, setPromptJson] = useState(task.prompt_json);
  const [priority, setPriority] = useState(task.priority);
  const [saving, setSaving] = useState(false);

  // Sync if the task prop changes (e.g., board refresh while panel is open)
  useEffect(() => {
    setName(task.name);
    setPromptJson(task.prompt_json);
    setPriority(task.priority);
  }, [task.id]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.updateTask(task.id, name.trim(), promptJson, priority);
      notify("保存成功");
      onSaved();
      onClose();
    } catch (e) {
      notify(String(e), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="slideover-backdrop" onClick={onClose} />
      <div className="slideover" role="dialog" aria-label="编辑任务">
        <div className="slideover-header">
          <h3>编辑任务</h3>
          <button className="btn-icon" onClick={onClose} aria-label="关闭" title="Esc 关闭">✕</button>
        </div>
        <div className="slideover-body">
          <div>
            <label className="field-label" htmlFor="edit-task-name">任务名称</label>
            <input
              id="edit-task-name"
              className="field-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
              placeholder="任务名称"
              autoFocus
            />
          </div>
          <div>
            <label className="field-label">提示词</label>
            <PromptEditor
              content={promptJson}
              rootPath={project.root_path}
              onChange={setPromptJson}
            />
          </div>
          <div>
            <label className="field-label" htmlFor="edit-task-priority">{tr("priority.label")}</label>
            <PrioritySelect id="edit-task-priority" label={tr("priority.label")} value={priority} onChange={setPriority} disabled={saving} />
          </div>
        </div>
        <div className="slideover-footer">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button onClick={handleSave} disabled={saving || !name.trim()} className="btn-primary">
            {saving ? <><span className="spinner" />保存中…</> : "保存"}
          </button>
        </div>
      </div>
    </>
  );
}
