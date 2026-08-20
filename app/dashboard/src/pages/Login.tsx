import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'

import { useAuth } from '@/context/auth'

export default function Login() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (user) return <Navigate to="/" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password, totp || undefined)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-2xl border border-zinc-200 bg-white p-7 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <header className="space-y-2">
          <ShieldCheck className="size-8 text-emerald-600" aria-hidden />
          <h1 className="text-2xl font-semibold">ShieldAI console</h1>
          <p className="text-sm text-zinc-500">Sign in with an administrator or analyst account.</p>
        </header>
        {error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-200">{error}</p> : null}
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium">Username</span>
          <input className="w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2.5" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium">Password</span>
          <input className="w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2.5" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="font-medium">MFA code <span className="font-normal text-zinc-400">(if enrolled)</span></span>
          <input className="w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2.5" value={totp} onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" />
        </label>
        <button disabled={busy} className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
