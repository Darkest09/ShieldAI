/** Human-readable lines for dashboard copy (no secrets). */
export const CUSTOM_RECOGNIZER_HELP: Record<string, string> = {
  NP_CITIZENSHIP_NUMBER:
    'Detects citizenship-style identifiers common in Nepal (pattern-based; tune for your issuer format).',
  NP_MOBILE_NUMBER:
    'Nepal handset numbers (e.g. prefixes used by Ncell/NTC and similar carriers).',
  AWS_ACCESS_KEY_ID:
    '20-character AWS access key IDs beginning with AKIA.',
  AWS_SECRET_ACCESS_KEY:
    'Heuristic secret-like blobs often paired with AWS keys (may false-positive).',
  STRIPE_API_KEY:
    'Live Stripe secret, restricted, or publishable prefixes (sk_live_, rk_live_, pk_live_).',
}

export function describeCustomRecognizer(entity: string): string {
  return (
    CUSTOM_RECOGNIZER_HELP[entity] ??
    'Custom pattern bundled with ShieldAI’s Presidio registry.'
  )
}
