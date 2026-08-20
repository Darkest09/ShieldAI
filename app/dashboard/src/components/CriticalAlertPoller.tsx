import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { getAlerts } from '@/api/client'

/**
 * Polls `/internal/alerts` and surfaces cryptographic / semantic escalations immediately.
 */
export function CriticalAlertPoller() {
  const sinceRef = useRef(Date.now() / 1000)
  const seenIds = useRef(new Set<string>())

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const { alerts } = await getAlerts(sinceRef.current)
        if (!alerts?.length || cancelled) return
        sinceRef.current = Math.max(...alerts.map((a) => a.ts))
        for (const alert of alerts) {
          if (seenIds.current.has(alert.id)) continue
          seenIds.current.add(alert.id)
          toast.error(`${alert.headline}`, {
            description: `${alert.detail} · corr ${alert.correlation_id}`,
            duration: 10_000,
          })
        }
      } catch {
        /* dashboards run without the API often — swallow noise */
      }
    }
    void poll()
    const handle = window.setInterval(() => void poll(), 3500)
    return () => {
      cancelled = true
      window.clearInterval(handle)
    }
  }, [])

  return null
}
