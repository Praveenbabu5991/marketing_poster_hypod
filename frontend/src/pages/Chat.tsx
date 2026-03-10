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

/** All agents auto-send "start" to trigger a welcome message from the backend. */
const AUTO_START_AGENTS = new Set([
  'single_post',
  'carousel',
  'campaign',
  'sales_poster',
  'motion_graphics',
  'product_video',
  'quick_image',
]);

export function Chat() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { messages, streaming, sendMessage, sendHidden, setMessages } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [brand, setBrand] = useState<Brand | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);
  const sentStartRef = useRef(false);

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

  function handleInteractiveSelect(value: string) {
    sendMessage(value);
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
  const showUpload = session?.agent_type === 'sales_poster' || session?.agent_type === 'product_video';

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
