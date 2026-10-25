// Single source for the landing pipeline: stages (docs/architecture.md 4.1) and gates (4.2). Used by the cards, tooltips and tables.
import type { IconName } from '../ui'

export interface Stage {
  id: string; name: string; icon: IconName; purpose: string; io: string; module: string
  /** set when a model call can happen here (edges only) */
  llm?: string
}
export interface Gate {
  id: string; name: string; after: string; level: 'run' | 'case'; check: string; onFail: string; module: string
}

export const STAGES: Stage[] = [
  { id: 'S0', name: 'Load', icon: 'file', purpose: 'Reads the dataset CSVs into typed records.', io: 'CSV files to Request, Identity, AuditRow, Activity, Rule, EvidenceFile', module: 'code/ghost/contract.py' },
  { id: 'S1', name: 'Ingest', icon: 'database', purpose: 'Turns every evidence file into structured facts, one parser per format.', io: 'evidence file to Fact[]', module: 'code/ghost/evidence.py', llm: 'Only PNG and PDF pages use a vision model; results are cached.' },
  { id: 'S2', name: 'Intent', icon: 'search', purpose: 'Decides whether the request text really authorises deletion.', io: 'request_text to DELETE or NOT_DELETE (+ confidence)', module: 'code/ghost/intent.py', llm: 'Rules run first; a model is asked only when confidence is low.' },
  { id: 'S3', name: 'Identity', icon: 'user', purpose: 'Resolves the person behind the email, including historical identifiers.', io: 'email + audit_at to Subject {user_id, emails, phones, hashes, names}', module: 'code/ghost/identity.py' },
  { id: 'S4', name: 'Link', icon: 'link', purpose: 'Links facts to the subject and drops anything observed after audit_at.', io: 'Subject + fact index to candidate facts observed at or before audit_at', module: 'code/ghost/reasoning.py' },
  { id: 'S5', name: 'State', icon: 'eye', purpose: 'Reconstructs each resource state at audit_at, exposed PII, flows and restores.', io: 'facts per (system, resource) to current state', module: 'code/ghost/reasoning.py' },
  { id: 'S6', name: 'Policy', icon: 'lock', purpose: 'Applies deletion_rules.csv to get the required final state per resource.', io: 'resource + category + condition to required state (rule id recorded)', module: 'code/ghost/reasoning.py' },
  { id: 'S7', name: 'Plan', icon: 'flow', purpose: 'Builds findings, ordered remediation and verification steps, and the status.', io: 'violations + compliant resources to ordered steps + status', module: 'code/ghost/planner.py' },
  { id: 'S8', name: 'Emit', icon: 'check', purpose: 'Writes output.csv, the run trail and the report.', io: 'rows to output.csv, trail, report', module: 'code/ghost/contract.py, code/ghost/audit.py' },
]

export const GATES: Gate[] = [
  { id: 'G1', name: 'Input', after: 'S0 Load', level: 'run', check: 'Exact headers; 518 unique case_ids; ISO-8601 times; requested_at not after reported_at or audit_at; every manifest path resolves inside dataset/evidence/.', onFail: 'Abort the run.', module: 'code/ghost/contract.py' },
  { id: 'G2', name: 'Evidence', after: 'S1 Ingest', level: 'run', check: 'Every manifest file was parsed or quarantined; captured_at known; SHA-256 recorded; SQL ran under the SQLite authorizer; no file over the size cap.', onFail: 'Quarantine the file and WARN; abort if more than 10% are quarantined.', module: 'code/ghost/evidence.py, safety.py' },
  { id: 'G3', name: 'Intent', after: 'S2 Intent', level: 'case', check: 'Label is in the enum; rule and model agree or the adjudicator decided; injection markers are flagged.', onFail: 'Delete only if the rules say so, otherwise NOT_APPLICABLE, plus a WARN.', module: 'code/ghost/intent.py' },
  { id: 'G4', name: 'Identity', after: 'S3 Identity', level: 'case', check: 'The request email resolves to exactly one user_id as of audit_at, and the identifier set includes historical values.', onFail: 'No findings are possible; WARN and a trail entry for review.', module: 'code/ghost/identity.py' },
  { id: 'G5', name: 'Temporal', after: 'S4 Link', level: 'case', check: 'Hard filter: only facts from files captured at or before audit_at may decide state or be cited. Discovery may use later files only for rows observed at or after requested_at.', onFail: 'The fact is dropped, never a soft warning.', module: 'code/ghost/reasoning.py' },
  { id: 'G6', name: 'Contract', after: 'S7 Plan', level: 'case', check: 'Enums valid; phase, operation and state consistent; steps numbered from 1 in phase order; COMPLETE has only cited verification; INCOMPLETE has uncited remediation; NOT_APPLICABLE is []; cited ids exist and are not later than audit_at.', onFail: 'Case marked FAIL in the report; the run continues; the release gate fails.', module: 'code/ghost/contract.py' },
  { id: 'G7', name: 'Release', after: 'S8 Emit', level: 'run', check: '518 rows; numeric case_id sort; exact header; zero G6 failures; output SHA-256 recorded for the determinism check.', onFail: 'Non-zero exit.', module: 'code/ghost/contract.py' },
]
