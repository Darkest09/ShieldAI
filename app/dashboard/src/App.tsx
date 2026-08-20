import { NavLink, Outlet } from 'react-router-dom'

import { ThemeToggle } from '@/components/ThemeToggle'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/auth'

type NavItem = {
  to: string
  end?: boolean
  label: string
  description: string
}

const NAV: NavItem[] = [
  {
    to: '/',
    end: true,
    label: 'Overview',
    description: 'Traffic totals and proxy flow.',
  },
  {
    to: '/logs',
    label: 'Logs',
    description: 'Audit rows — counts and entity types only.',
  },
  {
    to: '/governance',
    label: 'Governance',
    description: 'Compliance coverage + human approval queue.',
  },
  {
    to: '/config',
    label: 'Config',
    description: 'Recognizer toggles and shadow mode.',
  },
  { to: '/system', label: 'System', description: 'Readiness and security controls.' },
  { to: '/users', label: 'Users', description: 'Accounts, roles, and MFA.' },
]

function sidebarLinkClass(isActive: boolean) {
  return cn(
    'block rounded-lg border px-3 py-2 transition-colors',
    '[&:focus-visible]:outline-none [&:focus-visible]:ring-2 [&:focus-visible]:ring-zinc-400 [&:focus-visible]:ring-offset-2',
    '[&:focus-visible]:dark:ring-zinc-500 [&:focus-visible]:dark:ring-offset-zinc-950',
    isActive
      ? 'border-zinc-800 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900'
      : 'border-transparent text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-100',
  )
}

export default function App() {
  const { user, logout } = useAuth()
  const nav = user?.role === 'admin' ? NAV : NAV.filter((item) => !['/config', '/users'].includes(item.to))
  return (
    <div className="min-h-full">
      <div className="mx-auto flex w-full max-w-6xl min-w-0 gap-6 px-4 py-6 sm:px-6 lg:gap-8 lg:py-8">
        <aside className="hidden w-44 shrink-0 flex-col gap-6 lg:flex">
          <header className="space-y-3">
            <div className="text-[15px] font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              ShieldAI
            </div>
            <ThemeToggle />
            <p className="text-[11px] leading-snug text-zinc-500 dark:text-zinc-500">
              Vite → port <span className="font-mono text-zinc-600 dark:text-zinc-400">8888</span>.
              Token matches <span className="font-mono">SHIELD_INTERNAL_TOKEN</span>.
            </p>
          </header>
          <button onClick={logout} className="text-left text-xs font-medium text-red-600">Sign out {user?.subject}</button>
          <nav className="flex flex-col gap-1" aria-label="Primary">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={Boolean(item.end)}
                title={item.description}
                className={({ isActive }) => sidebarLinkClass(isActive)}
              >
                <span className="text-sm font-medium">{item.label}</span>
                <span data-slot="desc" className="sr-only">
                  {item.description}
                </span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="min-h-[70vh] min-w-0 flex-1 rounded-2xl border border-zinc-200/90 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-6">
          <div className="mb-6 flex flex-col gap-3 border-b border-zinc-100 pb-6 dark:border-zinc-800 lg:hidden">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[13px] font-semibold text-zinc-700 dark:text-zinc-300">
                ShieldAI menu
              </div>
              <ThemeToggle />
            </div>
            <div className="flex gap-2">
              {nav.map((item) => (
                <NavLink
                  key={`m-${item.to}`}
                  to={item.to}
                  end={Boolean(item.end)}
                  title={`${item.label}: ${item.description}`}
                  className={({ isActive }) =>
                    cn(
                      'flex-1 rounded-lg border px-2 py-2 text-center transition-colors',
                      '[&:focus-visible]:outline-none [&:focus-visible]:ring-2 [&:focus-visible]:ring-zinc-400',
                      '[&:focus-visible]:dark:ring-zinc-500',
                      isActive
                        ? 'border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900'
                        : 'border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800',
                    )
                  }
                >
                  <span className="text-[13px] font-medium">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>

          <Outlet />
        </main>
      </div>
    </div>
  )
}
