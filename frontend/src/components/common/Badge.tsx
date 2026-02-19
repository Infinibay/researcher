import type { ReactNode } from 'react'

const variants: Record<string, string> = {
  success: 'bg-emerald-500/20 text-emerald-300',
  warning: 'bg-amber-500/20 text-amber-300',
  error: 'bg-red-500/20 text-red-300',
  info: 'bg-sky-500/20 text-sky-300',
  neutral: 'bg-slate-500/20 text-slate-300',
  violet: 'bg-violet-500/20 text-violet-300',
}

export function Badge({
  variant = 'neutral',
  children,
}: {
  variant?: keyof typeof variants | string
  children: ReactNode
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${variants[variant] ?? variants.neutral}`}
    >
      {children}
    </span>
  )
}
