// Typed client for the console API (docs/console_api.md). Self-contained.
import { useEffect, useState, useSyncExternalStore } from 'react'
import { mockCase,mockIdentity, mockTimeline, mockAsk, mockRedteam } from './mock.ts'

export interface Step { step_no: number; phase: 'FINDING' | 'REMEDIATION' | 'VERIFICATION'; system_id: string; resource_id: string; operation: string; state: string; evidence_id: string }
export interface TrailEvent { ts: string; run_id: string; case_id: string; stage: string; gate: string; verdict: string; summary: string; evidence_ids: string[]; detail?: unknown }
export interface CaseDetailData {
  case_id: string; reported: string; reported_at: string; requested_at: string; audit_at: string; status: string
  intent: { label: string; source: string; flags: string[] }
  identity: { user_id: string; email_count: number; phone_count: number }
  steps: Step[]; trail: TrailEvent[]
}
export interface TimelineItem { observed_at: string; captured_at: string; system_id: string; resource_id: string; observation: string; evidence_id: string; is_claim: boolean; citable: boolean }
export interface TimelineData { requested_at: string; reported_at: string; audit_at: string; items: TimelineItem[] }
export interface IdNode { id: string; kind: 'user' | 'email' | 'phone' | 'hash' | 'resource'; label: string; current: boolean }
export interface IdEdge { from: string; to: string; label: string }
export interface IdentityData { nodes: IdNode[]; edges: IdEdge[] }
export interface Citation { case_id?: string; evidence_id?: string; summary: string }
export interface AskResponse { answer: string; citations: Citation[]; refused: boolean; reason?: string }
export interface RedteamResponse { label: string; confidence: number; source: string; flags: string[]; status_would_be: 'unchanged' | 'changed' }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

/** True once any call fell back to mock data (screens show a 'demo data' badge). */
let demo = false
const listeners = new Set<() => void>()
export const isDemo = () => demo
export function onDemoChange(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } }
function setDemo() { if (!demo) { demo = true; listeners.forEach((f) => f()) } }

let token: Promise<string> | null = null
const getToken = () => (token ??= fetch('/api/token').then((r) => { if (!r.ok) throw new Error('token'); return r.json() }).then((j: { token: string }) => j.token).catch((e) => { token = null; throw e }))

async function call<T>(path: string, init: RequestInit | undefined, fallback: () => T): Promise<T> {
  let res: Response
  try { res = await fetch(path, init) } catch (e) {
    // A timeout is NOT 'backend down': never swap in demo data for it (a hung question would show a made-up answer).
    if (e instanceof DOMException && (e.name === 'TimeoutError' || e.name === 'AbortError')) throw new ApiError(504, 'The auditor took too long to answer. The first question on a large run builds a search index; try again in a moment.')
    setDemo(); return fallback()
  }
  if (!res.ok) {
    if (res.status >= 502) { setDemo(); return fallback() } // dev proxy with no backend
    let msg = res.statusText
    try { const j = await res.json(); if (typeof j.detail === 'string') msg = j.detail } catch { /* keep statusText */ }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown, fallback: () => T, timeoutMs = 0): Promise<T> {
  let t: string
  try { t = await getToken() } catch { setDemo(); return fallback() }
  return call<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Console-Token': t }, body: JSON.stringify(body), ...(timeoutMs ? { signal: AbortSignal.timeout(timeoutMs) } : {}) }, fallback)
}

const base = (runId: string, caseId: string) => `/api/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}`
export const getCase = (r: string, c: string) => call<CaseDetailData>(base(r, c), undefined, () => mockCase(c))
export const getTimeline = (r: string, c: string) => call<TimelineData>(`${base(r, c)}/timeline`, undefined, mockTimeline)
export const getIdentity = (r: string, c: string) => call<IdentityData>(`${base(r, c)}/identity`, undefined, mockIdentity)
export const ask = (run_id: string, question: string) => post<AskResponse>('/api/ask', { run_id, question }, () => mockAsk(question), 75_000)
export const redteam = (text: string) => post<RedteamResponse>('/api/redteam', { text }, () => mockRedteam(text))

// --- React helpers (no JSX) ---
export type Async<T> = { state: 'loading' } | { state: 'error'; error: string } | { state: 'ok'; data: T }
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [s, set] = useState<Async<T>>({ state: 'loading' })
  useEffect(() => {
    let live = true
    set({ state: 'loading' })
    fn().then((data) => { if (live) set({ state: 'ok', data }) }, (e: unknown) => { if (live) set({ state: 'error', error: e instanceof Error ? e.message : String(e) }) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return s
}
export const useDemo = () => useSyncExternalStore(onDemoChange, isDemo)
