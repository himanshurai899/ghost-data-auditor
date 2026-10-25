// Typed client for GET /api/dashboard and GET /api/metrics/cost (docs/ui_redesign.md "Metrics, dashboard, evidence chain").
// No offline demo data: when the API is unreachable the pages show an error state with retry, never invented numbers.
import { useCallback, useEffect, useState } from 'react'
import { isOffline } from './api'
import type { Counts, Reported } from './types'

export interface DashboardData {
  run_id: string
  cases: number
  counts: Counts
  claim_matrix: { reported: Record<Reported, Counts> }
  ghosts: { count: number; of: number; pct: number | null }
  findings_by_system: { system_id: string; records: number; pii: number; flows: number; restores: number }[]
  gates: { gate: string; pass: number; warn: number; fail: number }[]
  runs: { run_id: string; started: string; cases: number; counts: Counts; output_sha256: string; strict_temporal: boolean; duration_s: number | null }[]
  evidence_mix: { A: number; B: number; C: number; D: number }
  /** model calls made during the run (null for runs recorded before usage logging) */
  llm_calls?: number | null
  offline?: boolean | null
}

export interface ModelRow {
  provider: string; model: string; role: string | null; calls: number; cached: number
  tokens_in: number | null; tokens_out: number | null; est_cost_usd: number | null
}
export interface CostData {
  run: {
    run_id: string; requests: number | null; calls: number; cached: number; live: number
    tokens_in: number | null; tokens_out: number | null; avg_tokens_per_request: number | null
    est_cost_usd: number | null; billed_usd: number; by_model: ModelRow[]; calls_over_time: { t: string; calls: number }[]
  }
  cache_build: { calls: number; by_model: ModelRow[] }
  all_runs: { run_id: string; calls: number | null; tokens: number | null; duration_s: number | null }[]
  pricing: { source: string | null; rates_known: boolean }
  notes: string[]
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
async function get<T>(path: string, runId: string | null): Promise<T> {
  if (isOffline()) throw new Error('The console API is unreachable (offline). Start it with: cd code && python -m uvicorn ghost.api:app --port 8000')
  const r = await fetch(`${BASE}/api${path}${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`)
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`)
  return r.json() as Promise<T>
}
export const getDashboard = (runId: string | null) => get<DashboardData>('/dashboard', runId)
export const getCost = (runId: string | null) => get<CostData>('/metrics/cost', runId)

/** Number formatting shared by both pages; null/undefined is shown as 'n/a', never 0. */
export const num = (n: number | null | undefined) => (n === null || n === undefined ? 'n/a' : n.toLocaleString('en-US'))
export const human = (s: string) => { const t = s.replace(/_/g, ' '); return t.charAt(0).toUpperCase() + t.slice(1) }
export const secs = (s: number | null) => (s === null ? 'n/a' : s < 90 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`)

/** Loads fn(runId); `reload` retries. Ignores stale responses when runId changes. */
export function useLoad<T>(fn: (runId: string | null) => Promise<T>, runId: string | null) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setState((s) => ({ ...s, error: null, loading: true }))
    fn(runId).then(
      (data) => live && setState({ data, error: null, loading: false }),
      (e: unknown) => live && setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false }),
    )
    return () => { live = false }
  }, [fn, runId, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}
