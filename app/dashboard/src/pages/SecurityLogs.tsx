import { useEffect, useMemo, useState } from 'react'
import {
  Loader2,
  RefreshCw,
  Copy,
  Check,
  ShieldCheck,
  ShieldAlert,
  Link2Off,
} from 'lucide-react'

import {
  type AuditRow,
  type AuditVerifyResult,
  getAuditVerify,
  getLogs,
  getPromptDebug,
} from '@/api/client'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

function riskVariant(level: string): 'low' | 'medium' | 'high' {
  const l = level?.toLowerCase?.() ?? ''
  if (l.includes('high')) return 'high'
  if (l.includes('medium')) return 'medium'
  return 'low'
}

function semanticVariant(
  tier: string,
): 'low' | 'medium' | 'high' | 'critical' {
  const t = tier?.toLowerCase?.() ?? ''
  if (t === 'critical') return 'critical'
  if (t === 'high') return 'high'
  if (t === 'medium') return 'medium'
  return 'low'
}

function summarizeKinds(row: AuditRow) {
  const entries = Object.entries(row.pii_types ?? {})
  if (!entries.length) return '–'
  return entries
    .map(([k, v]) => `${k}:${v}`)
    .slice(0, 3)
    .join(', ')
}

function formatTime(iso: string) {
  if (iso.length >= 16) return iso.slice(0, 16).replace('T', ' ')
  return iso
}

/** Live tamper-evidence indicator: re-verifies the SHA-256 hash chain. */
function ChainStatus({ refreshSignal }: { refreshSignal: number }) {
  const [result, setResult] = useState<AuditVerifyResult | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let canceled = false
    void getAuditVerify()
      .then((r) => {
        if (!canceled) {
          setResult(r)
          setFailed(false)
        }
      })
      .catch(() => {
        if (!canceled) setFailed(true)
      })
    return () => {
      canceled = true
    }
  }, [refreshSignal])

  const base =
    'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium tracking-wide'

  if (failed) {
    return (
      <span
        className={`${base} border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400`}
        title="Could not reach /internal/audit/verify"
      >
        <ShieldAlert className="size-3.5" aria-hidden />
        Chain unknown
      </span>
    )
  }

  if (!result) {
    return (
      <span
        className={`${base} border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400`}
      >
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
        Verifying…
      </span>
    )
  }

  if (result.ok) {
    return (
      <span
        className={`${base} border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-100`}
        title={
          result.head_hash
            ? `Hash chain intact · head ${result.head_hash.slice(0, 12)}…`
            : 'Hash chain intact'
        }
      >
        <ShieldCheck className="size-3.5" aria-hidden />
        Chain intact · {result.rows_checked} rows
      </span>
    )
  }

  return (
    <span
      className={`${base} border-red-300 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-100`}
      title={result.reason ?? 'Audit chain verification failed'}
    >
      <Link2Off className="size-3.5" aria-hidden />
      Chain broken at #{result.broken_at_id}
    </span>
  )
}

