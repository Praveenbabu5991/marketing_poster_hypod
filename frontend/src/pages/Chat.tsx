import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useChat } from '../hooks/useChat';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { getSession } from '../api/sessions';
import { getBrand } from '../api/brands';
import { listAgents } from '../api/agents';
import { uploadProductInChat } from '../api/client';
import type { Session, Brand, Agent } from '../types';

const AGENT_PROMPTS: Record<string, string[]> = {
  single_post: [
    'Describe the post topic or theme (e.g. "summer sale announcement")',
    'Mention the platform if you have a preference (Instagram, Facebook, etc.)',
    'Any specific style or mood you want?',
  ],
  carousel: [
    'What story or topic should the carousel cover?',
    'How many slides do you want? (3-10)',
    'Any specific call-to-action for the last slide?',
  ],
  campaign: [
    'What is the campaign goal? (awareness, sales, engagement, etc.)',
    'How many weeks should the campaign run?',
    'Any key dates or events to align with?',
  ],
  sales_poster: [
    'What product or offer should be featured?',
    'Include pricing details or discount percentage',
    'Any specific CTA? (e.g. "Shop Now", "Limited Time")',
  ],
  motion_graphics: [
    'What is the video about? (product launch, promo, announcement)',
    'Preferred duration? (5-15 seconds)',
    'Any specific visual style? (minimal, energetic, elegant)',
  ],
  product_video: [
    'Which product should be showcased?',
    'What key features to highlight?',
    'Any preferred video style? (cinematic, lifestyle, studio)',
  ],
};

export function Chat() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { messages, streaming, sendMessage } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);

  // Fetch session → brand → agent details on mount
  useEffect(() => {
    if (!sessionId) return;
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

  function handleInteractiveSelect(value: string) {
    sendMessage(value);
  }

  const [uploading, setUploading] = useState(false);

  async function handleUploadProduct(file: File) {
    if (!sessionId || uploading) return;
    setUploading(true);
    try {
      await uploadProductInChat(sessionId, file);
      // After upload succeeds, send a message so the agent knows
      sendMessage('I have uploaded the product image');
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  }

  // Show upload button for agents that use product images
  const showUpload = session?.agent_type === 'sales_poster' || session?.agent_type === 'product_video';

  const prompts = session ? AGENT_PROMPTS[session.agent_type] ?? [] : [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border bg-bg-card px-6 py-3">
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

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        {/* Welcome card — shown when no messages yet */}
        {messages.length === 0 && brand && agent && (
          <div className="mx-auto max-w-2xl px-4 py-8">
            <div className="rounded-xl border border-border bg-bg-card p-6 space-y-5">
              {/* Agent intro */}
              <div>
                <h2 className="text-xl font-bold text-text-primary">{agent.name} Agent</h2>
                <p className="mt-1 text-sm text-text-muted">{agent.description}</p>
              </div>

              {/* Brand context summary */}
              <div className="rounded-lg bg-bg-elevated p-4 space-y-2">
                <h3 className="text-sm font-semibold text-text-primary">Brand Context Loaded</h3>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                  <div className="text-text-muted">Brand</div>
                  <div className="text-text-primary">{brand.name}</div>

                  {brand.industry && (
                    <>
                      <div className="text-text-muted">Industry</div>
                      <div className="text-text-primary">{brand.industry}</div>
                    </>
                  )}

                  <div className="text-text-muted">Tone</div>
                  <div className="text-text-primary capitalize">{brand.tone}</div>

                  {brand.target_audience && (
                    <>
                      <div className="text-text-muted">Audience</div>
                      <div className="text-text-primary">{brand.target_audience}</div>
                    </>
                  )}

                  {brand.products_services && (
                    <>
                      <div className="text-text-muted">Products</div>
                      <div className="text-text-primary truncate">{brand.products_services}</div>
                    </>
                  )}

                  <div className="text-text-muted">Logo</div>
                  <div className="text-text-primary">
                    {brand.logo_path ? 'Uploaded' : 'Not set'}
                  </div>

                  <div className="text-text-muted">Colors</div>
                  <div className="flex items-center gap-1.5">
                    {brand.colors.length > 0 ? (
                      brand.colors.map((c, i) => (
                        <div
                          key={i}
                          className="h-4 w-4 rounded-sm border border-border"
                          style={{ backgroundColor: c }}
                          title={c}
                        />
                      ))
                    ) : (
                      <span className="text-text-muted">Not set</span>
                    )}
                  </div>

                  <div className="text-text-muted">Product Images</div>
                  <div className="text-text-primary">
                    {brand.product_images.length > 0
                      ? `${brand.product_images.length} uploaded`
                      : 'None'}
                  </div>
                </div>
              </div>

              {/* Prompts / guidance */}
              {prompts.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-text-primary mb-2">
                    To get started, tell me:
                  </h3>
                  <ul className="space-y-1.5">
                    {prompts.map((p, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-text-muted">
                        <span className="mt-0.5 text-accent">&#x25B8;</span>
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="text-xs text-text-muted border-t border-border pt-3">
                The agent already has your full brand context — just describe what you want to create.
              </p>
            </div>
          </div>
        )}

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
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
        onUploadProduct={handleUploadProduct}
        disabled={streaming || uploading}
        showUpload={showUpload}
      />
    </div>
  );
}
