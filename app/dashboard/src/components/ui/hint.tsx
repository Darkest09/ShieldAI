import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Short supporting copy for sections, metrics, or controls. */
export function Hint({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <p
      className={cn(
        'text-[13px] leading-relaxed text-zinc-500 dark:text-zinc-400',
        className,
      )}
    >
      {children}
    </p>
  )
}

/** Small uppercase label for grouping. */
export function Kicker({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400 dark:text-zinc-500">
      {children}
    </p>
  )
}
