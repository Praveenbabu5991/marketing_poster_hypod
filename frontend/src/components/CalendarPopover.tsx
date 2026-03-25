import { useState } from 'react';
import { MediaPreview } from './MediaPreview';
import type { CalendarSlot, CalendarSlotUpdate } from '../types';

interface CalendarPopoverProps {
  slot: CalendarSlot;
  onClose: () => void;
  onUpdate: (slotId: string, data: CalendarSlotUpdate) => Promise<void>;
  onApproveAndGenerate: (slotId: string) => Promise<void>;
  onViewSession: (slot: CalendarSlot) => void;
}

function formatTime12(time24: string): string {
  const [hStr, mStr] = time24.split(':');
  const h = parseInt(hStr, 10);
  const suffix = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${mStr} ${suffix}`;
}

const AGENT_LABELS: Record<string, string> = {
  single_post: 'Single Post',
  carousel: 'Carousel',
  campaign: 'Campaign',
  sales_poster: 'Sales Poster',
  motion_graphics: 'Motion Graphics',
  product_video: 'Product Video',
};

const TYPE_BADGES: Record<string, { label: string; cls: string }> = {
  festival: { label: 'Festival', cls: 'bg-orange-500/20 text-orange-300' },
  trending: { label: 'Trending', cls: 'bg-pink-500/20 text-pink-300' },
  brand: { label: 'Brand', cls: 'bg-cyan-500/20 text-cyan-300' },
  regular: { label: 'Regular', cls: 'bg-gray-500/20 text-gray-300' },
};

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  suggested: { label: 'Suggested', cls: 'text-blue-300' },
  approved: { label: 'Approved', cls: 'text-green-300' },
  generating: { label: 'Generating...', cls: 'text-yellow-300' },
  generated: { label: 'Generated', cls: 'text-purple-300' },
  skipped: { label: 'Skipped', cls: 'text-gray-400' },
};

export function CalendarPopover({ slot, onClose, onUpdate, onApproveAndGenerate, onViewSession }: CalendarPopoverProps) {
  const [editing, setEditing] = useState(false);
  const [editIdea, setEditIdea] = useState(slot.post_idea || '');
  const [editType, setEditType] = useState(slot.post_type);
  const [loading, setLoading] = useState(false);

  const statusInfo = STATUS_LABELS[slot.status] || STATUS_LABELS.suggested;
  const typeInfo = TYPE_BADGES[slot.event_type || 'regular'] || TYPE_BADGES.regular;

  async function handleApproveAndGenerate() {
    setLoading(true);
    try {
      await onApproveAndGenerate(slot.id);
    } finally {
      setLoading(false);
    }
  }

  async function handleRestore() {
    setLoading(true);
    try {
      await onUpdate(slot.id, { status: 'approved' });
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    setLoading(true);
    try {
      await onUpdate(slot.id, { status: 'skipped' });
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveEdit() {
    setLoading(true);
    try {
      await onUpdate(slot.id, { post_idea: editIdea, post_type: editType });
      setEditing(false);
    } finally {
      setLoading(false);
    }
  }

  const formattedDate = new Date(slot.slot_date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-border bg-bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <div>
            <p className="text-xs text-text-muted">{formattedDate}</p>
            <h3 className="mt-1 text-base font-semibold text-text-primary">
              {slot.event_name || 'Content Slot'}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${typeInfo.cls}`}>
              {typeInfo.label}
            </span>
            <span className={`text-xs font-medium ${statusInfo.cls}`}>{statusInfo.label}</span>
          </div>
        </div>

        {/* Content */}
        {editing ? (
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Post Idea</label>
              <textarea
                value={editIdea}
                onChange={(e) => setEditIdea(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-text-muted">Post Type</label>
              <select
                value={editType}
                onChange={(e) => setEditType(e.target.value)}
                className="w-full rounded-lg border border-border bg-bg-page px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
              >
                {Object.entries(AGENT_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSaveEdit}
                disabled={loading}
                className="rounded-lg bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-lg px-4 py-1.5 text-sm text-text-muted hover:bg-bg-elevated"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Post idea */}
            {slot.post_idea && (
              <p className="mb-3 text-sm leading-relaxed text-text-primary">{slot.post_idea}</p>
            )}

            {/* Post type & time */}
            <div className="mb-4 flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Agent:</span>
                <span className="text-xs font-medium text-text-primary">
                  {AGENT_LABELS[slot.post_type] || slot.post_type}
                </span>
              </div>
              {slot.posting_time && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">Post at:</span>
                  <span className="text-xs font-medium text-text-primary">
                    {formatTime12(slot.posting_time)}
                  </span>
                </div>
              )}
            </div>

            {/* Generated content preview */}
            {slot.generated_image && (
              <div className="mb-4">
                <MediaPreview media={{ image_path: slot.generated_image }} />
                {slot.caption && (
                  <p className="mt-2 text-xs text-text-muted line-clamp-3">{slot.caption}</p>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2">
              {slot.status === 'suggested' && (
                <>
                  <button
                    onClick={handleApproveAndGenerate}
                    disabled={loading}
                    className="rounded-lg bg-green-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={handleSkip}
                    disabled={loading}
                    className="rounded-lg bg-gray-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                  >
                    Skip
                  </button>
                  <button
                    onClick={() => setEditing(true)}
                    className="rounded-lg px-4 py-1.5 text-sm text-text-muted hover:bg-bg-elevated hover:text-text-primary"
                  >
                    Edit
                  </button>
                </>
              )}
              {slot.status === 'approved' && (
                <>
                  {slot.session_id ? (
                    <button
                      onClick={() => { onViewSession(slot); onClose(); }}
                      className="rounded-lg bg-purple-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-purple-700"
                    >
                      View Session
                    </button>
                  ) : (
                    <button
                      onClick={() => setEditing(true)}
                      className="rounded-lg px-4 py-1.5 text-sm text-text-muted hover:bg-bg-elevated hover:text-text-primary"
                    >
                      Edit
                    </button>
                  )}
                </>
              )}
              {(slot.status === 'generated' || slot.status === 'generating') && slot.session_id && (
                <button
                  onClick={() => { onViewSession(slot); onClose(); }}
                  className="rounded-lg bg-purple-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-purple-700"
                >
                  {slot.status === 'generating' ? 'View Progress' : 'View Session'}
                </button>
              )}
              {slot.status === 'skipped' && (
                <button
                  onClick={handleRestore}
                  disabled={loading}
                  className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  Restore
                </button>
              )}
            </div>
          </>
        )}

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
