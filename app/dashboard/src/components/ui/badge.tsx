import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Muted semantic chips — minimalist, mostly outline. */
const variants: Record<string, string> = {
  low:
    'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-600 dark:bg-zinc-800/80 dark:text-zinc-300',
  medium:
    'border-amber-200/90 bg-amber-50 text-amber-900 dark:border-amber-800/70 dark:bg-amber-950/50 dark:text-amber-100',
  high:
    'border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-100',
  critical:
    'border-fuchsia-950/65 bg-fuchsia-950 text-fuchsia-50 dark:border-fuchsia-400/55 dark:bg-fuchsia-950/90 dark:text-fuchsia-100',
}

export function Badge({
  variant = 'low',
  children,
}: {
  variant?: keyof typeof variants
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium tabular-nums tracking-wide',
        variants[variant] ?? variants.low,
      )}
    >
      {children}
    </span>
  )
}
