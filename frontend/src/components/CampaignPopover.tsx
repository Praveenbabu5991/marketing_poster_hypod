import { useState, useMemo } from 'react';

interface CampaignPopoverProps {
  year: number;
  month: number;
  onSubmit: (theme: string, fromDate: string, toDate: string, postsCount: number) => void;
  onClose: () => void;
}

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

function daysBetween(from: string, to: string): number {
  const a = new Date(from + 'T00:00:00');
  const b = new Date(to + 'T00:00:00');
  return Math.max(1, Math.round((b.getTime() - a.getTime()) / 86400000) + 1);
}

export function CampaignPopover({ year, month, onSubmit, onClose }: CampaignPopoverProps) {
  const now = new Date();
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth() + 1;
  const lastDay = new Date(year, month, 0).getDate();

  const defaultFrom = isCurrentMonth
    ? `${year}-${pad(month)}-${pad(now.getDate())}`
    : `${year}-${pad(month)}-01`;
  const defaultTo = `${year}-${pad(month)}-${pad(lastDay)}`;

  const [theme, setTheme] = useState('');
  const [fromDate, setFromDate] = useState(defaultFrom);
  const [toDate, setToDate] = useState(defaultTo);
  const [postsCount, setPostsCount] = useState(4);

  const minDate = `${year}-${pad(month)}-01`;
  const maxDate = defaultTo;

  const maxPosts = useMemo(() => daysBetween(fromDate, toDate), [fromDate, toDate]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!theme.trim()) return;
    const clamped = Math.max(1, Math.min(maxPosts, postsCount));
    onSubmit(theme.trim(), fromDate, toDate, clamped);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative w-full max-w-md rounded-xl border border-border bg-bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4">
          <p className="text-xs text-text-muted">
            {new Date(year, month - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
          </p>
          <h3 className="mt-1 text-base font-semibold text-text-primary">Generate Campaign</h3>
          <p className="mt-0.5 text-xs text-text-muted">
            Create a multi-day campaign with mixed content (images + videos)
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">Theme / Content</label>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="e.g. Valentine's Day, Summer Sale, Diwali"
              required
              autoFocus
              className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:border-accent focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">From Date</label>
              <input
                type="date"
                value={fromDate}
                min={minDate}
                max={maxDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  if (e.target.value > toDate) setToDate(e.target.value);
                }}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">To Date</label>
              <input
                type="date"
                value={toDate}
                min={fromDate || minDate}
                max={maxDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>

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
                max={maxPosts}
                value={postsCount}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v)) setPostsCount(Math.max(1, Math.min(maxPosts, v)));
                }}
                className="w-12 bg-transparent text-center text-sm text-text-primary outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button
                type="button"
                onClick={() => setPostsCount((c) => Math.min(maxPosts, c + 1))}
                disabled={postsCount >= maxPosts}
                className="px-3 py-2 text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors"
              >
                +
              </button>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">
              {daysBetween(fromDate, toDate)} days selected
            </p>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={!theme.trim()}
              className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              Start Campaign
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
