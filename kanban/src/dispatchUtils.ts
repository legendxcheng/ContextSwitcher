import * as api from "./api";

/** Walk the Tiptap doc, replacing mention nodes with expanded content. */
export async function resolveMentions(doc: any, _rootPath: string): Promise<string> {
  const parts: string[] = [];
  async function walk(node: any) {
    if (node.type === "text") {
      parts.push(node.text);
    } else if (node.type === "mention") {
      const kind = node.attrs.kind;
      const ref = node.attrs.ref;
      const label = node.attrs.label;
      try {
        if (kind === "file") {
          const content = await api.readFileContent(ref);
          parts.push(`\n--- @文件: ${label} (${ref}) ---\n\`\`\`\n${content}\n\`\`\`\n`);
        } else {
          const content = await api.readSkillContent(ref);
          parts.push(`\n--- $技能: ${label} ---\n${content}\n---\n`);
        }
      } catch (e) {
        parts.push(`\n[引用失败: ${label} — ${String(e)}]\n`);
      }
    } else if (node.content) {
      for (const child of node.content) await walk(child);
    }
    if (node.type === "paragraph" || node.type === "heading") {
      parts.push("\n");
    }
  }
  await walk(doc);
  return parts.join("").trim();
}
