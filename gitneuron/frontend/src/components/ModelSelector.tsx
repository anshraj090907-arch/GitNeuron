import type { ModelOption } from "../lib/types";

interface Props {
  models: ModelOption[];
  value: string; // "" means Auto (use the backend's fallback chain)
  onChange: (id: string) => void;
}

/**
 * The user-facing half of "model-agnostic": the backend already accepts
 * any provider:model as an override (core/rag.py), so this is what lets
 * someone actually pick Claude vs. GPT vs. Gemini vs. DeepSeek vs.
 * Llama/Qwen instead of that only being reachable by hand-building a
 * request. Unconfigured models (no API key on the backend) are listed
 * but disabled, so the picker also doubles as a map of what's live.
 */
export default function ModelSelector({ models, value, onChange }: Props) {
  if (!models.length) return null;

  return (
    <div className="models">
      <select className="models__select" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Auto (fallback chain)</option>
        {models.map((m) => (
          <option key={m.id} value={m.id} disabled={!m.configured}>
            {m.label}
            {!m.configured ? " — no API key" : m.is_default_chain ? " — default" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
