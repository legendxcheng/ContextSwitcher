import { useState } from "react";
import type { Project, WorkspaceOperation } from "./types";
import * as api from "./api";
import { ProjectFormDialog } from "./ProjectFormDialog";
import { Icon } from "./Icon";
import { WorkspaceRecovery } from "./WorkspaceRecovery";
import { tr, errorText } from "./i18n";
import { notify } from "./Toast";

interface ProjectSidebarProps {
  projects: Project[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onChanged: () => void;
  operations?: WorkspaceOperation[];
  syncing?: boolean;
  syncError?: string;
}

export function ProjectSidebar({ projects, selectedId, onSelect, onChanged, operations = [], syncing = false, syncError = "" }: ProjectSidebarProps) {
  const [showNew, setShowNew] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);

  async function handleDelete(id: string) {
    if (!confirm(tr("workspace.remove_confirm"))) return;
    try { await api.deleteProject(id); onChanged(); } catch (e) { notify(errorText(e),"error"); }
  }

  return (
    <aside className="sidebar" aria-label="项目导航">
      <div className="sidebar-brand">
        <span className="brand-mark"><Icon name="board" size={22} /></span>
        <span>herdr<span className="brand-subtitle"> / kanban</span></span>
      </div>
      <div className="sidebar-intro">把想法变成下一步。</div>
      <div className="sidebar-header">
        <h2>项目 <span className="sidebar-count">{projects.length}</span></h2>
        <button onClick={() => setShowNew(true)} className="btn-icon" aria-label="新建项目" title="新建项目"><Icon name="plus" /></button>
      </div>
      <div className="project-list">
        {projects.map((p) => (
          <div
            key={p.id}
            className={"project-item" + (p.id === selectedId ? " selected" : "")}
          >
            <button className="project-row" onClick={() => onSelect(p.id)} aria-current={p.id === selectedId ? "page" : undefined} title={p.name}>
              <Icon name="folder" />
              <span className="project-info">
                <span className="project-name">{p.name}</span>
                <span className="project-ws" title={p.root_path}>{p.sync_status !== "ready" ? tr(`workspace.${p.sync_status}`) : p.root_path || tr("workspace.directory_missing")}</span>
              </span>
            </button>
            <div className="project-actions">
              <button onClick={() => setEditTarget(p)} className="btn-icon" title="编辑项目" aria-label={`编辑项目 ${p.name}`}><Icon name="edit" size={14} /></button>
              <button onClick={() => handleDelete(p.id)} className="btn-icon" title="删除项目" aria-label={`删除项目 ${p.name}`}><Icon name="trash" size={14} /></button>
            </div>
          </div>
        ))}
      </div>
      <div className="workspace-sync"><button className="btn-secondary" disabled={syncing} onClick={onChanged}>{tr(syncing ? "workspace.syncing" : "workspace.refresh")}</button>
        {syncError && <p className="error" role="alert">{syncError}</p>}
      </div>
      {operations.length > 0 && <div className="workspace-pending"><strong>{tr("workspace.pending_title")}</strong>{operations.map((op) => <WorkspaceRecovery key={op.id} operation={op} onChanged={onChanged} />)}</div>}
      <button className="sidebar-create btn-secondary" onClick={() => setShowNew(true)}><Icon name="plus" />新建项目</button>
      <div className="sidebar-footer"><Icon name="terminal" /><div><strong>你的本地工作空间</strong><span>组织任务 · 协作开发</span></div></div>

      {showNew && (
        <ProjectFormDialog
          key="new-workspace"
          onClose={() => setShowNew(false)}
          onSaved={() => { setShowNew(false); onChanged(); }}
        />
      )}
      {editTarget && (
        <ProjectFormDialog
          existing={editTarget}
          key={editTarget.id}
          onClose={() => setEditTarget(null)}
          onSaved={() => { setEditTarget(null); onChanged(); }}
        />
      )}
    </aside>
  );
}
