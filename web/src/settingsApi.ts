// Typed client for the Settings endpoints (docs/ui_redesign.md "Settings"). Keys are only ever SENT (POST /keys); no endpoint returns one.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

export const ROLES = ['default', 'embed', 'embed_large', 'rerank', 'parse', 'chat'] as const
export const MODEL_ROLES = ['fast', 'reason', 'vision', 'guard', 'embed', 'embed_large', 'rerank', 'parse'] as const

export interface KeyEntry {
  ref: string; label: string; roles: string[]; preview: string; created: string
  last_test?: { ok: boolean; at: string; latency_ms: number; model: string }
  storage: 'dpapi' | 'fernet' | string
}
export interface SettingsData {
  keys: KeyEntry[]; active: Record<string, string>; models: Record<string, string>
  base_url: string; retrieval_url: string; env_keys: Record<string, boolean>; vault_available: boolean
  /** vault encryption backend ('dpapi' | 'fernet') or null when unavailable */
  storage?: string | null
  /** built-in model id per role (before .env and overrides) */
  defaults?: Record<string, string>
}
export interface TestResult { ok: boolean; status: number | null; latency_ms: number; model: string; message: string }
export interface Catalog { models: { id: string; owned_by: string }[]; note: string }

/** status 0 = the API could not be reached at all (network error). */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

/** Plain-language message for the statuses the settings endpoints can return. */
export function plain(e: unknown): string {
  if (!(e instanceof ApiError)) return 'Something went wrong. Try again.'
  switch (e.status) {
    case 0: return 'The console API is not reachable.'
    case 401: case 403: return 'The console refused the request (token or origin check). Reload the page and try again.'
    case 404: return 'That key no longer exists. Reload to refresh the list.'
    case 422: return 'The server rejected the value as invalid. Check the format and try again.'
    case 429: return 'Too many connection tests. Wait a minute and try again.'
    case 501: return 'No encryption backend on this machine. Put the key in .env as NVIDIA_API_KEY instead.'
    default: return `The server returned an error (${e.status}).`
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  try {
    if (method !== 'GET') {
      const t = await fetch(`${BASE}/api/token`)
      if (!t.ok) throw new ApiError(t.status, 'token')
      headers['X-Console-Token'] = ((await t.json()) as { token: string }).token
      headers['Content-Type'] = 'application/json'
    }
    const r = await fetch(`${BASE}/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
    if (!r.ok) throw new ApiError(r.status, `${method} ${path}`)
    return (await r.json()) as T
  } catch (e) {
    throw e instanceof ApiError ? e : new ApiError(0, 'network')
  }
}

export const getSettings = () => call<SettingsData>('GET', '/settings')
export const getCatalog = () => call<Catalog>('GET', '/settings/catalog')
export const addKey = (label: string, value: string, roles: string[]) => call<{ ref: string }>('POST', '/settings/keys', { label, value, roles })
export const deleteKey = (ref: string) => call<{ ok: boolean }>('DELETE', `/settings/keys/${encodeURIComponent(ref)}`)
export const setActive = (role: string, ref: string | null) => call<{ ok: boolean }>('PUT', '/settings/active', { role, ref })
export const setModel = (role: string, model: string) => call<{ ok: boolean }>('PUT', '/settings/models', { role, model })
export const testKey = (ref: string | null, role: string) => call<TestResult>('POST', '/settings/test', { ref, role })

export const KEY_RX = /^nvapi-[A-Za-z0-9_-]{20,}$/
export const MODEL_RX = /^[A-Za-z0-9._/-]{3,80}$/

/** Fake, non-secret data for the labelled read-only demo mode. */
export const DEMO: SettingsData = {
  keys: [{ ref: '00000000-0000-4000-8000-000000000001', label: 'Demo key', roles: ['default', 'embed'], preview: 'nvapi-…demo', created: '2026-01-01T00:00:00Z',
    last_test: { ok: true, at: '2026-01-01T00:05:00Z', latency_ms: 420, model: 'demo/model' }, storage: 'fernet' }],
  active: { default: '00000000-0000-4000-8000-000000000001' },
  models: { fast: 'demo/fast-model', reason: 'demo/reason-model', vision: 'demo/vision-model', guard: 'demo/guard-model', embed: 'demo/embed-model', embed_large: 'demo/embed-large', rerank: 'demo/rerank-model', parse: 'demo/parse-model' },
  base_url: 'https://example.invalid/v1', retrieval_url: 'https://example.invalid/retrieval', env_keys: { EMBED: true }, vault_available: true,
}
