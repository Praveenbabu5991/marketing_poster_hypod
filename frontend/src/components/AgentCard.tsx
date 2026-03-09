import type { Agent } from '../types';

interface Props {
  agent: Agent;
  disabled: boolean;
  onClick: () => void;
}

const ICONS: Record<string, string> = {
  image: '\u{1F5BC}',
  layers: '\u{1F4DA}',
  calendar: '\u{1F4C5}',
  tag: '\u{1F3F7}',
  film: '\u{1F3AC}',
  video: '\u{1F4F9}',
};

export function AgentCard({ agent, disabled, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-start gap-2 rounded-xl border border-border bg-bg-card p-5 text-left transition-all hover:border-accent hover:bg-bg-elevated disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-bg-card"
    >
      <span className="text-3xl">{ICONS[agent.icon] || '\u{2699}'}</span>
      <h3 className="text-lg font-semibold text-text-primary">{agent.name}</h3>
      <p className="text-sm text-text-muted">{agent.description}</p>
      {agent.requires_product_images && (
        <span className="mt-1 rounded-full bg-bg-elevated px-2 py-0.5 text-xs text-text-muted">
          Requires product images
        </span>
      )}
    </button>
  );
}
