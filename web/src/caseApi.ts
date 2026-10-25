// Typed client for the case-level endpoints (docs/console_api.md + docs/ui_redesign.md addendum).
// Errors are real: no mock fallback here, so the page can show a 404 or a retry.
import { useCallback, useEffect, useState } from 'react'
import type { CaseDetail, CaseRow } from './types'

export type TierLetter = 'A' | 'B' | 'C' | 'D' | 'X'
export interface ChainStep {
  step_no: number; phase: 'FINDING' | 'REMEDIATION' | 'VERIFICATION'; operation: string; system_id: string; resource_id: string
  state: string; evidence_id: string; tier: TierLetter; tier_label: string; score: number
  captured_at: string | null; observed_at: string | null; citable: boolean; why: string
}
export interface RankRow { evidence_id: string; tier: TierLetter; score: number; used_by_steps: number[] }
export interface EvidenceData { chain: ChainStep[]; ranking: RankRow[]; summary: Record<TierLetter, number> }

export class HttpError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response
  try { res = await fetch(path) } catch { throw new HttpError(0, 'The API is unreachable. Is the backend running on port 8000?') }
  if (!res.ok) {
    let msg = res.statusText
    try { const j = await res.json(); if (typeof j.detail === 'string') msg = j.detail } catch { /* keep statusText */ }
    throw new HttpError(res.status, msg)
  }
  return res.json() as Promise<T>
}

const base = (run: string, c: string) => `/api/runs/${encodeURIComponent(run)}/cases/${encodeURIComponent(c)}`
export const getEvidence = (run: string, c: string) => getJson<EvidenceData>(`${base(run, c)}/evidence`)
export const getCaseDetail = (run: string, c: string) => getJson<CaseDetail>(base(run, c))

// The list is small (518 rows); fetched once per run and filtered client-side. Cached so prev/next is instant.
const lists = new Map<string, Promise<CaseRow[]>>()
export function getCaseList(run: string, fresh = false): Promise<CaseRow[]> {
  if (fresh) lists.delete(run)
  let p = lists.get(run)
  if (!p) {
    p = getJson<CaseRow[]>(`/api/runs/${encodeURIComponent(run)}/cases`)
    p.catch(() => lists.delete(run))
    lists.set(run, p)
  }
  return p
}

export const fmtDate = (iso: string | null | undefined) => (iso ? iso.replace('T', ' ').replace(/:\d\d(\.\d+)?Z?$/, '').replace(/Z$/, '') + ' UTC' : 'n/a')
export const humanOp = (op: string) => { const s = op.toLowerCase().replace(/_/g, ' '); return s.charAt(0).toUpperCase() + s.slice(1) }
export const caseNum = (id: string) => Number(id.replace(/\D/g, '')) || 0

/** Small fetch hook with retry: `reload()` re-runs the request. */
export type Load<T> = { state: 'loading' } | { state: 'error'; error: string; status: number } | { state: 'ok'; data: T }
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]): [Load<T>, () => void] {
  const [n, setN] = useState(0)
  const [s, set] = useState<Load<T>>({ state: 'loading' })
  useEffect(() => {
    let live = true
    set({ state: 'loading' })
    fn().then((data) => { if (live) set({ state: 'ok', data }) }, (e: unknown) => {
      if (live) set({ state: 'error', error: e instanceof Error ? e.message : String(e), status: e instanceof HttpError ? e.status : 0 })
    })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, n])
  return [s, useCallback(() => setN((x) => x + 1), [])]
}
