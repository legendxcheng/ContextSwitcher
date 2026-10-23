import { useState, useEffect } from "react";
import type { Project, CsTask } from "./types";
import * as api from "./api";

interface ProjectFormDialogProps {
  existing?: Project | null;
  onClose: () => void;
  onSaved: () => void;
}

export function ProjectFormDialog({ existing, onClose, onSaved }: ProjectFormDialogProps) {
  const [name, setName] = useState(existing?.name ?? "");
  const [rootPath, setRootPath] = useState(existing?.root_path ?? "");
  const [herdrWs, setHerdrWs] = useState(existing?.herdr_workspace ?? "");
  const [csTaskId, setCsTaskId] = useState<string | null>(existing?.cs_task_id ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [csTasks, setCsTasks] = useState<CsTask[]>([]);
  const [csLoading, setCsLoading] = useState(false);

  useEffect(() => {
    setCsLoading(true);
    api.readCsTasks()
      .then((t) => setCsTasks(t))
      .catch(() => setCsTasks([]))
      .finally(() => setCsLoading(false));
  }, []);

  async function handleSave() {
    if (!name.trim() || !rootPath.trim() || !herdrWs.trim()) {
      setError("名称、本地目录、Herdr Workspace 均不能为空");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (existing) {
        await api.updateProject(existing.id, name.trim(), rootPath.trim(), herdrWs.trim(), csTaskId);
      } else {
        await api.createProject(name.trim(), rootPath.trim(), herdrWs.trim(), csTaskId);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const csStatusColor: Record<string, string> = {
    todo: "#6b6b82",
    in_progress: "#5a8fd4",
    completed: "#3db87a",
    paused: "#e0a33a",
    blocked: "#e05c5c",
    review: "#b87de8",
  };

  return (
    <div className="dialog-overlay" onMouseDown={onClose}>
      <div className="dialog" onMouseDown={(e) => e.stopPropagation()}>
        <h3>{existing ? "编辑项目" : "新建项目"}</h3>

        <div className="dialog-section">
          <label>项目名称</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Feature"
            autoFocus
            onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") onClose(); }}
          />
        </div>

        <div className="dialog-section">
          <label>本地目录（@ 文件引用根路径）</label>
          <div style={{ display: "flex", gap: "6px" }}>
            <input
              style={{ flex: 1 }}
              value={rootPath}
              onChange={(e) => setRootPath(e.target.value)}
              placeholder="E:\MyProject"
            />
            <button
              type="button"
              className="btn-secondary"
              style={{ whiteSpace: "nowrap", flexShrink: 0 }}
              onClick={async () => {
                const picked = await api.pickFolder();
                if (picked) setRootPath(picked);
              }}
            >
              浏览…
            </button>
          </div>
        </div>

        <div className="dialog-section">
          <label>Herdr Workspace 名称</label>
          <input
            value={herdrWs}
            onChange={(e) => setHerdrWs(e.target.value)}
            placeholder="my-workspace"
          />
        </div>

        <div className="dialog-section">
          <label>关联 ContextSwitcher 任务（可选）</label>
          {csLoading ? (
            <div className="loading-row"><span className="spinner" />读取中…</div>
          ) : csTasks.length === 0 ? (
            <p className="hint">未找到 ContextSwitcher 任务（ContextSwitcher 未安装或无数据）</p>
          ) : (
            <div className="cs-task-list">
              <div
                className={`cs-task-item${csTaskId === null ? " selected" : ""}`}
                onClick={() => setCsTaskId(null)}
              >
                <span className="cs-task-item-name" style={{ color: "var(--text-muted)" }}>不关联</span>
              </div>
              {csTasks.map((t) => (
                <div
                  key={t.id}
                  className={`cs-task-item${csTaskId === t.id ? " selected" : ""}`}
                  onClick={() => {
                    setCsTaskId(t.id);
                    // Auto-fill name and herdr workspace from the CS task if not already set
                    if (!name.trim()) setName(t.name);
                    if (!herdrWs.trim() && t.herdr_workspace) setHerdrWs(t.herdr_workspace);
                  }}
                >
                  <span
                    className="cs-task-status"
                    style={{
                      background: `${csStatusColor[t.status] ?? "#6b6b82"}22`,
                      color: csStatusColor[t.status] ?? "#6b6b82",
                    }}
                  >
                    {t.status}
                  </span>
                  <span className="cs-task-item-name">{t.name}</span>
                  {t.herdr_workspace && (
                    <span className="cs-task-item-ws">herdr:{t.herdr_workspace}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? <><span className="spinner" />保存中…</> : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
