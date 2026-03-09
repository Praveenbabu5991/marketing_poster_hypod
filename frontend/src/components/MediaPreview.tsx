interface Props {
  media: { image_path?: string; video_path?: string };
}

export function MediaPreview({ media }: Props) {
  if (media.image_path) {
    // Convert absolute path to URL via /generated or /uploads proxy
    const src = toUrl(media.image_path);
    return (
      <img
        src={src}
        alt="Generated content"
        className="mt-2 max-w-full rounded-lg border border-border"
        style={{ maxHeight: 400 }}
      />
    );
  }

  if (media.video_path) {
    const src = toUrl(media.video_path);
    return (
      <video
        src={src}
        controls
        className="mt-2 max-w-full rounded-lg border border-border"
        style={{ maxHeight: 400 }}
      />
    );
  }

  return null;
}

function toUrl(path: string): string {
  // Path may be absolute filesystem path like /home/.../generated/foo.png
  // Extract the /generated/... or /uploads/... portion
  const genIdx = path.indexOf('/generated/');
  if (genIdx !== -1) return path.slice(genIdx);
  const uplIdx = path.indexOf('/uploads/');
  if (uplIdx !== -1) return path.slice(uplIdx);
  // Fallback: already a relative URL
  return path;
}
