import { Laptop, Moon, Sun } from 'lucide-react'

import { cn } from '@/lib/utils'
import { type ThemeMode, useTheme } from '@/context/theme'

const OPTIONS: { id: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { id: 'light', label: 'Light', Icon: Sun },
  { id: 'dark', label: 'Dark', Icon: Moon },
  { id: 'system', label: 'System', Icon: Laptop },
]

/** Three-way toggle: forced light/dark vs. follow OS preference. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme, resolvedDark } = useTheme()

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-400 dark:text-zinc-500">
        Appearance
      </span>
      <div
        className="inline-flex rounded-xl border border-zinc-200 bg-zinc-50/80 p-0.5 dark:border-zinc-700 dark:bg-zinc-900/80"
        role="radiogroup"
        aria-label="Color theme"
      >
        {OPTIONS.map(({ id, label, Icon }) => {
          const active = theme === id
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={active}
              title={`${label} theme`}
              className={cn(
                'inline-flex flex-1 items-center justify-center gap-1 rounded-lg px-2 py-2 text-[13px] font-medium transition-colors',
                '[&:focus-visible]:outline-none [&:focus-visible]:ring-2 [&:focus-visible]:ring-zinc-400 [&:focus-visible]:ring-offset-2',
                '[&:focus-visible]:dark:ring-zinc-500 [&:focus-visible]:dark:ring-offset-zinc-950',
                active
                  ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
                  : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200',
              )}
              onClick={() => setTheme(id)}
            >
              <Icon className="size-4 opacity-85" aria-hidden />
              <span className="hidden min-[340px]:inline">{label}</span>
            </button>
          )
        })}
      </div>
      {theme === 'system' ? (
        <p className="text-[11px] leading-snug text-zinc-500 dark:text-zinc-400">
          Follows OS: currently {resolvedDark ? 'dark' : 'light'}.
        </p>
      ) : null}
    </div>
  )
}
