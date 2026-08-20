function internalHeaders(includeJson = false): HeadersInit {
  const token = sessionStorage.getItem('shieldai_access_token')
  const h: Record<string, string> = {}
  if (token) h.Authorization = `Bearer ${token}`
  if (includeJson) {
    h['Content-Type'] = 'application/json'
  }
  return h
}

async function apiError(res: Response) {
  let detail = `Request failed (${res.status})`
  try {
    const body = await res.json() as { detail?: string }
    if (body.detail) detail = body.detail
  } catch { /* non-JSON response */ }
  if (res.status === 401) sessionStorage.removeItem('shieldai_access_token')
  return new Error(detail)
}

export type SessionUser = { subject: string; role: string; expires_at: number }

export async function login(username: string, password: string, totpCode?: string) {
  const res = await fetch('/v1/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, totp_code: totpCode }),
  })
  if (!res.ok) throw await apiError(res)
  return res.json() as Promise<{ access_token: string; role: string; expires_in: number }>
}

export async function getMe() {
  const res = await fetch('/v1/auth/me', { headers: internalHeaders(false) })
  if (!res.ok) throw await apiError(res)
  return res.json() as Promise<SessionUser>
}

export async function getMetrics() {
  const res = await fetch('/internal/metrics', { headers: internalHeaders(false) })
  if (!res.ok) throw new Error(`metrics ${res.status}`)
  return res.json() as Promise<{
    pii_intercepted_total: number
    tokens_scrubbed_total: number
    active_threats_blocked_total: number
    relay_success_total: number
  }>
}

export async function getLogs(limit = 100) {
  const res = await fetch(`/internal/logs?limit=${limit}`, {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`logs ${res.status}`)
  return res.json() as Promise<{ events: AuditRow[] }>
}

export type AuditRow = {
  time: string
  correlation_id: string
  risk_level: string
  semantic_risk: string
  shadow_mode: boolean
  pii_types: Record<string, number>
  scrub_entities: number
  threats: string[]
  audit_row_hash_suffix: string
}

export type CriticalAlert = {
  id: string
  ts: number
  severity: string
  headline: string
  detail: string
  correlation_id: string
  source: string
}

export async function getAlerts(since = 0) {
  const res = await fetch(`/internal/alerts?since=${since}`, {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`alerts ${res.status}`)
  return res.json() as Promise<{ alerts: CriticalAlert[] }>
}

export async function getPromptDebug(correlationId: string) {
  const res = await fetch(`/internal/debug/prompt/${encodeURIComponent(correlationId)}`, {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`debug prompt ${res.status}`)
  return res.json() as Promise<{ original_prompt: string; scrubbed_prompt: string }>
}

export type AuditVerifyResult = {
  ok: boolean
  rows_checked: number
  broken_at_id: number | null
  reason: string | null
  head_hash?: string
}

export async function getAuditVerify() {
  const res = await fetch('/internal/audit/verify', {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`audit verify ${res.status}`)
  return res.json() as Promise<AuditVerifyResult>
}

export type ComplianceControl = {
  id: string
  regime: string
  requirement: string
  capability: string
  status: string
}

export type ComplianceReport = {
  summary: {
    controls_total: number
    controls_implemented: number
    coverage_pct: number
    active_policy_rules: number
  }
  by_regime: Record<
    string,
    { controls: ComplianceControl[]; implemented: number; total: number }
  >
  vault_encryption_enabled: boolean
  zero_trust_enabled: boolean
}

export async function getComplianceReport() {
  const res = await fetch('/internal/compliance/report', {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`compliance ${res.status}`)
  return res.json() as Promise<ComplianceReport>
}

export type ApprovalTicket = {
  id: string
  correlation_id: string
  subject: string
  role: string
  reason: string
  risk_score: number
  matched_rules: string[]
  regulatory_basis: string[]
  status: string
  created_at: number
}

export async function getApprovals(pendingOnly = true) {
  const res = await fetch(`/internal/approvals?pending_only=${pendingOnly}`, {
    headers: internalHeaders(false),
  })
  if (!res.ok) throw new Error(`approvals ${res.status}`)
  return res.json() as Promise<{ approvals: ApprovalTicket[] }>
}

export async function decideApproval(ticketId: string, approve: boolean) {
  const res = await fetch(`/internal/approvals/${encodeURIComponent(ticketId)}/decide`, {
    method: 'POST',
    headers: internalHeaders(true),
    body: JSON.stringify({ approve }),
  })
  if (!res.ok) throw new Error(`decide ${res.status}`)
  return res.json() as Promise<ApprovalTicket>
}

export type ManagedUser = { username: string; role: string; disabled: boolean; mfa_enrolled: boolean }

export async function getUsers() {
  const res = await fetch('/internal/users', { headers: internalHeaders(false) })
  if (!res.ok) throw await apiError(res)
  return res.json() as Promise<{ users: ManagedUser[] }>
}

export async function createUser(username: string, password: string, role: string) {
  const res = await fetch('/internal/users', {
    method: 'POST', headers: internalHeaders(true), body: JSON.stringify({ username, password, role }),
  })
  if (!res.ok) throw await apiError(res)
  return res.json()
}

export async function updateUser(username: string, patch: Record<string, unknown>) {
  const res = await fetch(`/internal/users/${encodeURIComponent(username)}`, {
    method: 'PATCH', headers: internalHeaders(true), body: JSON.stringify(patch),
  })
  if (!res.ok) throw await apiError(res)
  return res.json() as Promise<ManagedUser>
}

export type SystemStatus = {
  service: string; ready: boolean; nlp_engine_requested: string; upstream_configured: boolean;
  upstream_host: string; audit_chain_ok: boolean; zero_trust_enabled: boolean; mfa_enabled: boolean;
  vault_encryption_enabled: boolean; prompt_debug_enabled: boolean; siem_configured: boolean
}

export async function getSystemStatus() {
  const res = await fetch('/internal/system/status', { headers: internalHeaders(false) })
  if (!res.ok) throw await apiError(res)
  return res.json() as Promise<SystemStatus>
}

export async function getConfig() {
  const res = await fetch('/internal/config', { headers: internalHeaders(false) })
  if (!res.ok) throw new Error(`config ${res.status}`)
  return res.json() as Promise<{
    shadow_mode?: boolean
    credit_card_scanning: boolean
    email_scanning: boolean
    custom_recognizers: Record<string, boolean>
  }>
}

export async function patchConfig(patch: Record<string, unknown>) {
  const res = await fetch('/internal/config', {
    method: 'PATCH',
    headers: internalHeaders(true),
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`config patch ${res.status}`)
  return res.json() as Promise<Record<string, unknown>>
}
