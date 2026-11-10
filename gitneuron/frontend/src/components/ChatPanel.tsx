import { FormEvent, useEffect, useRef, useState } from "react";
import type { ChatMessage, ModelOption, Template } from "../lib/types";
import MessageBubble from "./MessageBubble";
import TemplateSelector from "./TemplateSelector";
import ModelSelector from "./ModelSelector";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  disabled: boolean;
  placeholder: string;
  templates: Template[];
  templateId: string;
  onTemplateChange: (id: string) => void;
  models: ModelOption[];
  modelId: string;
  onModelChange: (id: string) => void;
}

// Minimal, dependency-free voice input: browsers expose SpeechRecognition
// under a vendor-prefixed name, so this feature degrades silently (the
// mic button just doesn't render) wherever it isn't supported.
function getSpeechRecognition(): (new () => any) | null {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export default function ChatPanel({
  messages, onSend, disabled, placeholder, templates, templateId, onTemplateChange,
  models, modelId, onModelChange,
}: Props) {
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  const SpeechRecognitionCtor = getSpeechRecognition();

  function toggleVoice() {
    if (!SpeechRecognitionCtor) return;
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      setDraft((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim() || disabled) return;
    onSend(draft.trim());
    setDraft("");
  }

  return (
    <div className="chat-panel">
      <div className="chat-panel__scroll">
        {messages.length === 0 && (
          <div className="chat-panel__empty">
            Ask anything about this repository — file structure, how a function works,
            where something is implemented, or why a design decision was made.
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        <div ref={endRef} />
      </div>

      <div className="chat-panel__controls">
        <TemplateSelector templates={templates} value={templateId} onChange={onTemplateChange} />
        <ModelSelector models={models} value={modelId} onChange={onModelChange} />
      </div>

      <form className="chat-panel__composer" onSubmit={handleSubmit}>
        {SpeechRecognitionCtor && (
          <button
            type="button"
            className={`chat-panel__mic ${listening ? "chat-panel__mic--active" : ""}`}
            onClick={toggleVoice}
            title={listening ? "Stop listening" : "Ask by voice"}
          >
            ●
          </button>
        )}
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder={listening ? "Listening…" : placeholder}
          disabled={disabled}
          rows={1}
        />
        <button type="submit" disabled={disabled || !draft.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}
