import * as SwitchPrimitives from '@radix-ui/react-switch'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export function Switch({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>) {
  return (
    <SwitchPrimitives.Root
      className={cn(
        'peer inline-flex h-[22px] w-[42px] shrink-0 cursor-pointer items-center rounded-full border border-zinc-300 bg-zinc-100 px-0.5 outline-none transition-colors',
        'focus-visible:ring-2 focus-visible:ring-zinc-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-zinc-600 dark:bg-zinc-800 dark:focus-visible:ring-zinc-500 dark:focus-visible:ring-offset-zinc-900',
        'data-[state=checked]:border-zinc-800 data-[state=checked]:bg-zinc-800 dark:data-[state=checked]:border-zinc-200 dark:data-[state=checked]:bg-zinc-200',
        className,
      )}
      {...props}
    >
      <SwitchPrimitives.Thumb
        className={cn(
          'pointer-events-none block h-[18px] w-[18px] rounded-full bg-white shadow-sm transition-transform',
          'data-[state=checked]:translate-x-[18px]',
          'dark:bg-zinc-100 dark:data-[state=checked]:bg-zinc-900',
        )}
      />
    </SwitchPrimitives.Root>
  )
}
