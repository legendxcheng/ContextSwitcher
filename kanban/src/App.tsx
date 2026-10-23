import { useState, useEffect } from "react";
import type { Project } from "./types";
import { ProjectSidebar } from "./ProjectSidebar";
import { KanbanBoard } from "./KanbanBoard";
import { ToastContainer } from "./Toast";
import { Icon } from "./Icon";
import * as api from "./api";
import "./App.css";

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function loadProjects() {
    const ps = await api.listProjects();
    setProjects(ps);
    // auto-select first project if none selected
    if (ps.length > 0 && (selectedId === null || !ps.find((p) => p.id === selectedId))) {
      setSelectedId(ps[0].id);
    }
  }

  useEffect(() => { loadProjects(); }, []);

  const selectedProject = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="app">
      <ToastContainer />
      <ProjectSidebar
        projects={projects}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onChanged={loadProjects}
      />
      <main className="board-area">
        {selectedProject ? (
          <>
            <div className="workspace-bar">
              <h1 className="workspace-project" title={selectedProject.name}>{selectedProject.name}</h1>
              <span className="breadcrumb-sep">/</span>
              <span className="workspace-current" title={selectedProject.herdr_workspace}>{selectedProject.herdr_workspace}</span>
              <span className="board-meta">
                <Icon name="folder" />
                <span className="project-path" title={selectedProject.root_path}>{selectedProject.root_path}</span>
              </span>
            </div>
            <KanbanBoard project={selectedProject} />
          </>
        ) : (
          <div className="empty-state">
            <span className="empty-state-icon"><Icon name="board" size={32} /></span>
            <span className="eyebrow">YOUR NEXT IDEA STARTS HERE</span>
            <h1 className="empty-state-title">从一个项目，开始推进。</h1>
            <p className="empty-state-desc">在左侧新建项目，整理任务与提示词，<br />将下一步交给你的 Agent。</p>
          </div>
        )}
      </main>
    </div>
  );
}
