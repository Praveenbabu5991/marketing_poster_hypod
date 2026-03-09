import { useState, useRef, type KeyboardEvent } from 'react';

interface Props {
  onSend: (message: string) => void;
  onUploadProduct?: (file: File) => void;
  disabled: boolean;
  showUpload?: boolean;
}

export function ChatInput({ onSend, onUploadProduct, disabled, showUpload }: Props) {
  const [text, setText] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  function handleSend() {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText('');
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && onUploadProduct) {
      onUploadProduct(file);
    }
    // Reset so user can upload same file again if needed
    if (fileRef.current) fileRef.current.value = '';
  }

  return (
    <div className="flex gap-2 border-t border-border bg-bg-card p-4">
      {showUpload && (
        <>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={disabled}
            title="Upload product image"
            className="flex items-center justify-center rounded-lg border border-border bg-bg-page px-3 py-3 text-text-muted transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </button>
        </>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKey}
        placeholder="Type a message..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none rounded-lg border border-border bg-bg-page px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        className="rounded-lg bg-accent px-6 py-3 font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:hover:bg-accent"
      >
        Send
      </button>
    </div>
  );
}
