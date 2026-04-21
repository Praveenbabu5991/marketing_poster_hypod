import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useChat } from '../hooks/useChat';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { getSession } from '../api/sessions';
import { getBrand } from '../api/brands';
import { listAgents } from '../api/agents';
import { uploadProductInChat } from '../api/client';
import { useStore } from '../store/useStore';
import type { Session, Brand, Agent } from '../types';

const IMAGE_AGENTS = new Set([
  'single_post',
  'carousel',
  'sales_poster',
  'quick_image',
]);
const VIDEO_AGENTS = new Set([
  'product_ugc',
  'ugc',
  'motion_graphics',
  'advertisement',
]);

/** Credit costs per user-facing action (mirrors backend ACTION_CREDITS). */
const CREDITS = {
  image: 10,
  video_8s: 400,
  video_16s: 800,
};

/** Decide if a button label triggers an expensive (image/video) action.
 * Returns the expected credit cost, or 0 for cheap/non-expensive actions.
 */
function costForChoice(
  label: string,
  agentType: string | undefined,
  videoDurationSec: number,
): number {
  if (!agentType) return 0;
  const l = label.toLowerCase().trim();

  // Expensive keywords that trigger fresh generation
  const isGen =
    l.includes('generate') ||
    l.includes('create image') ||
    l.includes('create video') ||
    l.includes('approve and generate') ||
    l === 'looks good' ||
    l === 'use this image' ||
    l === 'use this prompt' ||
    l === 'use this idea and generate';

  // Regenerations of the actual asset (NOT regenerating ideas/prompts)
  const isRegenAsset =
    l.includes('regenerate image') ||
    l.includes('regenerate video') ||
    l.includes('retry image') ||
    l.includes('retry video');

  if (!isGen && !isRegenAsset) return 0;

  if (VIDEO_AGENTS.has(agentType)) {
    return videoDurationSec >= 16 ? CREDITS.video_16s : CREDITS.video_8s;
  }
  if (IMAGE_AGENTS.has(agentType)) return CREDITS.image;
  return 0;
}

/** All agents auto-send "start" to trigger a welcome message from the backend. */
const AUTO_START_AGENTS = new Set([
  'single_post',
  'carousel',
  'campaign',
  'sales_poster',
  'ugc',
  'product_ugc',
  'quick_image',
  'motion_graphics',
  'advertisement',
]);

