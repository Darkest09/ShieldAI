import { useEffect, useMemo, useState } from 'react'

import { getConfig, patchConfig } from '@/api/client'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Hint, Kicker } from '@/components/ui/hint'
import { Switch } from '@/components/ui/switch'
import { describeCustomRecognizer } from '@/lib/config-copy'

type Cfg = Awaited<ReturnType<typeof getConfig>>

function ToggleCard({
  id,
  title,
  subtitle,
  description,
  checked,
  disabled,
  onCheckedChange,
}: {
  id: string
  title: string
  subtitle: string
  description: string
  checked: boolean
  disabled?: boolean
  onCheckedChange: (v: boolean) => void
}) {
  const stateLabel = checked ? 'On' : 'Off'

  return (
    <div className="flex flex-col gap-3 border-b border-zinc-100 py-5 last:border-b-0 last:pb-2 dark:border-zinc-800 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{title}</p>
          <p className="text-[13px] text-zinc-500 dark:text-zinc-400">{subtitle}</p>
        </div>
        <Hint>{description}</Hint>
      </div>
      <div className="flex shrink-0 items-center gap-3 sm:flex-col sm:items-end">
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-400 dark:text-zinc-500">
          {stateLabel}
        </span>
        <Switch
          id={id}
          checked={checked}
          disabled={disabled}
          onCheckedChange={onCheckedChange}
          aria-label={`${title}: ${stateLabel}. ${subtitle}`}
        />
      </div>
    </div>
  )
}

export default function ConfigPanel() {
  const [cfg, setCfg] = useState<Cfg | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getConfig()
      .then((c) => {
        setCfg(c)
        setError(null)
      })
      .catch(() => setError('Failed to load `/internal/config` — check connectivity and tokens.'))
  }, [])

  const customKeys = useMemo(
    () => Object.keys(cfg?.custom_recognizers ?? {}),
    [cfg],
  )

  async function update(partial: Record<string, unknown>) {
    setStatus('Saving…')
    try {
      const next = await patchConfig(partial)
      setCfg(next as Cfg)
      setStatus('Saved')
      window.setTimeout(() => setStatus(null), 1400)
    } catch {
      setStatus(null)
      setError('PATCH failed — review proxy logs or internal token mismatches.')
    }
  }

  if (!cfg) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-200 px-5 py-8 text-[13px] text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        {error ?? 'Loading recognizer toggles…'}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl space-y-2">
          <Kicker>Recognizers</Kicker>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Detection policy
          </h1>
          <Hint>
            These switches PATCH `/internal/config` on the ShieldAI API, which persists JSON on disk
            and rebuilds Presidio&apos;s analyzer registry — no daemon restart needed.
          </Hint>
          <Hint>
            <span className="font-medium text-zinc-700 dark:text-zinc-300">Tip:</span> turning a
            recognizer Off stops new detections immediately; queued sessions still honor whatever
            mappings already exist.
          </Hint>
        </div>
        {status ? (
          <span className="inline-flex items-center rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/45 dark:text-emerald-100">
            {status}
          </span>
        ) : null}
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
          <CardTitle className="text-base">Presidio built-ins</CardTitle>
          <CardDescription>
            Broadly useful recognizers bundled with AnalyzerEngine defaults — disable when you want
            narrower coverage during evaluations.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <ToggleCard
            id="toggle-shadow-mode"
            title="Shadow observability mode"
            subtitle="Audits semantic hits without rewriting upstream payloads"
            checked={cfg.shadow_mode ?? false}
            description="When enabled, ShieldAI logs Presidio findings and emits critical alerts exactly as before, yet the verbatim text still crosses to the frontier model — use only inside a trusted evaluation plane."
            onCheckedChange={(v) => void update({ shadow_mode: v })}
          />

          <ToggleCard
            id="toggle-cc"
            title="Credit cards"
            subtitle="Detects CARD_NUMBER / CREDIT_CARD style hits"
            checked={cfg.credit_card_scanning}
            description="Keeps PAN-like sequences from leaking into frontier models during training-ish workloads. Turning this off skips credit-card-aware recognizers in the default registry rebuild."
            onCheckedChange={(v) => void update({ credit_card_scanning: v })}
          />

          <ToggleCard
            id="toggle-email"
            title="Email addresses"
            subtitle="Signals like user@company.tld inside prompts"
            checked={cfg.email_scanning}
            description="Preserves mailbox identifiers when you rely on placeholders for reversible scrubbing downstream. Useful for support bots that ingest customer mail threads."
            onCheckedChange={(v) => void update({ email_scanning: v })}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Custom ShieldAI recognizers</CardTitle>
          <CardDescription>
            Regex-first patterns shipped with ShieldAI — complementary to NLP-heavy built-ins.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1 pt-4">
          {customKeys.map((key) => (
            <ToggleCard
              key={key}
              id={`toggle-${key}`}
              title={key.replaceAll('_', ' ')}
              subtitle="ShieldAI-maintained regex bundle"
              checked={cfg.custom_recognizers[key] ?? true}
              description={describeCustomRecognizer(key)}
              onCheckedChange={(v) => void update({ custom_recognizers: { [key]: v } })}
            />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
