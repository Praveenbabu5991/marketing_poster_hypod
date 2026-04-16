import { useState } from 'react';

export interface AddSlotData {
  event_name: string;
  event_type: string;
  post_type: string;
  post_idea: string;
  posting_time: string;
}

interface AddSlotPopoverProps {
  date: string; // ISO date e.g. "2026-04-03"
  onSubmit: (data: AddSlotData) => void;
  onClose: () => void;
}

const EVENT_TYPES = [
  { value: 'regular', label: 'Regular' },
  { value: 'festival', label: 'Festival' },
  { value: 'trending', label: 'Trending' },
  { value: 'brand', label: 'Brand' },
];

const POST_TYPES = [
  { value: 'single_post', label: 'Single Post' },
  { value: 'carousel', label: 'Carousel' },
  { value: 'campaign', label: 'Campaign' },
  { value: 'sales_poster', label: 'Sales Poster' },
  { value: 'ugc', label: 'UGC' },
  { value: 'product_ugc', label: 'Product UGC' },
  { value: 'motion_graphics', label: 'Motion Graphics' },
  { value: 'advertisement', label: 'Advertisement' },
];

export function AddSlotPopover({ date, onSubmit, onClose }: AddSlotPopoverProps) {
  const [eventName, setEventName] = useState('');
  const [eventType, setEventType] = useState('regular');
  const [postType, setPostType] = useState('single_post');
  const [postIdea, setPostIdea] = useState('');
  const [postingTime, setPostingTime] = useState('10:00');

  const formattedDate = new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      event_name: eventName,
      event_type: eventType,
      post_type: postType,
      post_idea: postIdea,
      posting_time: postingTime,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative w-full max-w-md rounded-xl border border-border bg-bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4">
          <p className="text-xs text-text-muted">{formattedDate}</p>
          <h3 className="mt-1 text-base font-semibold text-text-primary">Add Content Slot</h3>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">Event Name</label>
            <input
              type="text"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              placeholder="e.g. Women's Day, Summer Sale"
              className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:border-accent focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Event Type</label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Post Type</label>
              <select
                value={postType}
                onChange={(e) => setPostType(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              >
                {POST_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">Post Idea</label>
            <textarea
              value={postIdea}
              onChange={(e) => setPostIdea(e.target.value)}
              rows={3}
              placeholder="Describe the content idea..."
              className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary placeholder:text-text-muted/50 focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-text-muted">Posting Time</label>
            <input
              type="time"
              value={postingTime}
              onChange={(e) => setPostingTime(e.target.value)}
              className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Add Slot
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
