export const STATUS_COLORS: Record<string, string> = {
  // Project status
  new: 'bg-slate-500/20 text-slate-300',
  planning: 'bg-sky-500/20 text-sky-300',
  executing: 'bg-emerald-500/20 text-emerald-300',
  paused: 'bg-amber-500/20 text-amber-300',
  completed: 'bg-sky-500/20 text-sky-300',
  failed: 'bg-red-500/20 text-red-300',

  // Task status
  backlog: 'bg-slate-500/20 text-slate-300',
  pending: 'bg-slate-500/20 text-slate-300',
  in_progress: 'bg-amber-500/20 text-amber-300',
  review_ready: 'bg-violet-500/20 text-violet-300',
  rejected: 'bg-red-500/20 text-red-300',
  done: 'bg-emerald-500/20 text-emerald-300',
  blocked: 'bg-orange-500/20 text-orange-300',

  // Epic / Milestone status
  open: 'bg-slate-500/20 text-slate-300',
  cancelled: 'bg-red-500/20 text-red-300',
}

export const PRIORITY_COLORS: Record<number, string> = {
  1: 'text-red-400',
  2: 'text-amber-400',
  3: 'text-sky-400',
  4: 'text-slate-300',
  5: 'text-slate-500',
}
