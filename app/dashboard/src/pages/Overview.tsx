import { useEffect, useState } from 'react'
import { Activity, Layers, RefreshCw, ShieldAlert } from 'lucide-react'

import { getMetrics } from '@/api/client'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Hint, Kicker } from '@/components/ui/hint'

const FLOW_STEPS = [
  {
    n: '1',
    title: 'Pre-flight scrub',
    body: 'ShieldAI analyzes prompts with Presidio and swaps detected spans for reversible placeholders before anything leaves your network boundary.',
  },
  {
    n: '2',
    title: 'Upstream model',
    body: 'The OpenAI-compatible body (with placeholders) goes to `POST /v1/chat/completions` on your configured base URL.',
  },
  {
    n: '3',
    title: 'Post-flight restore',
    body: 'The assistant reply is matched against the per-request vault and placeholders are swapped back — then the vault entry is discarded per policy/TTL.',
  },
] as const

export default function Overview() {
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof getMetrics>> | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let canceled = false
    const tick = () => {
      void getMetrics()
        .then((data) => {
          if (!canceled) {
            setMetrics(data)
            setError(null)
          }
        })
        .catch(() => {
          if (!canceled)
            setError(
              'Could not load `/internal/metrics`. Start the FastAPI app and align `VITE_INTERNAL_TOKEN` with `SHIELD_INTERNAL_TOKEN` (dashboard proxies to `vite.config.ts` target).',
            )
        })
    }
    tick()
    const handle = window.setInterval(tick, 5000)
    return () => {
      canceled = true
      window.clearInterval(handle)
    }
  }, [])

  const stats = metrics ?? {
    pii_intercepted_total: 0,
    tokens_scrubbed_total: 0,
    active_threats_blocked_total: 0,
    relay_success_total: 0,
  }

  const cards = [
    {
      title: 'PII intercepted',
      value: Intl.NumberFormat().format(stats.pii_intercepted_total),
      icon: Layers,
      hint:
        'Count of Presidio entity hits turned into placeholders on the way upstream. Not a cardinality of vault rows.',
    },
    {
      title: 'Tokens scrubbed (approx)',
      value: Intl.NumberFormat().format(stats.tokens_scrubbed_total),
      icon: Activity,
      hint:
        'Rough token-shaped counter derived from outbound payload sizing after scrubbing; use budgets on the proxy for enforcement.',
    },
    {
      title: 'Threats blocked',
      value: Intl.NumberFormat().format(stats.active_threats_blocked_total),
      icon: ShieldAlert,
      hint:
        'Injection heuristics that matched while `INJECTION_POLICY=block` on the API (blocked requests increment here).',
    },
  ]

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-xl space-y-2">
          <Kicker>Overview</Kicker>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Proxy health & flow
          </h1>
          <Hint>
            These counters are telemetry from the ShieldAI API process itself. They aggregate
            all clients using that instance — rotate keys upstream if you need per-tenant
            isolation beyond this MVP.
          </Hint>
          <Hint className="flex items-start gap-1.5 pt-1">
            <RefreshCw
              className="mt-0.5 size-3.5 shrink-0 opacity-70 dark:opacity-60"
              aria-hidden
            />
            Numbers refresh automatically about every{' '}
            <span className="font-medium tabular-nums text-zinc-700 dark:text-zinc-300">5s</span>{' '}
            while this page is open.
          </Hint>
        </div>
      </header>

      {error ? (
        <Card className="border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/35">
          <CardContent className="py-4 text-[13px] text-amber-950 dark:text-amber-100">
            {error}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">How a chat request is handled</CardTitle>
          <CardDescription>
            Read this once — it mirrors the middleware order inside the FastAPI handler.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {FLOW_STEPS.map((step) => (
            <div
              key={step.n}
              className="flex gap-4 border-b border-zinc-100 pb-5 last:border-b-0 last:pb-0 dark:border-zinc-800"
            >
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-zinc-50 text-xs font-semibold text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
                {step.n}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                  {step.title}
                </div>
                <Hint className="mt-1">{step.body}</Hint>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div>
        <div className="mb-4 flex flex-col gap-1">
          <Kicker>Counters</Kicker>
          <h2 className="text-[15px] font-semibold text-zinc-800 dark:text-zinc-100">
            What each number means
          </h2>
          <Hint>Think of figures as directional telemetry — not invoicing-grade usage.</Hint>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {cards.map((c) => (
            <Card key={c.title}>
              <CardHeader className="border-b-0 pb-3">
                <CardTitle className="flex items-center gap-2 text-[14px] font-medium text-zinc-800 dark:text-zinc-100">
                  <c.icon
                    className="size-4 text-zinc-400 dark:text-zinc-500"
                    strokeWidth={1.75}
                  />
                  {c.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="font-mono text-3xl tracking-tight text-zinc-900 dark:text-zinc-50">
                  {c.value}
                </div>
                <Hint className="mt-3 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                  {c.hint}
                </Hint>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Relay completions</CardTitle>
          <CardDescription>
            Successful round-trips after deanonymizing the assistant message in the proxy
            response path.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-4xl tracking-tight text-zinc-900 dark:text-zinc-50">
            {Intl.NumberFormat().format(stats.relay_success_total)}
          </div>
          <Hint className="mt-3">
            Counts completed relays through ShieldAI&apos;s OpenAI-compatible chat endpoint
            (after deanonymizing the assistant message). For streaming upstream responses, content
            is buffered first, then echoed as a synthesized SSE transcript.
          </Hint>
        </CardContent>
      </Card>
    </div>
  )
}
