import type { ChatMessage as ChatMessageType } from '../types';
import { ToolIndicator } from './ToolIndicator';
import { InteractiveCard } from './InteractiveCard';

interface Props {
  message: ChatMessageType;
  isLastInteractive: boolean;
  onInteractiveSelect: (value: string) => void;
}

export function ChatMessage({ message, isLastInteractive, onInteractiveSelect }: Props) {
  if (message.role === 'tool') {
    return <ToolIndicator message={message.content} active={message.toolActive ?? false} />;
  }

  if (message.role === 'status') {
    return (
      <div className="flex items-center gap-2 px-4 py-2 text-sm text-text-muted">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        {message.content}
      </div>
    );
  }

  if (message.role === 'error') {
    return (
      <div className="mx-4 my-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
        {message.content}
      </div>
    );
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end px-4 py-2">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-sm text-white">
          {message.imageUrl && (
            <img
              src={message.imageUrl}
              alt="Uploaded product"
              className="mb-2 max-w-full rounded-lg"
              style={{ maxHeight: 200 }}
            />
          )}
          {message.content}
        </div>
      </div>
    );
  }

  // assistant
  const displayContent = typeof message.content === 'string' ? message.content : '';
  return (
    <div className="flex justify-start px-4 py-2">
      <div className="max-w-[75%] space-y-2 rounded-2xl rounded-bl-md bg-bg-elevated px-4 py-3 text-sm text-text-primary">
        {displayContent && <div className="whitespace-pre-wrap">{displayContent}</div>}
        {message.interactive && (
          <InteractiveCard
            data={message.interactive}
            onSelect={onInteractiveSelect}
            disabled={!isLastInteractive}
          />
        )}
      </div>
    </div>
  );
}
