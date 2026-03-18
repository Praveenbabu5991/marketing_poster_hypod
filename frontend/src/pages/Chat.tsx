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

  // Poster Settings State
  const [posterSize, setPosterSize] = useState('1080x1080 (Square)');
  const [posterFont, setPosterFont] = useState('Bold Sans-Serif (Default)');

  // Video Settings State
  const [videoSize, setVideoSize] = useState('1080x1920 (Reels / Shorts)');

  // Helper to get settings context
  const getSettingsContext = () => {
    const posterAgents = ['sales_poster', 'single_post', 'carousel', 'quick_image'];
    const videoAgents = ['product_video', 'motion_graphics'];
    
    if (session?.agent_type && posterAgents.includes(session.agent_type)) {
      return `Size: ${posterSize}, Font: ${posterFont}`;
    }
    if (session?.agent_type && videoAgents.includes(session.agent_type)) {
      return `Size: ${videoSize}`;
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

  function handleInteractiveSelect(value: string) {
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
  const showUpload = session?.agent_type === 'sales_poster' || session?.agent_type === 'product_video';

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
        {session?.agent_type && ['product_video', 'motion_graphics'].includes(session.agent_type) && (
          <div className="flex flex-row items-center gap-6 px-6 pb-4 overflow-x-auto">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-text-muted">Size:</span>
              <select 
                value={videoSize} 
                onChange={(e) => setVideoSize(e.target.value)}
                className="rounded-md border border-border bg-bg-page px-2 py-1 text-text-primary outline-none focus:border-accent"
              >
                <option value="1080x1920 (Reels / Shorts)">9:16 (Reels / Shorts)</option>
                <option value="1080x1080 (Instagram Post)">1:1 (Instagram Post)</option>
                <option value="1920x1080 (Landscape)">16:9 (Landscape)</option>
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
    </div>
  );
}
