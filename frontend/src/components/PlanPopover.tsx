import { useState } from 'react';

interface PlanPopoverProps {
  maxDays: number;
  defaultCount: number;
  isRegenerate: boolean;
  onSubmit: (postsCount: number) => void;
  onClose: () => void;
}

export function PlanPopover({ maxDays, defaultCount, isRegenerate, onSubmit, onClose }: PlanPopoverProps) {
  const [postsCount, setPostsCount] = useState(defaultCount);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(Math.max(1, Math.min(maxDays, postsCount)));
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative w-full max-w-xs rounded-xl border border-border bg-bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-base font-semibold text-text-primary">
          {isRegenerate ? 'Regenerate Plan' : 'Generate Plan'}
        </h3>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">Number of Posts</label>
            <div className="flex items-center rounded-lg border border-border bg-bg-page">
              <button
                type="button"
                onClick={() => setPostsCount((c) => Math.max(1, c - 1))}
                disabled={postsCount <= 1}
                className="px-3 py-2 text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors"
              >
                -
              </button>
              <input
                type="number"
                min={1}
                max={maxDays}
                value={postsCount}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v)) setPostsCount(Math.max(1, Math.min(maxDays, v)));
                }}
                className="w-12 bg-transparent text-center text-sm text-text-primary outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                type="button"
                onClick={() => setPostsCount((c) => Math.min(maxDays, c + 1))}
                disabled={postsCount >= maxDays}
                className="px-3 py-2 text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors"
              >
                +
              </button>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">{maxDays} days in this month</p>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              {isRegenerate ? 'Regenerate' : 'Generate'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-1.5 text-sm text-text-muted hover:bg-bg-elevated"
            >
              Cancel
            </button>
          </div>
        </form>

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 rounded p-1 text-text-muted hover:bg-bg-elevated hover:text-text-primary"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
