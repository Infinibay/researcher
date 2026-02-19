export function ErrorMessage({
  message,
  retry,
}: {
  message: string
  retry?: () => void
}) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
      <div className="flex items-start gap-3">
        <svg className="mt-0.5 h-5 w-5 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div className="flex-1">
          <p className="text-sm text-red-300">{message}</p>
          {retry && (
            <button
              onClick={retry}
              className="mt-2 text-sm font-medium text-red-300 hover:text-red-200"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
