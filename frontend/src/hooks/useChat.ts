import { useState, useCallback, useRef, useEffect } from 'react';
import { fetchChatSSE } from '../api/client';
import type { ChatMessage, SSEEvent } from '../types';

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}`;
}

const STORAGE_PREFIX = 'chat-messages-';

function loadMessages(sessionId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + sessionId);
    if (!raw) return [];
    const msgs: ChatMessage[] = JSON.parse(raw);
    // Mark all tools as completed when restoring
    return msgs.map((m) =>
      m.role === 'tool' ? { ...m, toolActive: false } : m,
    );
  } catch {
    return [];
  }
}

function saveMessages(sessionId: string, messages: ChatMessage[]) {
  try {
    // Don't persist transient status messages
    const toSave = messages.filter((m) => m.role !== 'status');
    localStorage.setItem(STORAGE_PREFIX + sessionId, JSON.stringify(toSave));
  } catch {
    // localStorage full — ignore
  }
}

export function useChat(sessionId: string | undefined) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);

  // Keep ref in sync for saving
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Load persisted messages when session changes
  useEffect(() => {
    if (sessionId) {
      const saved = loadMessages(sessionId);
      setMessages(saved);
      // Ensure counter is above any existing IDs
      for (const m of saved) {
        const num = parseInt(m.id.replace('msg-', ''), 10);
        if (!isNaN(num) && num >= msgCounter) msgCounter = num + 1;
      }
    } else {
      setMessages([]);
    }
  }, [sessionId]);

  // Persist messages after streaming ends
  const persistMessages = useCallback(() => {
    if (sessionId) {
      saveMessages(sessionId, messagesRef.current);
    }
  }, [sessionId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || streaming) return;

      // Add user message
      const userMsg: ChatMessage = {
        id: nextId(),
        role: 'user',
        content: text.trim(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      // ID for the assistant message we'll accumulate into
      const assistantId = nextId();
      let assistantAdded = false;

      try {
        const res = await fetchChatSSE(sessionId, text.trim(), controller.signal);
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(body.detail || `Chat failed: ${res.status}`);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Split on double newline (SSE event boundary)
          const parts = buffer.split('\n\n');
          buffer = parts.pop()!; // keep incomplete chunk

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;

            let event: SSEEvent;
            try {
              event = JSON.parse(line.slice(6));
            } catch {
              continue;
            }

            // Helper: remove any transient status messages
            const stripStatus = (msgs: ChatMessage[]) =>
              msgs.filter((m) => m.role !== 'status');

            switch (event.type) {
              case 'text': {
                // Ensure content is always a string (Gemini can return arrays)
                const textContent = typeof event.content === 'string'
                  ? event.content
                  : String(event.content ?? '');
                if (!textContent) break;
                if (!assistantAdded) {
                  assistantAdded = true;
                  setMessages((prev) => [
                    ...stripStatus(prev),
                    { id: assistantId, role: 'assistant', content: textContent },
                  ]);
                } else {
                  setMessages((prev) =>
                    stripStatus(prev).map((m) =>
                      m.id === assistantId
                        ? { ...m, content: m.content + textContent }
                        : m,
                    ),
                  );
                }
                break;
              }

              case 'tool_start': {
                const toolId = nextId();
                setMessages((prev) => [
                  ...stripStatus(prev),
                  {
                    id: toolId,
                    role: 'tool',
                    content: event.message,
                    toolName: event.tool,
                    toolActive: true,
                  },
                ]);
                break;
              }

              case 'tool_end': {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.role === 'tool' && m.toolName === event.tool && m.toolActive
                      ? { ...m, toolActive: false }
                      : m,
                  ),
                );
                // Reset assistant accumulation so next text starts fresh
                assistantAdded = false;
                break;
              }

              case 'interactive': {
                const intId = nextId();
                setMessages((prev) => [
                  ...stripStatus(prev),
                  {
                    id: intId,
                    role: 'assistant',
                    content: event.content.message,
                    interactive: event.content,
                  },
                ]);
                break;
              }

              case 'status': {
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: nextId(), role: 'status', content: event.message },
                ]);
                break;
              }

              case 'error': {
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: nextId(), role: 'error', content: event.content },
                ]);
                break;
              }

              case 'done':
                // Remove any lingering status messages
                setMessages((prev) => stripStatus(prev));
                break;
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // cancelled by user
        } else {
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              role: 'error',
              content: err instanceof Error ? err.message : 'Stream failed',
            },
          ]);
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
        // Persist all messages after stream completes
        // Use setTimeout to ensure state has settled
        setTimeout(persistMessages, 50);
      }
    },
    [sessionId, streaming, persistMessages],
  );

  /** Send a message without showing a user bubble — used for the initial "start" trigger. */
  const sendHidden = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || streaming) return;

      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const assistantId = nextId();
      let assistantAdded = false;

      try {
        const res = await fetchChatSSE(sessionId, text.trim(), controller.signal);
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(body.detail || `Chat failed: ${res.status}`);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split('\n\n');
          buffer = parts.pop()!;

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith('data: ')) continue;

            let event: SSEEvent;
            try {
              event = JSON.parse(line.slice(6));
            } catch {
              continue;
            }

            const stripStatus = (msgs: ChatMessage[]) =>
              msgs.filter((m) => m.role !== 'status');

            switch (event.type) {
              case 'text': {
                const textContent = typeof event.content === 'string'
                  ? event.content
                  : String(event.content ?? '');
                if (!textContent) break;
                if (!assistantAdded) {
                  assistantAdded = true;
                  setMessages((prev) => [
                    ...stripStatus(prev),
                    { id: assistantId, role: 'assistant', content: textContent },
                  ]);
                } else {
                  setMessages((prev) =>
                    stripStatus(prev).map((m) =>
                      m.id === assistantId
                        ? { ...m, content: m.content + textContent }
                        : m,
                    ),
                  );
                }
                break;
              }
              case 'tool_start': {
                const toolId = nextId();
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: toolId, role: 'tool', content: event.message, toolName: event.tool, toolActive: true },
                ]);
                break;
              }
              case 'tool_end': {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.role === 'tool' && m.toolName === event.tool && m.toolActive
                      ? { ...m, toolActive: false }
                      : m,
                  ),
                );
                assistantAdded = false;
                break;
              }
              case 'interactive': {
                const intId = nextId();
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: intId, role: 'assistant', content: event.content.message, interactive: event.content },
                ]);
                break;
              }
              case 'status': {
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: nextId(), role: 'status', content: event.message },
                ]);
                break;
              }
              case 'error': {
                setMessages((prev) => [
                  ...stripStatus(prev),
                  { id: nextId(), role: 'error', content: event.content },
                ]);
                break;
              }
              case 'done':
                setMessages((prev) => stripStatus(prev));
                break;
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // cancelled
        } else {
          setMessages((prev) => [
            ...prev,
            { id: nextId(), role: 'error', content: err instanceof Error ? err.message : 'Stream failed' },
          ]);
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
        setTimeout(persistMessages, 50);
      }
    },
    [sessionId, streaming, persistMessages],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { messages, streaming, sendMessage, sendHidden, cancel, setMessages };
}
