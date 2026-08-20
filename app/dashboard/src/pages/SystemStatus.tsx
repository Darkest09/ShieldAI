import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

import { getSystemStatus, type SystemStatus as Status } from '@/api/client'
import { Card, CardContent } from '@/components/ui/card'

export default function SystemStatus() {
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { void getSystemStatus().then(setStatus).catch((e: Error) => setError(e.message)) }, [])
  const rows = status ? [
    ['Gateway ready', status.ready], ['Audit chain intact', status.audit_chain_ok], ['Upstream configured', status.upstream_configured],
    ['Zero-Trust enabled', status.zero_trust_enabled], ['MFA enabled', status.mfa_enabled], ['Vault encrypted', status.vault_encryption_enabled],
    ['SIEM configured', status.siem_configured], ['Sensitive prompt debugging', status.prompt_debug_enabled],
  ] as const : []
  return <div className="space-y-8"><header><p className="text-xs font-semibold uppercase tracking-widest text-emerald-600">Operations</p><h1 className="mt-2 text-2xl font-semibold">System status</h1><p className="mt-2 text-sm text-zinc-500">Deployment readiness and security-control state.</p></header>
    {error ? <p className="text-red-600">{error}</p> : null}
    {status ? <><Card><CardContent className="grid gap-3 pt-6 sm:grid-cols-2">{rows.map(([label, on]) => <div key={label} className="flex items-center justify-between rounded-lg border p-3 dark:border-zinc-800"><span className="text-sm">{label}</span>{on ? <CheckCircle2 className="size-5 text-emerald-600" /> : <XCircle className="size-5 text-zinc-400" />}</div>)}</CardContent></Card><p className="text-sm text-zinc-500">NLP engine requested: <b>{status.nlp_engine_requested}</b> · Upstream: <b>{status.upstream_host}</b></p></> : <p>Loading…</p>}
  </div>
}
