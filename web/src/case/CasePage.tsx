// Case page (#/cases/<id>): header, ranked evidence chain, resurrection timeline, identity graph, gate trail.
import { useMemo, useState } from 'react'
import { Button, Card, EmptyState, Icon, Skeleton, StatusBadge } from '../ui'
import { applyFilter, GhostMark, isGhost, ReportedBadge } from './CaseList'
import EvidenceChain from './EvidenceChain'
import Timeline from '../screens/Timeline'
import IdentityGraph from '../screens/IdentityGraph'
import { caseNum, fmtDate, getCaseDetail, getCaseList, useLoad } from '../caseApi'
import { href } from '../shell/router'
import type { CaseFilter } from '../types'

const Arrow = () => (
  <svg className="cp-arrow" width="28" height="20" viewBox="0 0 28 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="audited as" role="img"><path d="M3 10h20m-6-6l6 6-6 6" /></svg>
)

export default function CasePage({ runId, caseId, filter, setCaseId }: {
  runId: string | null; caseId: string; filter: CaseFilter; setCaseId: (id: string | null) => void
}) {
  const [sel, setSel] = useState<string | null>(null)
  const [d, reload] = useLoad(() => (runId ? getCaseDetail(runId, caseId) : Promise.reject(new Error('No run selected'))), [runId, caseId])
  const [list] = useLoad(() => (runId ? getCaseList(runId) : Promise.resolve([])), [runId])
  const nb = useMemo(() => {
    if (list.state !== 'ok') return { prev: null as string | null, next: null as string | null }
    const ids = applyFilter(list.data, filter).map((c) => c.case_id).sort((x, y) => caseNum(x) - caseNum(y))
    const i = ids.indexOf(caseId)
    // when the open case is outside the active filter, fall back to its numeric neighbours in the full list
    const base = i >= 0 ? ids : list.data.map((c) => c.case_id).sort((x, y) => caseNum(x) - caseNum(y))
    const j = i >= 0 ? i : base.indexOf(caseId)
    return { prev: j > 0 ? base[j - 1] : null, next: j >= 0 && j < base.length - 1 ? base[j + 1] : null }
  }, [list, filter, caseId])

  const back = <Button variant="ghost" href={href('cases')}>Back to cases</Button>

  if (d.state === 'loading') return <div className="stack" role="status" aria-label="Loading case"><Skeleton h={28} w="30%" /><Skeleton h={120} /><Skeleton h={220} /></div>
  if (d.state === 'error') {
    return (
      <div className="stack">
        <div className="cp-nav">{back}</div>
        {d.status === 404
          ? <EmptyState icon="search" title="Case not found" text={`${caseId} is not part of this run. Pick it from the list, or switch to another run in the top bar.`} />
          : <EmptyState icon="warn" title="Could not load this case" text={d.error} action={<Button variant="secondary" onClick={reload}>Retry</Button>} />}
      </div>
    )
  }
  const c = d.data
  const ghost = isGhost(c)
  const trail = c.trail.filter((e) => e.verdict && e.verdict !== 'PASS')
  const dates = [['Requested', c.requested_at], ['Reported', c.reported_at], ['Audit_at (cutoff)', c.audit_at]] as const

  return (
    <div className="stack cp">
      <div className="cp-nav">
        {back}
        <span className="cp-pn">
          <Button variant="secondary" disabled={!nb.prev} onClick={() => nb.prev && setCaseId(nb.prev)} aria-label={nb.prev ? `Previous case ${nb.prev}` : 'No previous case'}>Previous</Button>
          <Button variant="secondary" disabled={!nb.next} onClick={() => nb.next && setCaseId(nb.next)} aria-label={nb.next ? `Next case ${nb.next}` : 'No next case'}>Next</Button>
        </span>
      </div>

      <Card as="section" tone={ghost ? 'warn' : 'neutral'} className={ghost ? 'cp-head is-ghost' : 'cp-head'}>
        <div className="cp-title">
          <h1>{c.case_id}</h1>
          <span className="cp-pair"><span className="muted">Reported</span><ReportedBadge r={c.reported} /><Arrow /><span className="muted">Audited</span><StatusBadge status={c.status} /></span>
          {ghost && <GhostMark />}
        </div>
        {ghost && (
          <p className="cp-callout" role="note"><Icon name="eye" size={18} /><span><strong>Ghost data.</strong> The workflow reported this deletion COMPLETE, but at audit_at the evidence shows it is still INCOMPLETE.</span></p>
        )}
        <dl className="cp-dates">
          {dates.map(([k, v], i) => <div key={k} className={i === 2 ? 'is-audit' : ''}><dt><Icon name="clock" size={14} /> {k}</dt><dd>{fmtDate(v)}</dd></div>)}
        </dl>
        <div className="cp-meta">
          <span className="cp-chip"><Icon name="search" size={14} />Intent <strong>{c.intent.label}</strong> <span className="muted">via {c.intent.source}</span></span>
          {c.intent.flags.map((f) => (
            f === 'injection_marker'
              ? <span key={f} className="cp-chip is-bad"><Icon name="warn" size={14} />Injection marker</span>
              : <span key={f} className="cp-chip">{f}</span>
          ))}
          <span className="cp-chip"><Icon name="user" size={14} />User <code>{c.identity.user_id}</code> <span className="muted">{c.identity.email_count} email{c.identity.email_count === 1 ? '' : 's'}, {c.identity.phone_count} phone{c.identity.phone_count === 1 ? '' : 's'}</span></span>
        </div>
      </Card>

      {runId && <EvidenceChain runId={runId} caseId={caseId} status={c.status} sel={sel} onSel={setSel} />}
      {runId && <Card as="section"><Timeline runId={runId} caseId={caseId} sel={sel} onSel={setSel} /></Card>}
      {runId && <Card as="section"><IdentityGraph runId={runId} caseId={caseId} /></Card>}

      <Card as="section" title="Gate trail: warnings and failures">
        {trail.length === 0 ? <p className="muted">All gates passed for this case.</p> : (
          <ul className="cp-trail">
            {trail.map((e, i) => (
              <li key={i}>
                <StatusBadge status={e.verdict ?? 'WARN'} />
                <code>{e.stage}{e.gate ? `/${e.gate}` : ''}</code>
                <span>{e.summary}</span>
                {(e.evidence_ids ?? []).map((id) => <code key={id} className="cp-ev">{id}</code>)}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
