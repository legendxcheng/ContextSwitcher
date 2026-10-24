import { useEditor, EditorContent, EditorContext } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { MentionNode } from "./MentionNode";
import { MentionPopover } from "./MentionPopover";
import { useEffect } from "react";
import { tr } from "./i18n";

interface PromptEditorProps {
  content: string; // Tiptap JSON string
  rootPath: string;
  onChange: (json: string) => void;
  labelledBy?: string;
  disabled?: boolean;
}

export function PromptEditor({ content, rootPath, onChange, labelledBy, disabled = false }: PromptEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: tr("task.prompt_placeholder") }),
      MentionNode,
    ],
    content: (() => {
      try { const value = JSON.parse(content); return value?.type === "doc" ? value : null; } catch { return null; }
    })(),
    editable: !disabled,
    editorProps: { attributes: { role: "textbox", "aria-multiline": "true", ...(labelledBy ? { "aria-labelledby": labelledBy } : { "aria-label": tr("task.prompt") }) } },
    onUpdate({ editor }) {
      onChange(JSON.stringify(editor.getJSON()));
    },
  });

  useEffect(() => { editor?.setEditable(!disabled); }, [editor, disabled]);

  return (
    <EditorContext.Provider value={{ editor }}>
      <div className="prompt-editor-wrap">
        <EditorContent editor={editor} className="prompt-editor" />
        {!disabled && <MentionPopover rootPath={rootPath} />}
      </div>
    </EditorContext.Provider>
  );
}
