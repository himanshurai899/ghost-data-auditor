// Response types: exactly docs/console_api.md.
import type { ComponentType } from 'react'
import type { IconName } from './ui'

export type Status = 'COMPLETE' | 'INCOMPLETE' | 'NOT_APPLICABLE'
export type Reported = 'COMPLETE' | 'PARTIALLY_COMPLETE' | 'NOT_STARTED'
export type Counts = Record<Status, number>

export interface RunSummary {
  run_id: string
  started: string
  cases: number
  counts: Counts
  strict_temporal: boolean
  output_sha256: string
}
export interface RunDetail extends RunSummary {
  claim_matrix: { reported: Record<Reported, Counts> }
  running: boolean
}
export interface StartRun {
  dataset: 'full' | 'sample'
  cases?: string[]
  strict_temporal: boolean
}
export interface TrailEvent {
  ts: string
  run_id: string
  case_id?: string | null
  stage: string
  gate?: string | null
  verdict?: string | null
  summary: string
  evidence_ids?: string[]
  detail?: unknown
}
export interface CaseRow {
  case_id: string
  reported: Reported
  status: Status
  steps: number
  warns: number
  fails: number
}
export interface Step {
  step_no: number
  phase: 'FINDING' | 'REMEDIATION' | 'VERIFICATION'
  system_id: string
  resource_id: string
  operation: string
  state: string
  evidence_id: string
}
export interface CaseDetail {
  case_id: string
  reported: Reported
  reported_at: string
  requested_at: string
  audit_at: string
  status: Status
  intent: { label: string; source: string; flags: string[] }
  identity: { user_id: string; email_count: number; phone_count: number }
  steps: Step[]
  trail: TrailEvent[]
}
export interface Timeline {
  requested_at: string
  reported_at: string
  audit_at: string
  items: {
    observed_at: string
    captured_at: string
    system_id: string
    resource_id: string
    observation: string
    evidence_id: string
    is_claim: boolean
    citable: boolean
  }[]
}
export interface Identity {
  nodes: { id: string; kind: 'user' | 'email' | 'phone' | 'hash' | 'resource'; label: string; current: boolean }[]
  edges: { from: string; to: string; label: string }[]
}
export interface Usage {
  calls: number
  cached: number
  tokens: number
  by_model: unknown[]
  output_sha256: string
  deterministic: boolean | null
}
export interface RedteamResult {
  label: string
  confidence: number
  source: string
  flags: string[]
  status_would_be: 'unchanged' | 'changed'
}
export interface AskResult {
  answer: string
  citations: { case_id?: string; evidence_id?: string; summary: string }[]
  refused: boolean
  reason?: string
}

// ---- page registry contract (pages/index.ts) ----
export interface CaseFilter {
  status?: Status
  reported?: Reported
}
/** Props the shell passes to EVERY page component. */
export interface ScreenProps {
  runId: string | null
  /** selected case: derived from the route #/cases/<id>; setCaseId navigates there (null = #/cases) */
  caseId: string | null
  setCaseId: (id: string | null) => void
  /** shared Cases filter, set by Claim vs truth cells */
  filter: CaseFilter
  setFilter: (f: CaseFilter) => void
  /** navigate by page path ('cases', 'dashboard', 'live', ...; '' = landing) */
  go: (path: string) => void
  /** all runs (newest first) as loaded by the shell */
  runs: RunSummary[]
  /** start a full audit run and navigate to #/live */
  startAudit: () => Promise<void>
  starting: boolean
}
export interface PageDef {
  /** route segment without '#/': '' (landing), 'dashboard', 'cases', ... Keep stable. */
  path: string
  title: string
  icon: IconName
  /** show in the left rail / bottom tab bar */
  nav: boolean
  component: ComponentType<ScreenProps>
}
