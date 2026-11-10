import type { SourceChunk } from "../lib/types";

export default function SourcesPanel({ sources }: { sources: SourceChunk[] }) {
  if (!sources.length) return null;
  return (
    <details className="sources">
      <summary className="sources__summary">
        Sources <span className="sources__count">{sources.length}</span>
      </summary>
      <ul className="sources__list">
        {sources.map((s, i) => (
          <li key={i} className="sources__item">
            <div className="sources__path">
              {s.file_path}
              <span className="sources__lines">
                :{s.start_line}-{s.end_line}
              </span>
              <span className="sources__score">{(s.score * 100).toFixed(0)}%</span>
            </div>
            <pre className="sources__snippet">{s.snippet}</pre>
          </li>
        ))}
      </ul>
    </details>
  );
}
