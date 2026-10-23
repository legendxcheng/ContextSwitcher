import { useState } from "react";
import type { Project } from "./types";
import * as api from "./api";
import { ProjectFormDialog } from "./ProjectFormDialog";
import { Icon } from "./Icon";

interface ProjectSidebarProps {
  projects: Project[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onChanged: () => void;
}

export function ProjectSidebar({ projects, selectedId, onSelect, onChanged }: ProjectSidebarProps) {
  const [showNew, setShowNew] = useState(false);
  const [editTarget, setEditTarget] = useState<Project | null>(null);

  async function handleDelete(id: string) {
    if (!confirm("删除项目及其所有任务？")) return;
    await api.deleteProject(id);
    onChanged();
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
                <span className="project-ws">{p.herdr_workspace}</span>
              </span>
            </button>
            <div className="project-actions">
              <button onClick={() => setEditTarget(p)} className="btn-icon" title="编辑项目" aria-label={`编辑项目 ${p.name}`}><Icon name="edit" size={14} /></button>
              <button onClick={() => handleDelete(p.id)} className="btn-icon" title="删除项目" aria-label={`删除项目 ${p.name}`}><Icon name="trash" size={14} /></button>
            </div>
          </div>
        ))}
      </div>
      <button className="sidebar-create btn-secondary" onClick={() => setShowNew(true)}><Icon name="plus" />新建项目</button>
      <div className="sidebar-footer"><Icon name="terminal" /><div><strong>你的本地工作空间</strong><span>组织任务 · 协作开发</span></div></div>

      {showNew && (
        <ProjectFormDialog
          onClose={() => setShowNew(false)}
          onSaved={() => { setShowNew(false); onChanged(); }}
        />
      )}
      {editTarget && (
        <ProjectFormDialog
          existing={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => { setEditTarget(null); onChanged(); }}
        />
      )}
    </aside>
  );
}
