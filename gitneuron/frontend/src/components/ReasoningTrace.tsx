import { useEffect, useState } from "react";
import type { ReasoningStep } from "../lib/types";

const KIND_MARK: Record<string, string> = {
  plan: "◇",
  retrieval: "⌕",
  generation: "✎",
  tool: "⚙",
  fallback: "↻",
  error: "×",
};

/**
 * The "live agent reasoning canvas": a horizontal node graph that grows
 * as steps arrive during streaming (kept open while `live` is true) and
 * collapses into a compact strip once the answer is done.
 */
export default function ReasoningTrace({ steps, live }: { steps: ReasoningStep[]; live: boolean }) {
  const [open, setOpen] = useState(live);

  useEffect(() => {
    if (live) setOpen(true);
  }, [live]);

  if (!steps.length) return null;

  return (
    <div className="canvas">
      <button className="canvas__toggle" onClick={() => setOpen((v) => !v)}>
        {live ? "Reasoning live" : "Reasoning trace"}
        <span className="canvas__count">{steps.length}</span>
      </button>

      {open && (
        <div className="canvas__graph">
          {steps.map((s, i) => (
            <div className="canvas__node-wrap" key={s.id}>
              {i > 0 && <span className="canvas__edge" />}
              <div
                className={`canvas__node canvas__node--${s.kind} canvas__node--${s.status}`}
                title={s.detail}
              >
                <span className="canvas__mark">{KIND_MARK[s.kind] ?? "·"}</span>
                <span className="canvas__label">{s.label}</span>
                {s.status === "running" && <span className="canvas__spinner" />}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
