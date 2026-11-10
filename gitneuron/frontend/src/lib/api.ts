import type { IndexStatus, SourceChunk, ReasoningStep, FileTreeNode, Template, ModelOption } from "./types";

const BASE = "/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export function indexRepository(repoUrl: string, branch?: string): Promise<IndexStatus> {
  return fetch(`${BASE}/repos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl, branch: branch || null }),
  }).then((r) => asJson<IndexStatus>(r));
}

export function getIndexStatus(repoId: string): Promise<IndexStatus> {
  return fetch(`${BASE}/repos/${repoId}/status`).then((r) => asJson<IndexStatus>(r));
}

export interface ChatApiResponse {
  answer: string;
  sources: SourceChunk[];
  reasoning: ReasoningStep[];
  model_used: string;
}

export function sendChat(
  repoId: string,
  message: string,
  history: { role: string; content: string }[],
  templateId?: string,
  modelOverride?: string
): Promise<ChatApiResponse> {
  return fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_id: repoId, message, history,
      template_id: templateId || null, model_override: modelOverride || null,
    }),
  }).then((r) => asJson<ChatApiResponse>(r));
}

export function getModels(): Promise<ModelOption[]> {
  return fetch(`${BASE}/models`).then((r) => asJson<ModelOption[]>(r));
}

/**
 * Streams the live agent reasoning canvas: calls `onStep` for every
 * reasoning step as it happens and `onFinal` once with the completed
 * answer. Uses a raw `fetch` + ReadableStream reader (not `EventSource`,
 * which can't send a POST body) to parse the backend's SSE response.
 */
export async function sendChatStream(
  repoId: string,
  message: string,
  history: { role: string; content: string }[],
  templateId: string | undefined,
  modelOverride: string | undefined,
  onStep: (step: ReasoningStep) => void,
  onFinal: (res: ChatApiResponse) => void
): Promise<void> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_id: repoId, message, history,
      template_id: templateId || null, model_override: modelOverride || null,
    }),
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Chat request failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      const eventLine = rawEvent.split("\n").find((l) => l.startsWith("event:"));
      const dataLine = rawEvent.split("\n").find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const eventType = eventLine.slice("event:".length).trim();
      const data = JSON.parse(dataLine.slice("data:".length).trim());

      if (eventType === "step") onStep(data as ReasoningStep);
      else if (eventType === "final") onFinal(data as ChatApiResponse);
    }
  }
}

export function getFileTree(repoId: string): Promise<FileTreeNode> {
  return fetch(`${BASE}/repos/${repoId}/files`).then((r) => asJson<FileTreeNode>(r));
}

export function getTemplates(): Promise<Template[]> {
  return fetch(`${BASE}/templates`).then((r) => asJson<Template[]>(r));
}

export function exportGist(title: string, content: string): Promise<{ url: string }> {
  return fetch(`${BASE}/export/gist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  }).then((r) => asJson<{ url: string }>(r));
}

export async function exportPdf(title: string, content: string, sources: SourceChunk[]): Promise<void> {
  const res = await fetch(`${BASE}/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content, sources }),
  });
  if (!res.ok) throw new Error("PDF export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/\s+/g, "_").slice(0, 40) || "gitneuron-export"}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportSandbox(title: string, files: Record<string, string>): Promise<any> {
  return fetch(`${BASE}/export/sandbox`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, files }),
  }).then((r) => asJson(r));
}
