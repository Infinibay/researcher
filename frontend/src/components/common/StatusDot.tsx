const colors = {
  active: 'bg-emerald-400',
  inactive: 'bg-slate-600',
  error: 'bg-red-400',
}

export function StatusDot({
  status,
  animated = false,
}: {
  status: 'active' | 'inactive' | 'error'
  animated?: boolean
}) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${colors[status]} ${
        animated && status === 'active' ? 'animate-pulse' : ''
      }`}
    />
  )
}
