import { useCurrentEditor } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";
import * as api from "./api";
import type { FileEntry, SkillEntry } from "./types";

interface Suggestion {
  kind: "file" | "skill";
  label: string;
  ref: string;
  description?: string;
}

/**
 * Mention popover controller. Renders a floating suggestion list when the
 * editor has an active @ or $ trigger, and inserts a mention node on select.
 */
export function MentionPopover({ rootPath }: { rootPath: string }) {
  const { editor } = useCurrentEditor();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [index, setIndex] = useState(0);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"file" | "skill">("file");
  const boxRef = useRef<HTMLDivElement>(null);

  // Watch editor selection for trigger chars
  useEffect(() => {
    if (!editor) return;
    const handler = () => {
      const sel = editor.state.selection;
      const $pos = sel.$from;
      const textBefore = $pos.parent.textContent.slice(0, $pos.parentOffset);
      // find last @ or $ not followed by space
      const m = textBefore.match(/([@$])([\w./_-]*)$/);
      if (m) {
        const ch = m[1];
        const q = m[2];
        setKind(ch === "@" ? "file" : "skill");
        setQuery(q);
        setOpen(true);
      } else {
        setOpen(false);
      }
    };
    editor.on("selectionUpdate", handler);
    editor.on("update", handler);
    return () => {
      editor.off("selectionUpdate", handler);
      editor.off("update", handler);
    };
  }, [editor]);

  // Fetch suggestions when query/kind changes
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        let suggestions: Suggestion[] = [];
        if (kind === "file") {
          if (!rootPath) return;
          const files = await api.searchFiles(rootPath, query);
          suggestions = files.map((f: FileEntry) => ({
            kind: "file" as const,
            label: f.rel_path,
            ref: f.abs_path,
          }));
        } else {
          const skills = await api.searchSkills(query);
          suggestions = skills.map((s: SkillEntry) => ({
            kind: "skill" as const,
            label: s.name,
            ref: s.skill_md_path,
            description: s.description,
          }));
        }
        if (!cancelled) {
          setItems(suggestions);
          setIndex(0);
        }
      } catch (e) {
        if (!cancelled) setItems([]);
      }
    })();
    return () => { cancelled = true; };
  }, [open, query, kind, rootPath]);

  // Keyboard handling inside editor
  useEffect(() => {
    if (!editor || !open) return;
    const handler = (e: KeyboardEvent) => {
      if (!open || items.length === 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setIndex((i) => (i + 1) % items.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setIndex((i) => (i - 1 + items.length) % items.length);
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        insertMention(items[index]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    };
    editor.view.dom.addEventListener("keydown", handler);
    return () => editor.view.dom.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, open, items, index]);

  function insertMention(s: Suggestion) {
    if (!editor) return;
    const { state, dispatch } = editor.view;
    const sel = state.selection;
    const $pos = sel.$from;
    const textBefore = $pos.parent.textContent.slice(0, $pos.parentOffset);
    const m = textBefore.match(/([@$])([\w./_-]*)$/);
    if (!m) return;
    const start = sel.from - (m[0].length);
    // Replace the trigger+query with a mention node
    const mentionNode = state.schema.nodes.mention.create({
      kind: s.kind,
      label: s.label,
      ref: s.ref,
    });
    const tr = state.tr.deleteRange(start, sel.to).insert(start, mentionNode).insert(start + mentionNode.nodeSize, state.schema.text(" "));
    dispatch(tr.scrollIntoView());
    setOpen(false);
    editor.view.focus();
  }

  if (!open || items.length === 0) return null;

  return (
    <div ref={boxRef} className="mention-popover">
      {items.map((s, i) => (
        <div
          key={s.ref}
          className={"mention-item" + (i === index ? " active" : "")}
          onMouseDown={(e) => { e.preventDefault(); insertMention(s); }}
          onMouseEnter={() => setIndex(i)}
        >
          <span className="mention-kind">{s.kind === "file" ? "@" : "$"}</span>
          <span className="mention-label">{s.label}</span>
          {s.description && <span className="mention-desc">{s.description}</span>}
        </div>
      ))}
    </div>
  );
}
