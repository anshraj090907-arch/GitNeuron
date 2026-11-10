import { useState } from "react";
import { exportGist, exportPdf, exportSandbox } from "../lib/api";
import type { SourceChunk } from "../lib/types";

interface Props {
  title: string;
  content: string;
  sources: SourceChunk[];
}

export default function ExportMenu({ title, content, sources }: Props) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function run(action: () => Promise<string | void>) {
    setStatus("Working…");
    try {
      const result = await action();
      setStatus(typeof result === "string" ? result : "Done");
    } catch (err: any) {
      setStatus(err.message || "Export failed");
    }
    setTimeout(() => setStatus(null), 4000);
  }

  return (
    <div className="export-menu">
      <button className="export-menu__trigger" onClick={() => setOpen((v) => !v)}>
        Export ⌄
      </button>
      {open && (
        <div className="export-menu__panel">
          <button
            onClick={() =>
              run(async () => {
                const res = await exportGist(title, content);
                window.open(res.url, "_blank");
                return "Gist created";
              })
            }
          >
            Export to GitHub Gist
          </button>
          <button onClick={() => run(() => exportPdf(title, content, sources))}>
            Export as PDF
          </button>
          <button
            onClick={() =>
              run(async () => {
                const payload = await exportSandbox(title, { "answer.md": content });
                const form = document.createElement("form");
                form.method = "POST";
                form.action = "https://codesandbox.io/api/v1/sandboxes/define?json=1";
                form.target = "_blank";
                const input = document.createElement("input");
                input.type = "hidden";
                input.name = "parameters";
                input.value = btoa(JSON.stringify(payload));
                form.appendChild(input);
                document.body.appendChild(form);
                form.submit();
                document.body.removeChild(form);
                return "Opening CodeSandbox";
              })
            }
          >
            Open in CodeSandbox
          </button>
        </div>
      )}
      {status && <span className="export-menu__status">{status}</span>}
    </div>
  );
}
