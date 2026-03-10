import { useState } from 'react';

interface Props {
  media: { image_path?: string; video_path?: string };
}

export function MediaPreview({ media }: Props) {
  const [zoomed, setZoomed] = useState(false);

  if (media.image_path) {
    const src = toUrl(media.image_path);
    const filename = media.image_path.split('/').pop() || 'image.png';

    return (
      <>
        {/* Inline preview */}
        <div className="relative mt-2 inline-block group">
          <img
            src={src}
            alt="Generated content"
            className="max-w-full rounded-lg border border-border cursor-zoom-in"
            style={{ maxHeight: 400 }}
            onClick={() => setZoomed(true)}
          />
          {/* Hover overlay with actions */}
          <div className="absolute bottom-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => setZoomed(true)}
              className="p-1.5 rounded-md bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm"
              title="Zoom"
            >
              <ZoomIcon />
            </button>
            <a
              href={src}
              download={filename}
              className="p-1.5 rounded-md bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm"
              title="Download"
            >
              <DownloadIcon />
            </a>
          </div>
        </div>

        {/* Lightbox modal */}
        {zoomed && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
            onClick={() => setZoomed(false)}
          >
            {/* Top-right controls */}
            <div className="absolute top-4 right-4 flex gap-2 z-10">
              <a
                href={src}
                download={filename}
                onClick={(e) => e.stopPropagation()}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                title="Download"
              >
                <DownloadIcon size={20} />
              </a>
              <button
                onClick={() => setZoomed(false)}
                className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                title="Close"
              >
                <CloseIcon size={20} />
              </button>
            </div>
            {/* Full-size image */}
            <img
              src={src}
              alt="Generated content"
              className="max-w-[90vw] max-h-[90vh] rounded-lg object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </>
    );
  }

  if (media.video_path) {
    const src = toUrl(media.video_path);
    const filename = media.video_path.split('/').pop() || 'video.mp4';

    return (
      <div className="relative mt-2 inline-block group">
        <video
          src={src}
          controls
          className="max-w-full rounded-lg border border-border"
          style={{ maxHeight: 400 }}
        />
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <a
            href={src}
            download={filename}
            className="p-1.5 rounded-md bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm"
            title="Download"
          >
            <DownloadIcon />
          </a>
        </div>
      </div>
    );
  }

  return null;
}

function toUrl(path: string): string {
  const genIdx = path.indexOf('/generated/');
  if (genIdx !== -1) return path.slice(genIdx);
  const uplIdx = path.indexOf('/uploads/');
  if (uplIdx !== -1) return path.slice(uplIdx);
  return path;
}

function ZoomIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}

function DownloadIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function CloseIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
