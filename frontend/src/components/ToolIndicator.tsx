interface Props {
  message: string;
  active: boolean;
}

export function ToolIndicator({ message, active }: Props) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm text-text-muted">
      {active ? (
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      ) : (
        <svg className="h-4 w-4 text-green-500" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clipRule="evenodd"
          />
        </svg>
      )}
      <span>{message}</span>
    </div>
  );
}
