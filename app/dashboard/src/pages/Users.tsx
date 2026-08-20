import { useEffect, useState, type FormEvent } from 'react'
import { UserPlus } from 'lucide-react'

import { createUser, getUsers, updateUser, type ManagedUser } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function Users() {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('teller')

  const load = () => void getUsers().then((r) => { setUsers(r.users); setError(null) }).catch((e: Error) => setError(e.message))
  useEffect(load, [])

  async function add(event: FormEvent) {
    event.preventDefault()
    try {
      await createUser(username, password, role)
      setUsername(''); setPassword(''); load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create user') }
  }

  async function change(user: ManagedUser, patch: Record<string, unknown>) {
    try { await updateUser(user.username, patch); load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed') }
  }

  return <div className="space-y-8">
    <header><p className="text-xs font-semibold uppercase tracking-widest text-emerald-600">Identity</p><h1 className="mt-2 text-2xl font-semibold">User management</h1><p className="mt-2 text-sm text-zinc-500">Create accounts, assign least-privilege roles, disable access, and reset MFA.</p></header>
    {error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-200">{error}</p> : null}
    <Card><CardHeader><CardTitle className="text-base">Add user</CardTitle></CardHeader><CardContent>
      <form onSubmit={add} className="grid gap-3 sm:grid-cols-4">
        <input className="rounded-lg border bg-transparent px-3 py-2 text-sm" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} />
        <input className="rounded-lg border bg-transparent px-3 py-2 text-sm" type="password" placeholder="Password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        <select className="rounded-lg border bg-transparent px-3 py-2 text-sm" value={role} onChange={(e) => setRole(e.target.value)}>{['teller','officer','analyst','admin'].map((r) => <option key={r}>{r}</option>)}</select>
        <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"><UserPlus className="size-4" /> Create</button>
      </form>
    </CardContent></Card>
    <Card><CardContent className="p-0"><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500 dark:bg-zinc-950"><tr><th className="px-4 py-3">User</th><th>Role</th><th>MFA</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map((u) => <tr key={u.username} className="border-t dark:border-zinc-800"><td className="px-4 py-3 font-medium">{u.username}</td><td><select className="rounded border bg-transparent px-2 py-1" value={u.role} onChange={(e) => void change(u, { role: e.target.value })}>{['teller','officer','analyst','admin'].map((r) => <option key={r}>{r}</option>)}</select></td><td>{u.mfa_enrolled ? 'Enrolled' : 'Not enrolled'}</td><td>{u.disabled ? 'Disabled' : 'Active'}</td><td className="space-x-2"><button className="rounded border px-2 py-1" onClick={() => void change(u, { disabled: !u.disabled })}>{u.disabled ? 'Enable' : 'Disable'}</button>{u.mfa_enrolled ? <button className="rounded border px-2 py-1" onClick={() => void change(u, { reset_mfa: true })}>Reset MFA</button> : null}</td></tr>)}</tbody></table></div></CardContent></Card>
  </div>
}
