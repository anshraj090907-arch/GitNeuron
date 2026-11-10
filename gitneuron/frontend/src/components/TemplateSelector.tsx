import type { Template } from "../lib/types";

interface Props {
  templates: Template[];
  value: string;
  onChange: (id: string) => void;
}

/** The "template library" from the deck: each option swaps the agent's system prompt/behavior. */
export default function TemplateSelector({ templates, value, onChange }: Props) {
  if (!templates.length) return null;
  const active = templates.find((t) => t.id === value);

  return (
    <div className="templates">
      <select
        className="templates__select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        title={active?.description}
      >
        {templates.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      {active && active.id !== "default" && <span className="templates__hint">{active.description}</span>}
    </div>
  );
}
