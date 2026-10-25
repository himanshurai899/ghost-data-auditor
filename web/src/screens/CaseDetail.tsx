import { getCase, useAsync } from './client.ts'
import type { Step } from './client.ts'
import { StatusBadge } from '../ui'
import Timeline, { DemoBadge, Gate } from './Timeline.tsx'
import './screens.css'

const PHASES: Step['phase'][] = ['FINDING', 'REMEDIATION', 'VERIFICATION']

export default function CaseDetail({ runId, caseId }: { runId: string; caseId: string }) {
  const a = useAsync(() => getCase(runId, caseId), [runId, caseId])
  return (
    <section className="screen" aria-label={`Case ${caseId}`}>
      <Gate a={a}>
        {(c) => {
          const ghost = c.reported === 'COMPLETE' && c.status === 'INCOMPLETE'
          const trail = c.trail.filter((e) => e.verdict !== 'PASS')
          return (
            <>
              <div className={`s-card cd-head ${ghost ? 'cd-ghost' : ''}`}>
                <h2>{c.case_id}</h2>
                <span className="chip plain">reported: {c.reported}</span>
                <span aria-hidden="true">→</span>
                <span>audited: <StatusBadge status={c.status} /></span>
                {ghost && <span className="chip ghost">Ghost: reported COMPLETE, still INCOMPLETE</span>}
                <DemoBadge />
                <div className="s-muted" style={{ flexBasis: '100%' }}>
                  intent <b>{c.intent.label}</b> via {c.intent.source}
                  {c.intent.flags.map((f) => <span key={f} className={`chip ${f === 'injection_marker' ? 'red' : 'plain'}`} style={{ marginLeft: 6 }}>{f}</span>)}
                  {' · '}user <code>{c.identity.user_id}</code> · {c.identity.email_count} email(s), {c.identity.phone_count} phone(s)
                  {' · '}audit_at <code>{c.audit_at}</code>
                </div>
              </div>

              <div className="s-card">
                <h3>Steps ({c.steps.length})</h3>
                {c.steps.length === 0 && <p className="s-muted">No steps: nothing to report for this case.</p>}
                {PHASES.map((ph) => {
                  const rows = c.steps.filter((s) => s.phase === ph)
                  if (!rows.length) return null
                  return (
                    <div className="cd-phase" key={ph}>
                      <b>{ph}</b>
                      <ol className="cd-steps" style={{ listStyle: 'none' }}>
                        {rows.map((s) => (
                          <li key={s.step_no}>
                            <span className="no">{s.step_no}</span>
                            <div className="meta">
                              <code>{s.operation}</code>
                              <span>{s.system_id} / {s.resource_id}</span>
                              <span className="chip plain">{s.state}</span>
                              {s.evidence_id ? <span className="chip plain ev">{s.evidence_id}</span> : <span className="s-muted">planned</span>}
                            </div>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )
                })}
              </div>

              <div className="s-card"><Timeline runId={runId} caseId={caseId} /></div>

              <div className="s-card">
                <h3>Gate trail: warnings and failures</h3>
                {trail.length === 0 ? <p className="s-muted">All gates passed for this case.</p> : (
                  <ul style={{ paddingLeft: 18, margin: '6px 0 0' }}>
                    {trail.map((e, i) => (
                      <li key={i}>
                        <span className={`chip ${e.verdict === 'FAIL' ? 'red' : 'amber'}`}>{e.verdict}</span>{' '}
                        <code>{e.stage}/{e.gate}</code> {e.summary}{' '}
                        {e.evidence_ids.map((id) => <span key={id} className="chip plain ev">{id}</span>)}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )
        }}
      </Gate>
    </section>
  )
}
