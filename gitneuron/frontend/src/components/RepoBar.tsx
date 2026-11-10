import { FormEvent, useState } from "react";
import type { IndexStatus } from "../lib/types";

interface Props {
  onSubmit: (url: string, branch: string) => void;
  status: IndexStatus | null;
  busy: boolean;
}

const STAGE_LABEL: Record<string, string> = {
  pending: "Queued",
  validating: "Checking repository is valid and accessible",
  cloning: "Cloning repository",
  chunking: "Parsing & chunking",
  embedding: "Embedding chunks",
  ready: "Ready",
  error: "Error",
};

export default function RepoBar({ onSubmit, status, busy }: Props) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim(), branch.trim());
  }

  return (
    <div className="repo-bar">
      <form onSubmit={handleSubmit} className="repo-form">
        <span className="repo-form__mark">git://</span>
        <input
          className="repo-form__input"
          placeholder="https://github.com/owner/repository"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          spellCheck={false}
        />
        <input
          className="repo-form__branch"
          placeholder="branch (optional)"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          spellCheck={false}
        />
        <button type="submit" className="repo-form__submit" disabled={busy}>
          {busy ? "Indexing…" : "Index repository"}
        </button>
      </form>

      {status && (
        <div className={`repo-status repo-status--${status.status}`}>
          <span className="repo-status__dot" />
          <span className="repo-status__label">{STAGE_LABEL[status.status] ?? status.status}</span>
          {status.repo_name && <span className="repo-status__repo">{status.repo_name}</span>}
          {status.status !== "ready" && status.status !== "error" && status.message && (
            <span className="repo-status__message">{status.message}</span>
          )}
          {status.status === "ready" && (
            <span className="repo-status__message">
              {status.files_indexed} files · {status.chunks_indexed} chunks
            </span>
          )}
          {status.status === "error" && <span className="repo-status__message">{status.message}</span>}
        </div>
      )}
    </div>
  );
}
