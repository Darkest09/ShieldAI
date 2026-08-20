import { useEffect, useState } from 'react'
import { ShieldCheck, Lock, KeyRound, Check, X } from 'lucide-react'

import {
  type ApprovalTicket,
  type ComplianceReport,
  decideApproval,
  getApprovals,
  getComplianceReport,
} from '@/api/client'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Hint, Kicker } from '@/components/ui/hint'
import { useAuth } from '@/context/auth'

function StatusPill({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium ' +
        (on
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-100'
          : 'border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400')
      }
    >
      {on ? <Lock className="size-3.5" aria-hidden /> : <KeyRound className="size-3.5" aria-hidden />}
      {label}: {on ? 'On' : 'Off'}
    </span>
  )
}

export default function Governance() {
  const { user } = useAuth()
  const [report, setReport] = useState<ComplianceReport | null>(null)
  const [approvals, setApprovals] = useState<ApprovalTicket[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    void getComplianceReport()
      .then((r) => {
        setReport(r)
        setError(null)
      })
      .catch(() =>
        setError('Could not load `/internal/compliance/report` — check API + VITE_INTERNAL_TOKEN.'),
      )
    void getApprovals(true)
      .then((r) => setApprovals(r.approvals))
      .catch(() => {})
  }

  useEffect(() => {
    load()
    const h = window.setInterval(load, 6000)
    return () => window.clearInterval(h)
  }, [])

  async function decide(id: string, approve: boolean) {
    try {
      await decideApproval(id, approve)
      setApprovals((a) => a.filter((t) => t.id !== id))
    } catch {
      setError('Decision failed — check the API connection.')
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <header className="space-y-2">
        <Kicker>Compliance & Governance</Kicker>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Regulatory coverage & approvals
        </h1>
        <Hint>
          Maps gateway capabilities to NRB Cyber Resilience, Nepal&apos;s Individual Privacy Act
          2018, ISO/IEC 27001, NIST SP 800-207, and OWASP-LLM — and lets an admin clear prompts
          held for human review.
        </Hint>
      </header>

      {error ? (
        <Card className="border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/35">
          <CardContent className="py-4 text-[13px] text-amber-950 dark:text-amber-100">
            {error}
          </CardContent>
        </Card>
      ) : null}

      {report ? (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-[13px] font-medium text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100">
              <ShieldCheck className="size-4 text-emerald-600" aria-hidden />
              {report.summary.controls_implemented}/{report.summary.controls_total} controls (
              {report.summary.coverage_pct}% )
            </span>
            <StatusPill on={report.zero_trust_enabled} label="Zero-Trust" />
            <StatusPill on={report.vault_encryption_enabled} label="Vault AES-256" />
            <span className="text-[12px] text-zinc-500 dark:text-zinc-400">
              {report.summary.active_policy_rules} active policy rules
            </span>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Human approval queue</CardTitle>
              <CardDescription>
                Prompts held by the governance workflow (Zero-Trust mode). Approve to release a
                re-submission with the ticket id.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {approvals.length === 0 ? (
                <p className="text-[13px] text-zinc-500 dark:text-zinc-400">No prompts awaiting approval.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {approvals.map((t) => (
                    <div
                      key={t.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2.5 dark:border-zinc-800"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-[13px] font-medium text-zinc-900 dark:text-zinc-50">
                          <span className="font-mono text-[11px]">{t.id}</span>
                          <Badge variant="high">risk {t.risk_score}</Badge>
                          <span className="text-zinc-500">{t.role}</span>
                        </div>
                        <p className="mt-0.5 text-[12px] text-zinc-600 dark:text-zinc-400">{t.reason}</p>
                        <p className="text-[11px] text-zinc-400">
                          basis: {t.regulatory_basis.join(', ') || '–'}
                        </p>
                      </div>
                      {user?.role === 'admin' ? <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => void decide(t.id, true)}
                          className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-[12px] font-medium text-emerald-800 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
                        >
                          <Check className="size-3.5" aria-hidden /> Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => void decide(t.id, false)}
                          className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-3 py-1.5 text-[12px] font-medium text-red-800 hover:bg-red-100 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-100"
                        >
                          <X className="size-3.5" aria-hidden /> Deny
                        </button>
                      </div> : <span className="text-xs text-zinc-500">Admin decision required</span>}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {Object.entries(report.by_regime).map(([regime, bucket]) => (
            <Card key={regime}>
              <CardHeader>
                <CardTitle className="text-base">{regime}</CardTitle>
                <CardDescription>
                  {bucket.implemented}/{bucket.total} controls implemented
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="w-full overflow-x-auto">
                  <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                    <thead className="border-b border-zinc-100 bg-zinc-50/80 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950/70">
                      <tr>
                        <th className="px-4 py-2.5">Control</th>
                        <th className="px-4 py-2.5">Requirement</th>
                        <th className="px-4 py-2.5">Gateway capability</th>
                        <th className="px-4 py-2.5">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bucket.controls.map((c) => (
                        <tr key={c.id} className="border-t border-zinc-100 dark:border-zinc-800">
                          <td className="px-4 py-2.5 font-mono text-[11px] text-zinc-600 dark:text-zinc-400">
                            {c.id}
                          </td>
                          <td className="px-4 py-2.5 text-[12px] text-zinc-700 dark:text-zinc-300">
                            {c.requirement}
                          </td>
                          <td className="px-4 py-2.5 text-[12px] text-zinc-600 dark:text-zinc-400">
                            {c.capability}
                          </td>
                          <td className="px-4 py-2.5">
                            <Badge variant={c.status === 'implemented' ? 'low' : 'medium'}>
                              {c.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          ))}
        </>
      ) : (
        <p className="text-[13px] text-zinc-500 dark:text-zinc-400">Loading compliance report…</p>
      )}
    </div>
  )
}
