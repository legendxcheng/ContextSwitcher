import { useState, useEffect } from "react";
import { ProjectSidebar } from "./ProjectSidebar";
import { KanbanBoard } from "./KanbanBoard";
import { ToastContainer } from "./Toast";
import { Icon } from "./Icon";
import { TerminalPanel } from "./TerminalPanel";
import { useProjectSync } from "./useProjectSync";
import "./App.css";

export default function App() {
  const { projects, operations, syncing, error, refresh } = useProjectSync();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => { setSelectedId((id) => projects.some((p) => p.id === id) ? id : projects[0]?.id ?? null); }, [projects]);

  const selectedProject = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="app">
      <ToastContainer />
      <ProjectSidebar
        projects={projects}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onChanged={refresh}
        operations={operations}
        syncing={syncing}
        syncError={error}
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
