import { useEditor, EditorContent, EditorContext } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { MentionNode } from "./MentionNode";
import { MentionPopover } from "./MentionPopover";

interface PromptEditorProps {
  content: string; // Tiptap JSON string
  rootPath: string;
  onChange: (json: string) => void;
}

export function PromptEditor({ content, rootPath, onChange }: PromptEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: "写提示词… 输入 @ 引用文件，输入 $ 引用技能" }),
      MentionNode,
    ],
    content: (() => {
      try { return JSON.parse(content); } catch { return null; }
    })(),
    onUpdate({ editor }) {
      onChange(JSON.stringify(editor.getJSON()));
    },
  });

  return (
    <EditorContext.Provider value={{ editor }}>
      <div className="prompt-editor-wrap">
        <EditorContent editor={editor} className="prompt-editor" />
        <MentionPopover rootPath={rootPath} />
      </div>
    </EditorContext.Provider>
  );
}
