import { useRef, useState } from 'react';
import { MediaPreview } from './MediaPreview';
import type { CalendarSlot, CalendarSlotUpdate } from '../types';

export interface SlotConfig {
  image_size?: string;
  font_style?: string;
  aspect_ratio?: string;
  duration?: string;
}

interface CalendarPopoverProps {
  slot: CalendarSlot;
  onClose: () => void;
  onUpdate: (slotId: string, data: CalendarSlotUpdate) => Promise<void>;
  onApproveAndGenerate: (slotId: string, config?: SlotConfig) => Promise<void>;
  onViewSession: (slot: CalendarSlot) => void;
  onRegenerate: (slot: CalendarSlot) => void;
  hasProductImages: boolean;
  onUploadProductImage: (file: File) => Promise<void>;
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
  ugc: 'UGC',
  product_ugc: 'Product UGC',
  motion_graphics: 'Motion Graphics',
  creative_video: 'Creative Video',
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

const IMAGE_SIZES = [
  { value: '1080x1080', label: '1080x1080 (Square)' },
  { value: '1080x1350', label: '1080x1350 (Portrait)' },
  { value: '1920x1080', label: '1920x1080 (Landscape)' },
];

const FONT_STYLES = [
  { value: 'modern', label: 'Modern' },
  { value: 'classic', label: 'Classic' },
  { value: 'bold', label: 'Bold' },
  { value: 'minimal', label: 'Minimal' },
  { value: 'elegant', label: 'Elegant' },
];

const ASPECT_RATIOS = [
  { value: '9:16', label: '9:16 (Portrait/Reels)' },
  { value: '16:9', label: '16:9 (Landscape)' },
  { value: '1:1', label: '1:1 (Square)' },
];

const DURATIONS = [
  { value: '6', label: '6 seconds' },
  { value: '10', label: '10 seconds' },
  { value: '15', label: '15 seconds' },
  { value: '30', label: '30 seconds' },
];

const POSTER_TYPES = new Set(['single_post', 'carousel', 'sales_poster', 'campaign']);
const VIDEO_TYPES = new Set(['ugc', 'product_ugc', 'motion_graphics', 'creative_video']);

export function CalendarPopover({
  slot,
  onClose,
  onUpdate,
  onApproveAndGenerate,
  onViewSession,
  onRegenerate,
  hasProductImages,
  onUploadProductImage,
}: CalendarPopoverProps) {
  const [editing, setEditing] = useState(false);
  const [editIdea, setEditIdea] = useState(slot.post_idea || '');
  const [editType, setEditType] = useState(slot.post_type);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Config state for generation options
  const [imageSize, setImageSize] = useState('1080x1080');
  const [fontStyle, setFontStyle] = useState('modern');
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [duration, setDuration] = useState('10');

  const statusInfo = STATUS_LABELS[slot.status] || STATUS_LABELS.suggested;
  const typeInfo = TYPE_BADGES[slot.event_type || 'regular'] || TYPE_BADGES.regular;

  const isPoster = POSTER_TYPES.has(slot.post_type);
  const isVideo = VIDEO_TYPES.has(slot.post_type);
  const needsProductImage = slot.post_type === 'sales_poster' || slot.post_type === 'product_ugc' || slot.post_type === 'motion_graphics';

  async function handleApproveAndGenerate() {
    setLoading(true);
    try {
      const config: SlotConfig = {};
      if (isPoster) {
        config.image_size = imageSize;
        config.font_style = fontStyle;
      }
      if (isVideo) {
        config.aspect_ratio = aspectRatio;
        config.duration = duration;
      }
      await onApproveAndGenerate(slot.id, config);
    } finally {
      setLoading(false);
    }
  }

  async function handleRestore() {
    setLoading(true);
    try {
      await onUpdate(slot.id, { status: 'suggested' });
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
      await onUpdate(slot.id, { post_idea: editIdea, post_type: editType, status: 'suggested' });
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
        className="relative w-full max-w-md rounded-xl border border-border bg-bg-card p-5 shadow-2xl"
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

            {/* Product image: upload prompt or success confirmation */}
            {slot.status === 'suggested' && needsProductImage && (
              <>
                {hasProductImages || uploadedFileName ? (
                  <div className="mb-3 rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5 shrink-0 text-green-400">
                      <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                    </svg>
                    <span className="text-xs text-green-300">
                      {uploadedFileName
                        ? `Product image uploaded: ${uploadedFileName}`
                        : 'Product image available'}
                    </span>
                    <label className="ml-auto cursor-pointer text-[10px] text-green-400 hover:text-green-300 underline">
                      Change
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setUploading(true);
                          try {
                            await onUploadProductImage(file);
                            setUploadedFileName(file.name);
                          } finally {
                            setUploading(false);
                          }
                        }}
                      />
                    </label>
                  </div>
                ) : (
                  <div className="mb-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2">
                    <p className="text-xs text-yellow-300 mb-2">
                      This post type requires a product image.
                    </p>
                    <label
                      className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-yellow-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-yellow-700 transition-colors ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                        <path d="M7.25 10.25a.75.75 0 0 0 1.5 0V4.56l2.22 2.22a.75.75 0 1 0 1.06-1.06l-3.5-3.5a.75.75 0 0 0-1.06 0l-3.5 3.5a.75.75 0 0 0 1.06 1.06l2.22-2.22v5.69Z" />
                        <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
                      </svg>
                      {uploading ? 'Uploading...' : 'Upload Product Image'}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setUploading(true);
                          try {
                            await onUploadProductImage(file);
                            setUploadedFileName(file.name);
                          } finally {
                            setUploading(false);
                            if (fileInputRef.current) fileInputRef.current.value = '';
                          }
                        }}
                      />
                    </label>
                  </div>
                )}
              </>
            )}

            {/* Config options for suggested slots */}
            {slot.status === 'suggested' && (
              <div className="mb-4 space-y-2 rounded-lg border border-border bg-bg-page p-3">
                <p className="text-[10px] font-medium text-text-muted uppercase tracking-wide">Generation Options</p>
                {isPoster && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="mb-0.5 block text-[10px] text-text-muted">Image Size</label>
                      <select
                        value={imageSize}
                        onChange={(e) => setImageSize(e.target.value)}
                        className="w-full rounded border border-border bg-bg-card px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
                      >
                        {IMAGE_SIZES.map((s) => (
                          <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-0.5 block text-[10px] text-text-muted">Font Style</label>
                      <select
                        value={fontStyle}
                        onChange={(e) => setFontStyle(e.target.value)}
                        className="w-full rounded border border-border bg-bg-card px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
                      >
                        {FONT_STYLES.map((f) => (
                          <option key={f.value} value={f.value}>{f.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}
                {isVideo && (
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="mb-0.5 block text-[10px] text-text-muted">Aspect Ratio</label>
                      <select
                        value={aspectRatio}
                        onChange={(e) => setAspectRatio(e.target.value)}
                        className="w-full rounded border border-border bg-bg-card px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
                      >
                        {ASPECT_RATIOS.map((a) => (
                          <option key={a.value} value={a.value}>{a.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-0.5 block text-[10px] text-text-muted">Duration</label>
                      <select
                        value={duration}
                        onChange={(e) => setDuration(e.target.value)}
                        className="w-full rounded border border-border bg-bg-card px-2 py-1 text-xs text-text-primary focus:border-accent focus:outline-none"
                      >
                        {DURATIONS.map((d) => (
                          <option key={d.value} value={d.value}>{d.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}
              </div>
            )}

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
                    disabled={loading || (needsProductImage && !hasProductImages)}
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
                  <button
                    onClick={() => { onRegenerate(slot); onClose(); }}
                    disabled={loading}
                    className="rounded-lg px-4 py-1.5 text-sm text-text-muted hover:bg-bg-elevated hover:text-text-primary"
                  >
                    Regenerate Idea
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