export function Chat() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { messages, streaming, sendMessage, sendHidden, setMessages } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);
  const sentStartRef = useRef(false);
  const { credits, refreshCredits } = useStore();

  // Low-balance modal: set to required cost when user clicks but can't afford
  const [insufficientModal, setInsufficientModal] = useState<{
    required: number;
    balance: number;
  } | null>(null);

  // Poster Settings State
  const [posterSize, setPosterSize] = useState('1080x1080 (Square)');
  const [posterFont, setPosterFont] = useState('Bold Sans-Serif (Default)');

  // Video Settings State
  const [videoSize, setVideoSize] = useState('1080x1920 (Reels / Shorts)');
  const [videoDuration, setVideoDuration] = useState('8');

  // Refresh credits whenever streaming completes (so the badge reflects the latest deduction)
  useEffect(() => {
    if (!streaming) refreshCredits();
  }, [streaming]);

  // Helper to get settings context
  const getSettingsContext = () => {
    const posterAgents = ['sales_poster', 'single_post', 'carousel', 'quick_image'];
    const videoAgents = ['product_ugc', 'ugc', 'motion_graphics', 'advertisement'];
    
    if (session?.agent_type && posterAgents.includes(session.agent_type)) {
      return `Size: ${posterSize}, Font: ${posterFont}`;
    }
    if (session?.agent_type && videoAgents.includes(session.agent_type)) {
      return `Size: ${videoSize}, Duration: ${videoDuration} seconds`;
    }
    return undefined;
  };

  // Fetch session → brand → agent details on mount
  useEffect(() => {
    if (!sessionId) return;
    sentStartRef.current = false;
    getSession(sessionId)
      .then((s) => {
        setSession(s);
        return Promise.all([
          getBrand(s.brand_id),
          listAgents(),
        ]).then(([b, agents]) => {
          setBrand(b);
          setAgent(agents.find((a) => a.id === s.agent_type) ?? null);
        });
      })
      .catch(console.error);
  }, [sessionId]);

  // Auto-send "start" for agents that support welcome messages
  useEffect(() => {
    if (!session || !brand || !agent) return;
    if (sentStartRef.current) return;
    if (messages.length > 0) return;
    if (!AUTO_START_AGENTS.has(session.agent_type)) return;
    sentStartRef.current = true;
    sendHidden('start');
  }, [session, brand, agent, messages.length, sendHidden]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Find the last interactive message index for enabling/disabling
  const lastInteractiveIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].interactive) return i;
    }
    return -1;
  })();

  const videoDurationSec = parseInt(videoDuration, 10) || 8;

  /** Cost helper used by InteractiveCard to render the "N credits" chip. */
  function costForLabel(label: string): number | null {
    const c = costForChoice(label, session?.agent_type, videoDurationSec);
    return c > 0 ? c : null;
  }

  function handleInteractiveSelect(value: string) {
    const cost = costForChoice(value, session?.agent_type, videoDurationSec);
    if (cost > 0 && credits && credits.balance < cost) {
      setInsufficientModal({ required: cost, balance: credits.balance });
      return;
    }
    sendMessage(value, getSettingsContext());
  }

  function handleSend(text: string) {
    sendMessage(text, getSettingsContext());
  }

  const [uploading, setUploading] = useState(false);

  async function handleUploadProduct(file: File) {
    if (!sessionId || uploading) return;
    setUploading(true);
    try {
      const res = await uploadProductInChat(sessionId, file);
      // Show the uploaded image in the conversation as a user message
      const uploadMsg: import('../types').ChatMessage = {
        id: `upload-${Date.now()}`,
        role: 'user',
        content: 'I have uploaded the product image',
        imageUrl: res.url,
      };
      setMessages((prev) => [...prev, uploadMsg]);
      // Send the text message to the agent (without adding another user bubble)
      sendHidden('I have uploaded the product image');
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  }

  // Show upload button for agents that use product images
  const showUpload = session?.agent_type === 'sales_poster' || session?.agent_type === 'product_ugc' || session?.agent_type === 'motion_graphics';

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Header */}
      <div className="flex flex-col border-b border-border bg-bg-card">
        <div className="flex items-center gap-3 px-6 py-3">
          {agent && (
            <span className="rounded-lg bg-bg-elevated px-2.5 py-1 text-sm font-medium text-accent">
              {agent.name}
            </span>
          )}
          {brand && (
            <span className="text-sm text-text-muted">
              for <span className="text-text-primary">{brand.name}</span>
            </span>
          )}
        </div>
        
        {/* Settings Panel for Image Agents */}
        {session?.agent_type && ['sales_poster', 'single_post', 'carousel', 'quick_image'].includes(session.agent_type) && (
          <div className="flex flex-row items-center gap-6 px-6 pb-4 overflow-x-auto">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-text-muted">Size:</span>
              <select 
                value={posterSize} 
                onChange={(e) => setPosterSize(e.target.value)}
                className="rounded-md border border-border bg-bg-page px-2 py-1 text-text-primary outline-none focus:border-accent"
              >
                <option value="1080x1080 (Square)">Square (1:1)</option>
                <option value="1080x1920 (Story)">Story (9:16)</option>
                <option value="1080x1350 (Portrait)">Portrait (4:5)</option>
                <option value="1920x1080 (Landscape)">Landscape (16:9)</option>
              </select>
            </div>

            <div className="flex items-center gap-2 text-sm">
              <span className="text-text-muted">Font:</span>
              <select 
                value={posterFont} 
                onChange={(e) => setPosterFont(e.target.value)}
                className="rounded-md border border-border bg-bg-page px-2 py-1 text-text-primary outline-none focus:border-accent"
              >
                <option value="Bold Sans-Serif (Default)">Bold Sans-Serif (Default)</option>
                <option value="Elegant Serif">Elegant Serif</option>
                <option value="Playful Handwriting">Playful Handwriting</option>
                <option value="Modern Minimalist">Modern Minimalist</option>
                <option value="Heavy Impact">Heavy Impact</option>
              </select>
            </div>
          </div>
        )}

        {/* Settings Panel for Video Agents */}
        {session?.agent_type && ['product_ugc', 'ugc', 'motion_graphics', 'advertisement'].includes(session.agent_type) && (
          <div className="flex flex-row items-center gap-6 px-6 pb-4 overflow-x-auto">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-text-muted">Size:</span>
              <select 
                value={videoSize} 
                onChange={(e) => setVideoSize(e.target.value)}
                className="rounded-md border border-border bg-bg-page px-2 py-1 text-text-primary outline-none focus:border-accent"
              >
                <option value="1080x1920 (Reels / Shorts)">9:16 (Reels / Shorts)</option>
                <option value="1920x1080 (Landscape)">16:9 (Landscape)</option>
              </select>
            </div>

            <div className="flex items-center gap-2 text-sm">
              <span className="text-text-muted">Duration:</span>
              <select 
                value={videoDuration} 
                onChange={(e) => setVideoDuration(e.target.value)}
                className="rounded-md border border-border bg-bg-page px-2 py-1 text-text-primary outline-none focus:border-accent"
              >
                <option value="8">8 Seconds</option>
                <option value="16">16 Seconds</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        {/* Loading state before session/brand loads */}
        {messages.length === 0 && !brand && (
          <div className="flex h-full items-center justify-center text-text-muted">
            Loading session...
          </div>
        )}

        {messages.map((msg, idx) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isLastInteractive={idx === lastInteractiveIdx && !streaming}
            onInteractiveSelect={handleInteractiveSelect}
            costForLabel={costForLabel}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        onUploadProduct={handleUploadProduct}
        disabled={streaming || uploading}
        showUpload={showUpload}
      />

      {/* Insufficient credits modal */}
      {insufficientModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setInsufficientModal(null)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-border bg-bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-text-primary">
              Not enough credits
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              This action needs{' '}
              <span className="font-semibold text-text-primary">
                {insufficientModal.required.toLocaleString()}
              </span>{' '}
              credits. You currently have{' '}
              <span className="font-semibold text-text-primary">
                {insufficientModal.balance.toLocaleString()}
              </span>
              .
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setInsufficientModal(null)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-muted hover:border-accent hover:text-text-primary"
              >
                Close
              </button>
              <Link
                to="/usage"
                onClick={() => setInsufficientModal(null)}
                className="rounded-lg bg-accent px-3 py-1.5 text-sm text-white no-underline hover:bg-accent-hover"
              >
                View plans
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
