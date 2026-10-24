import { useState, useEffect } from "react";
import type { Project } from "./types";
import { ProjectSidebar } from "./ProjectSidebar";
import { KanbanBoard } from "./KanbanBoard";
import { ToastContainer } from "./Toast";
import { Icon } from "./Icon";
import { TerminalPanel } from "./TerminalPanel";
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
          <KanbanBoard key={selectedProject.id} project={selectedProject} />
        ) : (
          <div className="board-workspace">
            <div className="board-main empty-state">
              <span className="empty-state-icon"><Icon name="board" size={32} /></span>
              <span className="eyebrow">YOUR NEXT IDEA STARTS HERE</span>
              <h1 className="empty-state-title">从一个项目，开始推进。</h1>
              <p className="empty-state-desc">在左侧新建项目，整理任务与提示词，<br />将下一步交给你的 Agent。</p>
            </div>
            <TerminalPanel task={null} />
          </div>
        )}
      </main>
    </div>
  );
}
