// Demo data, used only when the local API is unreachable (client.ts sets the 'demo data' flag).
import type { AskResponse, CaseDetailData, IdentityData, RedteamResponse, TimelineData } from './client.ts'

export const mockTimeline = (): TimelineData => ({
  requested_at: '2026-03-01T09:00:00Z', reported_at: '2026-03-10T12:00:00Z', audit_at: '2026-04-01T00:00:00Z',
  items: [
    { observed_at: '2026-03-02T10:00:00Z', captured_at: '2026-03-02T10:00:00Z', system_id: 'account_service', resource_id: 'account_005', observation: 'ABSENT', evidence_id: 'activity_0101', is_claim: true, citable: true },
    { observed_at: '2026-03-05T08:00:00Z', captured_at: '2026-03-05T08:00:00Z', system_id: 'sync_job', resource_id: 'sync_002', observation: 'ACTIVE', evidence_id: 'activity_0140', is_claim: true, citable: true },
    { observed_at: '2026-03-20T04:00:00Z', captured_at: '2026-03-20T04:05:00Z', system_id: 'account_service', resource_id: 'account_005', observation: 'PRESENT', evidence_id: 'evidence_01', is_claim: false, citable: true },
    { observed_at: '2026-03-25T04:00:00Z', captured_at: '2026-03-25T04:05:00Z', system_id: 'backup_store', resource_id: 'backup_009', observation: 'RESTORE_RISK', evidence_id: 'evidence_07', is_claim: false, citable: true },
    { observed_at: '2026-03-28T04:00:00Z', captured_at: '2026-03-28T04:05:00Z', system_id: 'search_index', resource_id: 'index_003', observation: 'REDACTED', evidence_id: 'evidence_09', is_claim: false, citable: true },
    { observed_at: '2026-04-05T04:00:00Z', captured_at: '2026-04-05T04:05:00Z', system_id: 'analytics_store', resource_id: 'event_44', observation: 'ABSENT', evidence_id: 'evidence_12', is_claim: false, citable: false },
  ],
})

export const mockIdentity = (): IdentityData => ({
  nodes: [
    { id: 'u', kind: 'user', label: 'user_0042', current: true },
    { id: 'e1', kind: 'email', label: 'a***@example.com', current: true },
    { id: 'e2', kind: 'email', label: 'o***@old.example', current: false },
    { id: 'p1', kind: 'phone', label: '+1***4421', current: true },
    { id: 'h1', kind: 'hash', label: 'sha256:9f2c...', current: true },
    { id: 'r1', kind: 'resource', label: 'account_service/account_005', current: true },
    { id: 'r2', kind: 'resource', label: 'support/ticket_17', current: true },
    { id: 'r3', kind: 'resource', label: 'backup_store/backup_009', current: true },
    { id: 'r4', kind: 'resource', label: 'logs/log_220', current: true },
  ],
  edges: [
    { from: 'u', to: 'e1', label: 'email' }, { from: 'u', to: 'e2', label: 'email' }, { from: 'u', to: 'p1', label: 'phone' }, { from: 'u', to: 'h1', label: 'hash' },
    { from: 'e1', to: 'r1', label: 'email' }, { from: 'e2', to: 'r2', label: 'email' }, { from: 'h1', to: 'r3', label: 'hash' }, { from: 'p1', to: 'r4', label: 'phone' },
  ],
})

export const mockCase = (caseId: string): CaseDetailData => ({
  case_id: caseId, reported: 'COMPLETE', status: 'INCOMPLETE',
  requested_at: '2026-03-01T09:00:00Z', reported_at: '2026-03-10T12:00:00Z', audit_at: '2026-04-01T00:00:00Z',
  intent: { label: 'DELETE', source: 'rules', flags: [] },
  identity: { user_id: 'user_0042', email_count: 2, phone_count: 1 },
  steps: [
    { step_no: 1, phase: 'FINDING', system_id: 'account_service', resource_id: 'account_005', operation: 'REPORT_REMAINING_RECORD', state: 'PRESENT', evidence_id: 'evidence_01' },
    { step_no: 2, phase: 'FINDING', system_id: 'backup_store', resource_id: 'backup_009', operation: 'REPORT_RESTORE_RISK', state: 'ACTIVE', evidence_id: 'evidence_07' },
    { step_no: 3, phase: 'REMEDIATION', system_id: 'backup_store', resource_id: 'backup_009', operation: 'BLOCK_RESTORE', state: 'BLOCKED', evidence_id: '' },
    { step_no: 4, phase: 'REMEDIATION', system_id: 'account_service', resource_id: 'account_005', operation: 'DELETE_RECORD', state: 'ABSENT', evidence_id: '' },
    { step_no: 5, phase: 'VERIFICATION', system_id: 'backup_store', resource_id: 'backup_009', operation: 'VERIFY_RESTORE_BLOCKED', state: 'BLOCKED', evidence_id: '' },
    { step_no: 6, phase: 'VERIFICATION', system_id: 'account_service', resource_id: 'account_005', operation: 'VERIFY_RECORD_ABSENT', state: 'ABSENT', evidence_id: '' },
  ],
  trail: [{ ts: '2026-04-01T00:00:01Z', run_id: 'demo', case_id: caseId, stage: 'decide', gate: 'G2', verdict: 'WARN', summary: 'Reported COMPLETE but a record is still present', evidence_ids: ['evidence_01'] }],
})

export const mockAsk = (q: string): AskResponse =>
  /ignore|rules|secret|key/i.test(q)
    ? { answer: '', citations: [], refused: true, reason: 'Question is not about this run.' }
    : { answer: 'In demo data, case_33 was reported COMPLETE but a record is still present in account_service.', citations: [{ case_id: 'case_33', evidence_id: 'evidence_01', summary: 'account_005 still PRESENT at audit_at' }], refused: false }

export const mockRedteam = (text: string): RedteamResponse =>
  /ignore|ignora|mark .*complete|marca/i.test(text)
    ? { label: 'NOT_DELETE', confidence: 0.9, source: 'rules', flags: ['injection_marker'], status_would_be: 'unchanged' }
    : { label: 'DELETE', confidence: 0.95, source: 'rules', flags: [], status_would_be: 'unchanged' }
