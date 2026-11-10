import { useEffect, useRef, useState } from "react";

let mermaidPromise: Promise<typeof import("mermaid")> | null = null;
function loadMermaid() {
  if (!mermaidPromise) mermaidPromise = import("mermaid");
  return mermaidPromise;
}

/**
 * Renders a ```mermaid fenced block as an actual diagram instead of a
 * text dump — the "generative UI" touch from the deck: when a template
 * (e.g. Architecture Explainer) decides a diagram communicates better
 * than prose, the UI renders what the model generated, live.
 */
export default function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    let cancelled = false;
    loadMermaid()
      .then(async (mod) => {
        const mermaid = mod.default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
        const { svg } = await mermaid.render(id.current, code);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch(() => {
        if (!cancelled) setError("Diagram could not be rendered.");
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return <pre className="mermaid-fallback">{code}</pre>;
  }
  return <div className="mermaid-block" ref={ref} />;
}
