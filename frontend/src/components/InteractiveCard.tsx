import { useState } from 'react';
import type { InteractiveResponse } from '../types';
import { MediaPreview } from './MediaPreview';

interface Props {
  data: InteractiveResponse;
  onSelect: (value: string) => void;
  disabled: boolean;
}

export function InteractiveCard({ data, onSelect, disabled }: Props) {
  const [freeText, setFreeText] = useState('');
  const [selectedMulti, setSelectedMulti] = useState<Set<string>>(new Set());

  function handleChoice(label: string) {
    if (disabled) return;
    onSelect(label);
  }

  function handleMultiToggle(id: string) {
    setSelectedMulti((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleMultiSubmit() {
    if (disabled || selectedMulti.size === 0) return;
    const labels = data.choices
      .filter((c) => selectedMulti.has(c.id))
      .map((c) => c.label);
    onSelect(labels.join(', '));
  }

  function handleFreeSubmit() {
    if (disabled || !freeText.trim()) return;
    onSelect(freeText.trim());
    setFreeText('');
  }

  return (
    <div className="space-y-3">
      {data.media && <MediaPreview media={data.media} />}

      {data.has_choices && data.choice_type === 'multi_select' ? (
        <div className="space-y-2">
          {data.choices.map((c) => (
            <label
              key={c.id}
              className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
                disabled
                  ? 'border-border opacity-60'
                  : selectedMulti.has(c.id)
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-accent/50'
              }`}
            >
              <input
                type="checkbox"
                checked={selectedMulti.has(c.id)}
                onChange={() => handleMultiToggle(c.id)}
                disabled={disabled}
                className="accent-accent"
              />
              <span className="text-sm text-text-primary">{c.label}</span>
              {c.description && (
                <span className="text-xs text-text-muted">— {c.description}</span>
              )}
            </label>
          ))}
          {!disabled && (
            <button
              onClick={handleMultiSubmit}
              disabled={selectedMulti.size === 0}
              className="mt-1 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
            >
              Submit Selection
            </button>
          )}
        </div>
      ) : data.has_choices ? (
        <div className="space-y-2">
          {data.choices.map((c) => (
            <button
              key={c.id}
              onClick={() => handleChoice(c.label)}
              disabled={disabled}
              className="block w-full rounded-lg border border-border bg-bg-card px-4 py-3 text-left transition-colors hover:border-accent hover:bg-bg-elevated disabled:opacity-60 disabled:hover:border-border disabled:hover:bg-bg-card"
            >
              <div className="text-sm font-medium text-text-primary">{c.label}</div>
              {c.description && (
                <div className="mt-1 text-xs text-text-muted">{c.description}</div>
              )}
            </button>
          ))}
        </div>
      ) : null}

      {data.allow_free_input && !disabled && (
        <div className="flex gap-2">
          <input
            type="text"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleFreeSubmit()}
            placeholder={data.input_placeholder}
            className="flex-1 rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
          <button
            onClick={handleFreeSubmit}
            disabled={!freeText.trim()}
            className="rounded-lg bg-accent px-3 py-2 text-sm text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
