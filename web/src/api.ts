// Typed client for docs/console_api.md. Offline demo data lives only in the MOCK section below.
import type {
  AskResult, CaseDetail, CaseRow, Identity, RedteamResult, RunDetail, RunSummary, StartRun, Timeline,
  TrailEvent, Usage,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
let offline = false
export const isOffline = () => offline

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}/api${path}`, init)
  if (!r.ok) throw new Error(`${init?.method ?? 'GET'} ${path} -> ${r.status}`)
  return r.json() as Promise<T>
}
const q = (o: Record<string, string | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(o)) if (v) p.set(k, v)
  const s = p.toString()
  return s ? `?${s}` : ''
}
const rp = (id: string) => `/runs/${encodeURIComponent(id)}`
const cp = (id: string, c: string) => `${rp(id)}/cases/${encodeURIComponent(c)}`

/** Probe the API once; falls back to labelled offline demo data if it is unreachable. */
export async function health(): Promise<boolean> {
  try {
    await http<{ ok: boolean }>('/health')
    offline = false
  } catch {
    offline = true
  }
  return !offline
}

export const getRuns = () => (offline ? Promise.resolve(mock.runs()) : http<RunSummary[]>('/runs'))
export const getRun = (id: string) => (offline ? Promise.resolve(mock.run()) : http<RunDetail>(rp(id)))
export const getCases = (id: string, f: { status?: string; reported?: string; q?: string } = {}) =>
  offline ? Promise.resolve(mock.cases(f)) : http<CaseRow[]>(`${rp(id)}/cases${q(f)}`)
export const getCase = (id: string, c: string) => (offline ? Promise.resolve(mock.case(c)) : http<CaseDetail>(cp(id, c)))
export const getTimeline = (id: string, c: string) => (offline ? Promise.resolve(mock.timeline()) : http<Timeline>(`${cp(id, c)}/timeline`))
export const getIdentity = (id: string, c: string) => (offline ? Promise.resolve(mock.identity()) : http<Identity>(`${cp(id, c)}/identity`))
export const getUsage = (id: string) => (offline ? Promise.resolve(mock.usage()) : http<Usage>(`${rp(id)}/usage`))

const post = <T>(path: string, body: unknown, token: string) =>
  http<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Console-Token': token },
    body: JSON.stringify(body),
  })
const token = async () => (await http<{ token: string }>('/token')).token

export async function startRun(body: StartRun): Promise<{ run_id: string }> {
  if (offline) return { run_id: mockRunId }
  return post('/runs', body, await token())
}
export async function redteam(text: string): Promise<RedteamResult> {
  if (offline) return mock.redteam(text)
  return post('/redteam', { text }, await token())
}
export async function ask(run_id: string, question: string): Promise<AskResult> {
  if (offline) return mock.ask()
  return post('/ask', { run_id, question }, await token())
}

/**
 * Follow a run's SSE stream. Reconnects with ?from=<events seen>, so replays never duplicate.
 * Returns a close function.
 */
export function openEvents(runId: string, onEvent: (e: TrailEvent) => void, onDone: () => void): () => void {
  if (offline) return mock.stream(onEvent, onDone)
  let seen = 0
  let es: EventSource | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let closed = false
  const connect = () => {
    es = new EventSource(`${BASE}/api${rp(runId)}/events${q({ from: String(seen) })}`)
    es.onmessage = (m) => {
      try {
        const e = JSON.parse(m.data) as TrailEvent
        seen++
        onEvent(e)
      } catch { /* ignore malformed frame */ }
    }
    es.addEventListener('done', () => { closed = true; es?.close(); onDone() })
    es.onerror = () => {
      es?.close()
      if (!closed) timer = setTimeout(connect, 1500)
    }
  }
  connect()
  return () => { closed = true; clearTimeout(timer); es?.close() }
}

export const GATE_IDS = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7']

// ======================= MOCK (offline demo data) =======================
const mockRunId = '20261025T000000Z-abc123'
const mockCasesList = (): CaseRow[] =>
  Array.from({ length: 60 }, (_, i) => {
    const status = (['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE'] as const)[i % 3]
    return {
      case_id: `case_${i + 1}`,
      reported: (['COMPLETE', 'PARTIALLY_COMPLETE', 'NOT_STARTED'] as const)[(i * 7) % 3],
      status, steps: status === 'NOT_APPLICABLE' ? 0 : 4 + (i % 5), warns: i % 11 === 0 ? 1 : 0, fails: i % 29 === 0 ? 1 : 0,
    }
  })
const mock = {
  runs: (): RunSummary[] => [{
    run_id: mockRunId, started: '2026-10-25T00:00:00Z', cases: 60,
    counts: { COMPLETE: 20, INCOMPLETE: 20, NOT_APPLICABLE: 20 }, strict_temporal: false, output_sha256: 'deadbeefcafe0123',
  }],
  run: (): RunDetail => ({
    ...mock.runs()[0], running: false,
    claim_matrix: { reported: {
      COMPLETE: { COMPLETE: 12, INCOMPLETE: 6, NOT_APPLICABLE: 2 },
      PARTIALLY_COMPLETE: { COMPLETE: 3, INCOMPLETE: 9, NOT_APPLICABLE: 8 },
      NOT_STARTED: { COMPLETE: 5, INCOMPLETE: 5, NOT_APPLICABLE: 10 },
    } },
  }),
  cases: (f: { status?: string; reported?: string; q?: string }) =>
    mockCasesList().filter((c) => (!f.status || c.status === f.status) && (!f.reported || c.reported === f.reported) && (!f.q || c.case_id.startsWith(f.q))),
  case: (c: string): CaseDetail => ({
    case_id: c, reported: 'COMPLETE', reported_at: '2026-01-02T10:00:00Z', requested_at: '2026-01-01T09:00:00Z',
    audit_at: '2026-01-03T00:00:00Z', status: 'INCOMPLETE', intent: { label: 'DELETE', source: 'rules', flags: [] },
    identity: { user_id: 'user_***', email_count: 2, phone_count: 1 }, steps: [], trail: [],
  }),
  timeline: (): Timeline => ({ requested_at: '', reported_at: '', audit_at: '', items: [] }),
  identity: (): Identity => ({ nodes: [], edges: [] }),
  usage: (): Usage => ({ calls: 0, cached: 0, tokens: 0, by_model: [], output_sha256: 'deadbeefcafe0123', deterministic: true }),
  redteam: (text: string): RedteamResult => ({
    label: /ignore|mark .*complete/i.test(text) ? 'INJECTION' : 'DELETE', confidence: 0.9, source: 'rules', flags: [], status_would_be: 'unchanged',
  }),
  ask: (): AskResult => ({ answer: 'Offline demo data: no grounded answer available.', citations: [], refused: true, reason: 'offline' }),
  stream(onEvent: (e: TrailEvent) => void, onDone: () => void) {
    const ev = (stage: string, gate: string | null, verdict: string | null, case_id?: string): TrailEvent =>
      ({ ts: '', run_id: mockRunId, case_id, stage, gate, verdict, summary: `${stage} ${verdict ?? ''}`.trim() })
    const evs: TrailEvent[] = [ev('load', 'G1', 'PASS'), ev('ingest', 'G2', 'PASS')]
    for (const c of mockCasesList()) {
      evs.push(ev('intent', 'G3', c.warns ? 'WARN' : 'PASS', c.case_id), ev('identity', 'G4', 'PASS', c.case_id),
        ev('link', null, null, c.case_id), ev('plan', null, null, c.case_id),
        ev('contract', 'G6', c.fails ? 'FAIL' : 'PASS', c.case_id), ev('emit', null, null, c.case_id))
    }
    evs.push(ev('release', 'G7', 'PASS'))
    let i = 0
    const t = setInterval(() => {
      for (let k = 0; k < 6 && i < evs.length; k++) onEvent(evs[i++])
      if (i >= evs.length) { clearInterval(t); onDone() }
    }, 120)
    return () => clearInterval(t)
  },
}