export default function SecurityLogs() {
  const [events, setEvents] = useState<AuditRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [activeCorrId, setActiveCorrId] = useState<string | null>(null)
  const [debugLoading, setDebugLoading] = useState(false)
  const [debugError, setDebugError] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<{
    original_prompt: string
    scrubbed_prompt: string
  } | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [verifyTick, setVerifyTick] = useState(0)

  useEffect(() => {
    let canceled = false
    const load = () =>
      void getLogs(200)
        .then((r) => {
          if (!canceled) {
            setEvents(r.events)
            setError(null)
            setVerifyTick((t) => t + 1)
          }
        })
        .catch(() => {
          if (!canceled)
            setError('Cannot load logs — check API on :8888 and VITE_INTERNAL_TOKEN.')
        })
    load()
    const handle = window.setInterval(load, 9000)
    return () => {
      canceled = true
      window.clearInterval(handle)
    }
  }, [])

  const rows = useMemo(() => events, [events])

  async function openDebug(correlationId: string) {
    setActiveCorrId(correlationId)
    setDebugOpen(true)
    setDebugLoading(true)
    setDebugError(null)
    setSnapshot(null)
    try {
      const snap = await getPromptDebug(correlationId)
      setSnapshot(snap)
    } catch {
      setDebugError('No debug snapshot (expired or unknown id).')
    } finally {
      setDebugLoading(false)
    }
  }

  function closeDebug() {
    setDebugOpen(false)
    setSnapshot(null)
    setDebugError(null)
    setActiveCorrId(null)
  }

  async function copyCorr(id: string) {
    try {
      await navigator.clipboard.writeText(id)
      setCopiedId(id)
      window.setTimeout(() => setCopiedId((c) => (c === id ? null : c)), 1600)
    } catch {
      setCopiedId(null)
    }
  }

  return (
    <div className="flex w-full min-w-0 max-w-full flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-zinc-200/80 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Security logs
          </h1>
          <p className="mt-0.5 text-[13px] text-zinc-500 dark:text-zinc-400">
            Hash-chained audit · refreshes every 9s
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ChainStatus refreshSignal={verifyTick} />
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            <RefreshCw className="size-3.5" aria-hidden />
            Live
          </span>
        </div>
      </header>

      {error ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100">
          {error}
        </p>
      ) : null}

      <Card className="min-w-0 overflow-hidden border-zinc-200/90 p-0 dark:border-zinc-800">
        <CardHeader className="border-b border-zinc-100 px-4 py-3 dark:border-zinc-800 sm:px-5">
          <CardTitle className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            Recent events
          </CardTitle>
        </CardHeader>
        <CardContent className="min-w-0 p-0">
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="w-full min-w-[640px] table-auto border-collapse text-left text-sm">
              <thead className="border-b border-zinc-100 bg-zinc-50/90 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950/80 dark:text-zinc-500">
                <tr>
                  <th className="whitespace-nowrap px-3 py-2.5 sm:px-4">Time</th>
                  <th className="px-3 py-2.5 sm:px-4">Risk</th>
                  <th className="px-3 py-2.5 sm:px-4">Tier</th>
                  <th className="px-3 py-2.5 sm:px-4" title="Shadow mode">
                    Sh
                  </th>
                  <th className="min-w-[8rem] px-3 py-2.5 sm:px-4">PII</th>
                  <th className="px-3 py-2.5 text-right sm:px-4">#</th>
                  <th className="min-w-[6rem] px-3 py-2.5 sm:px-4">Threat</th>
                  <th className="px-3 py-2.5 sm:px-4" />
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td
                      className="px-4 py-10 text-center text-[13px] text-zinc-500 dark:text-zinc-400"
                      colSpan={8}
                    >
                      No events yet. Send a request to{' '}
                      <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">/v1/chat/completions</code>.
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr
                      key={`${row.time}-${row.correlation_id}-${row.audit_row_hash_suffix}`}
                      className="border-t border-zinc-100 dark:border-zinc-800"
                    >
                      <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-zinc-600 dark:text-zinc-400 sm:px-4">
                        {formatTime(row.time)}
                      </td>
                      <td className="px-3 py-2.5 sm:px-4">
                        <Badge variant={riskVariant(row.risk_level)}>
                          {row.risk_level}
                        </Badge>
                      </td>
                      <td className="px-3 py-2.5 sm:px-4">
                        <Badge variant={semanticVariant(row.semantic_risk ?? 'low')}>
                          {row.semantic_risk ?? 'low'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2.5 sm:px-4">
                        {row.shadow_mode ? (
                          <span className="text-amber-600 dark:text-amber-400">S</span>
                        ) : (
                          <span className="text-zinc-400">·</span>
                        )}
                      </td>
                      <td className="max-w-[10rem] truncate px-3 py-2.5 font-mono text-[11px] text-zinc-600 dark:text-zinc-400 sm:max-w-[14rem] sm:px-4">
                        {summarizeKinds(row)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-[12px] tabular-nums sm:px-4">
                        {row.scrub_entities}
                      </td>
                      <td className="max-w-[7rem] truncate px-3 py-2.5 text-[12px] text-zinc-600 dark:text-zinc-400 sm:max-w-[10rem] sm:px-4">
                        {row.threats?.length ? row.threats.join(', ') : '–'}
                      </td>
                      <td className="px-2 py-2.5 sm:px-3">
                        <div className="flex items-center gap-0.5">
                          <button
                            type="button"
                            className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                            title="Copy correlation ID"
                            aria-label="Copy correlation ID"
                            onClick={() => void copyCorr(row.correlation_id)}
                          >
                            {copiedId === row.correlation_id ? (
                              <Check className="size-3.5 text-emerald-600" aria-hidden />
                            ) : (
                              <Copy className="size-3.5" aria-hidden />
                            )}
                          </button>
                          <button
                            type="button"
                            className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                            title={row.correlation_id}
                            onClick={() => void openDebug(row.correlation_id)}
                          >
                            Debug
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {debugOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 backdrop-blur-sm sm:p-4">
          <div
            role="presentation"
            className="absolute inset-0"
            onClick={() => closeDebug()}
            aria-hidden
          />
          <div className="relative z-10 flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
            <header className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3 dark:border-zinc-800 sm:px-5">
              <p className="min-w-0 truncate font-mono text-[12px] text-zinc-600 dark:text-zinc-400">
                {activeCorrId}
              </p>
              <button
                type="button"
                className="shrink-0 rounded-lg px-3 py-1.5 text-[13px] font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900"
                onClick={() => closeDebug()}
              >
                Close
              </button>
            </header>

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4 sm:p-5">
              {debugLoading ? (
                <div className="flex items-center justify-center gap-2 py-16 text-[13px] text-zinc-500">
                  <Loader2 className="size-5 animate-spin" aria-hidden />
                  Loading…
                </div>
              ) : debugError ? (
                <p className="text-[13px] text-rose-600 dark:text-rose-400">{debugError}</p>
              ) : snapshot ? (
                <div className="grid min-h-0 flex-1 gap-3 sm:grid-cols-2">
                  <div className="flex min-h-[200px] flex-col overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <div className="border-b border-zinc-100 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                      Original
                    </div>
                    <pre className="max-h-[50vh] flex-1 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-zinc-800 dark:text-zinc-100">
                      {snapshot.original_prompt}
                    </pre>
                  </div>
                  <div className="flex min-h-[200px] flex-col overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
                    <div className="border-b border-zinc-100 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                      Scrubbed
                    </div>
                    <pre className="max-h-[50vh] flex-1 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-zinc-800 dark:text-zinc-100">
                      {snapshot.scrubbed_prompt}
                    </pre>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
