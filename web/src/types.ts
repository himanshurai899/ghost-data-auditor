// Response types: exactly docs/console_api.md.
import type { ComponentType } from 'react'

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

// ---- screen registry contract (see screens/registry.ts) ----
export interface CaseFilter {
  status?: Status
  reported?: Reported
}
export interface ScreenProps {
  runId: string | null
  /** shared selected case (null = none) */
  caseId: string | null
  setCaseId: (id: string | null) => void
  /** shared Cases-tab filter, set by Claim vs truth cells */
  filter: CaseFilter
  setFilter: (f: CaseFilter) => void
  /** switch tab by registry id */
  go: (screenId: string) => void
}
export interface ScreenDef {
  id: string
  title: string
  component: ComponentType<ScreenProps>
}
