import { useState } from "react";
import type { FileTreeNode } from "../lib/types";

function Node({ node, depth }: { node: FileTreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);

  if (node.type === "file") {
    return (
      <div className="filetree__row filetree__row--file" style={{ paddingLeft: depth * 14 }}>
        <span className="filetree__icon">·</span>
        {node.name}
      </div>
    );
  }

  const children = node.children ?? [];
  return (
    <div>
      <div
        className="filetree__row filetree__row--dir"
        style={{ paddingLeft: depth * 14 }}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="filetree__icon">{open ? "▾" : "▸"}</span>
        {node.name || "/"}
      </div>
      {open && children.map((c, i) => <Node node={c} depth={depth + 1} key={c.path ?? c.name + i} />)}
    </div>
  );
}

/** Backs the synopsis's "understands file structure" feature with an actual repo map. */
export default function FileTree({ root }: { root: FileTreeNode | null }) {
  const [open, setOpen] = useState(false);
  if (!root) return null;

  return (
    <details className="filetree" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="filetree__summary">File structure</summary>
      <div className="filetree__body">
        {(root.children ?? []).map((c, i) => (
          <Node node={c} depth={0} key={c.path ?? c.name + i} />
        ))}
      </div>
    </details>
  );
}
