import { useRef, useEffect } from 'react';
import { MediaPreview } from './MediaPreview';
import type { ChatMessage, CalendarSlot } from '../types';

interface CalendarSidebarProps {
  messages: ChatMessage[];
  streaming: boolean;
  onSendMessage: (text: string) => void;
  planStatus: string;
  mode: 'planner' | 'content';
  contentSlot?: CalendarSlot;
  onBackToPlanner: () => void;
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

export function CalendarSidebar({
  messages,
  streaming,
  onSendMessage,
  planStatus,
  mode,
  contentSlot,
  onBackToPlanner,
}: CalendarSidebarProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const input = inputRef.current;
    if (!input || !input.value.trim() || streaming) return;
    onSendMessage(input.value.trim());
    input.value = '';
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        {mode === 'content' && contentSlot ? (
          <>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">
                {AGENT_LABELS[contentSlot.post_type] || contentSlot.post_type}
              </h3>
              <button
                onClick={onBackToPlanner}
                disabled={streaming}
                className="text-[10px] text-accent hover:text-accent-hover disabled:opacity-50"
              >
                &larr; Back to Planner
              </button>
            </div>
            <p className="mt-0.5 text-[10px] text-text-muted truncate">
              {contentSlot.event_name || contentSlot.post_idea?.slice(0, 50) || 'Generating content...'}
            </p>
          </>
        ) : (
          <>
            <h3 className="text-sm font-semibold text-text-primary">AI Planner</h3>
            <p className="text-[10px] text-text-muted">
              {planStatus === 'draft'
                ? 'Generate a content plan for this month'
                : 'Ask AI to modify the plan'}
            </p>
          </>
        )}
      </div>

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && !streaming && mode === 'planner' && (
          <p className="text-xs text-text-muted text-center py-8">
            Click "Generate Plan" to start, or type a message to the AI planner.
          </p>
        )}

        {messages.length === 0 && !streaming && mode === 'content' && (
          <p className="text-xs text-text-muted text-center py-8">
            Starting content generation...
          </p>
        )}

        {messages.map((msg) => {
          if (msg.role === 'status') {
            return (
              <div key={msg.id} className="flex items-center gap-2 text-xs text-text-muted">
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-text-muted border-t-transparent" />
                {msg.content}
              </div>
            );
          }
          if (msg.role === 'tool') {
            return (
              <div key={msg.id} className="flex items-center gap-2 text-[10px] text-text-muted">
                {msg.toolActive ? (
                  <div className="h-2.5 w-2.5 animate-spin rounded-full border border-text-muted border-t-transparent" />
                ) : (
                  <span className="text-green-400">&#10003;</span>
                )}
                {msg.content}
              </div>
            );
          }
          if (msg.role === 'error') {
            return (
              <div key={msg.id} className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {msg.content}
              </div>
            );
          }
          if (msg.role === 'user') {
            return (
              <div key={msg.id} className="flex justify-end">
                <div className="max-w-[85%] rounded-lg bg-accent/20 px-3 py-2 text-xs text-text-primary">
                  {msg.content}
                </div>
              </div>
            );
          }
          // assistant — show media preview if available
          return (
            <div key={msg.id} className="space-y-2">
              <div className="rounded-lg bg-bg-elevated px-3 py-2 text-xs text-text-primary leading-relaxed">
                {msg.content}
              </div>
              {msg.interactive?.media && (msg.interactive.media.image_path || msg.interactive.media.video_path) && (
                <MediaPreview media={msg.interactive.media} />
              )}
              {/* Show choices if available */}
              {msg.interactive?.choices && msg.interactive.choices.length > 0 && (
                <div className="space-y-1">
                  {msg.interactive.choices.map((choice) => (
                    <button
                      key={choice.id}
                      onClick={() => onSendMessage(choice.label)}
                      disabled={streaming}
                      className="w-full rounded-lg border border-border bg-bg-page px-3 py-1.5 text-left text-[11px] text-text-primary hover:border-accent/50 hover:bg-bg-elevated disabled:opacity-50 transition-colors"
                    >
                      <span className="font-medium">{choice.label}</span>
                      {choice.description && (
                        <span className="ml-1 text-text-muted">— {choice.description}</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-border p-3">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder={mode === 'content' ? 'Tell the agent what to change...' : 'Ask AI to adjust the plan...'}
            disabled={streaming}
            className="flex-1 rounded-lg border border-border bg-bg-page px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming}
            className="rounded-lg bg-accent px-3 py-2 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
