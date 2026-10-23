import { useState, useEffect } from "react";
import type { Task, Project, HerdrAgent } from "./types";
import * as api from "./api";
import { resolveMentions } from "./dispatchUtils";

interface DispatchDialogProps {
  task: Task;
  project: Project;
  onClose: () => void;
  onDispatched: () => void;
  preselectedPaneId?: string;
}

export function DispatchDialog({ task, project, onClose, onDispatched, preselectedPaneId }: DispatchDialogProps) {
  const [agents, setAgents] = useState<HerdrAgent[]>([]);
  const [selected, setSelected] = useState<string>(preselectedPaneId ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [preview, setPreview] = useState<string>("");

  // Load agents; once loaded, honour preselectedPaneId
  useEffect(() => {
    setLoading(true);
    api.herdrListAgents(project.herdr_workspace)
      .then((a) => {
        setAgents(a);
        if (preselectedPaneId && a.some((ag) => ag.pane_id === preselectedPaneId)) {
          setSelected(preselectedPaneId);
        }
        setLoading(false);
      })
      .catch((e) => { setError(String(e)); setLoading(false); });
  }, [project.herdr_workspace]);

  function buildPreview() {
    // Extract plain text from Tiptap JSON, expanding mention nodes with content
    try {
      const doc = JSON.parse(task.prompt_json);
      const text = extractTextWithMentions(doc);
      setPreview(text);
    } catch {
      setPreview("");
    }
  }

  async function handleDispatch() {
    if (!selected) { setError("请先选择 Agent"); return; }
    setError("");
    setLoading(true);
    try {
      // Build the resolved prompt: expand mentions into file/skill content
      const doc = JSON.parse(task.prompt_json);
      const resolved = await resolveMentions(doc, project.root_path);
      await api.dispatchToHerdr(task.id, selected, project.herdr_workspace, resolved);
      setLoading(false);
      onDispatched();
      onClose();
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  }

  return (
    <div className="dialog-overlay" onMouseDown={onClose}>
      <div className="dialog" onMouseDown={(e) => e.stopPropagation()}>
        <h3>派发任务: {task.name}</h3>
        <div className="dialog-section">
          <label>目标 Workspace: <strong>{project.herdr_workspace}</strong></label>
        </div>
        <div className="dialog-section">
          <label>选择 Agent</label>
          {loading && agents.length === 0 ? (
            <p>加载中…</p>
          ) : agents.length === 0 ? (
            <p className="hint">未找到 Agent。确认 Herdr 正在运行且 workspace 内有 agent。</p>
          ) : (
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">-- 选择 --</option>
              {agents.map((a) => (
                <option key={a.pane_id} value={a.pane_id}>
                  {a.title || a.name} ({a.status})
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="dialog-section">
          <button className="btn-secondary" onClick={buildPreview}>预览提示词</button>
          {preview && (
            <pre className="prompt-preview">{preview}</pre>
          )}
        </div>
        {error && <p className="error">{error}</p>}
        <div className="dialog-actions">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button onClick={handleDispatch} disabled={loading || !selected} className="btn-primary">
            {loading ? "派发中…" : "派发"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Extract text from a Tiptap doc, keeping mention placeholders for preview. */
function extractTextWithMentions(doc: any): string {
  if (!doc || !doc.content) return "";
  let text = "";
  function walk(node: any) {
    if (node.type === "text") {
      text += node.text;
    } else if (node.type === "mention") {
      text += `\n[${node.attrs.kind === "file" ? "@文件" : "$技能"}: ${node.attrs.label}]\n`;
    } else if (node.content) {
      node.content.forEach(walk);
    }
    if (node.type === "paragraph" || node.type === "heading") {
      text += "\n";
    }
  }
  walk(doc);
  return text.trim();
}

