import { useCallback, useEffect, useRef, useState } from "react";
import RepoBar from "./components/RepoBar";
import ChatPanel from "./components/ChatPanel";
import FileTree from "./components/FileTree";
import { getFileTree, getIndexStatus, getModels, getTemplates, indexRepository, sendChatStream } from "./lib/api";
import type { ChatMessage, FileTreeNode, IndexStatus, ModelOption, Template } from "./lib/types";

export default function App() {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [fileTree, setFileTree] = useState<FileTreeNode | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState("default");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelId, setModelId] = useState(""); // "" = Auto (backend fallback chain)
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  useEffect(() => {
    getTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
    getModels()
      .then(setModels)
      .catch(() => setModels([]));
  }, []);

  useEffect(() => {
    if (status?.status === "ready") {
      getFileTree(status.repo_id)
        .then(setFileTree)
        .catch(() => setFileTree(null));
    } else {
      setFileTree(null);
    }
  }, [status?.status, status?.repo_id]);

  async function handleIndex(url: string, branch: string) {
    stopPolling();
    setMessages([]);
    setFileTree(null);
    setIndexing(true);
    try {
      const initial = await indexRepository(url, branch || undefined);
      setStatus(initial);
      pollRef.current = window.setInterval(async () => {
        try {
          const latest = await getIndexStatus(initial.repo_id);
          setStatus(latest);
          if (latest.status === "ready" || latest.status === "error") {
            stopPolling();
            setIndexing(false);
          }
        } catch (pollErr: any) {
          stopPolling();
          setIndexing(false);
          setStatus((prev) => ({
            repo_id: initial.repo_id,
            status: "error",
            message: pollErr.message || "Connection to backend lost or backend crashed.",
            files_indexed: prev?.files_indexed ?? 0,
            chunks_indexed: prev?.chunks_indexed ?? 0,
            repo_name: prev?.repo_name ?? "",
            default_branch: prev?.default_branch ?? "",
          }));
        }
      }, 1000);
    } catch (err: any) {
      setStatus({
        repo_id: "",
        status: "error",
        message: err.message || "Failed to start indexing.",
        files_indexed: 0,
        chunks_indexed: 0,
        repo_name: "",
        default_branch: "",
      });
      setIndexing(false);
    }
  }

  async function handleSend(text: string) {
    if (!status || status.status !== "ready") return;

    const userMessage: ChatMessage = { role: "user", content: text };
    const history = [...messages, userMessage].map((m) => ({ role: m.role, content: m.content }));

    // Placeholder assistant turn that fills in live as reasoning steps stream in.
    const placeholder: ChatMessage = { role: "assistant", content: "", reasoning: [], streaming: true };
    setMessages((prev) => [...prev, userMessage, placeholder]);
    setAsking(true);

    try {
      await sendChatStream(
        status.repo_id,
        text,
        history.slice(0, -1),
        templateId,
        modelId || undefined,
        (step) => {
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, reasoning: [...(last.reasoning ?? []), step] };
            return copy;
          });
        },
        (final) => {
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = {
              ...last,
              content: final.answer,
              sources: final.sources,
              modelUsed: final.model_used,
              streaming: false,
            };
            return copy;
          });
        }
      );
    } catch (err: any) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: `_${err.message || "Something went wrong."}_`,
          streaming: false,
        };
        return copy;
      });
    } finally {
      setAsking(false);
    }
  }

  const ready = status?.status === "ready";

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__brand-mark">GN</span>
          <div>
            <div className="app__brand-name">GitNeuron</div>
            <div className="app__brand-tag">Chat with any GitHub repository</div>
          </div>
        </div>
      </header>

      <RepoBar onSubmit={handleIndex} status={status} busy={indexing} />

      {ready && <FileTree root={fileTree} />}

      <main className="app__main">
        <ChatPanel
          messages={messages}
          onSend={handleSend}
          disabled={!ready || asking}
          placeholder={
            ready
              ? "Ask about this repository…"
              : status
              ? "Waiting for indexing to finish…"
              : "Index a repository above to start chatting"
          }
          templates={templates}
          templateId={templateId}
          onTemplateChange={setTemplateId}
          models={models}
          modelId={modelId}
          onModelChange={setModelId}
        />
      </main>
    </div>
  );
}
