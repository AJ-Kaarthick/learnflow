/**
 * Markmap's Transformer parses standard markdown. A heading for the
 * root plus a nested bullet list for everything below it is the
 * simplest input that reliably produces a correct tree — no need for
 * Markmap-specific syntax.
 */
export function treeToMarkdown(node) {
  const lines = [`# ${node.title}`];

  function addChildren(children, depth) {
    for (const child of children || []) {
      lines.push(`${"  ".repeat(depth)}- ${child.title}`);
      addChildren(child.children, depth + 1);
    }
  }

  addChildren(node.children, 0);
  return lines.join("\n");
}
