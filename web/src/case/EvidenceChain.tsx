/*
 * EvidenceChain: ranked, colour-coded evidence for one case (data: GET .../evidence).
 * Props: { runId, caseId, status?, sel, onSel }   sel = highlighted evidence id (shared with the timeline on the Case page)
 * Tier colour is always paired with a letter, and X (future) is dashed, D (late) is hatched.
 */
import { useMemo, useState } from 'react'
import { Button, Card, EmptyState, EvidenceChip, Icon, Legend, Segmented, Skeleton, TIERS, Tooltip } from '../ui'
import { fmtDate, getEvidence, humanOp, useLoad } from '../caseApi'
import type { ChainStep, EvidenceData, RankRow, TierLetter } from '../caseApi'
import './evidence.css'

const ORDER: TierLetter[] = ['A', 'B', 'C', 'D', 'X']
const PHASES: ChainStep['phase'][] = ['FINDING', 'REMEDIATION', 'VERIFICATION']
const TOP = 12

export const TierSwatch = ({ tier }: { tier: TierLetter }) => <span className={`ec-sw t-${tier.toLowerCase()}`}>{tier}</span>

const Arrow = () => (
  <span className="ec-arrow" aria-hidden="true">
    <svg width="28" height="20" viewBox="0 0 28 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 10h20m-6-6l6 6-6 6" /></svg>
  </span>
)

function reason(r: RankRow): string {
  if (r.tier === 'C') return 'Claim only, never cited'
  if (r.tier === 'D') return 'Captured after audit_at, discovery only'
  return r.used_by_steps.length ? `Cited by step${r.used_by_steps.length > 1 ? 's' : ''} ${r.used_by_steps.join(', ')}` : 'Citable, not cited by any step'
}

function Node({ s, sel, onSel }: { s: ChainStep; sel: string | null; onSel: (id: string | null) => void }) {
  const on = !!s.evidence_id && s.evidence_id === sel
  const tip = (
    <>
      <span className="tt-title">Step {s.step_no}: {humanOp(s.operation)}</span>
      <span className="tt-row">{s.why}</span>
      <span className="tt-row"><b>Captured</b> {fmtDate(s.captured_at)}</span>
      <span className="tt-row"><b>Observed</b> {fmtDate(s.observed_at)}</span>
      <span className="tt-row"><b>Citable at audit_at</b> {s.tier === 'X' ? 'not applicable (future step)' : s.citable ? 'yes' : 'no'}</span>
    </>
  )
  return (
    <li className={`ec-node t-${s.tier.toLowerCase()} ${on ? 'is-sel' : ''} ${s.tier === 'X' ? 'is-future' : ''}`}>
      <Tooltip content={tip}>
        <button type="button" className="ec-node-btn" aria-pressed={s.evidence_id ? on : undefined} onClick={() => s.evidence_id && onSel(on ? null : s.evidence_id)}>
          <span className="ec-no">{s.step_no}</span>
          <span className="ec-op">{humanOp(s.operation)}</span>
          <span className="ec-state">{s.state}{s.tier === 'X' ? ' (planned)' : ''}</span>
        </button>
      </Tooltip>
      <EvidenceChip id={s.evidence_id} tier={s.tier} score={s.tier === 'X' ? undefined : s.score} />
    </li>
  )
}

function Chain({ chain, sel, onSel }: { chain: ChainStep[]; sel: string | null; onSel: (id: string | null) => void }) {
  const lanes = useMemo(() => {
    const m = new Map<string, ChainStep[]>()
    for (const s of chain) { const k = `${s.system_id} / ${s.resource_id}`; m.set(k, [...(m.get(k) ?? []), s]) }
    return [...m.entries()]
  }, [chain])
  return (
    <div className="ec-chain">
      <div className="ec-flow ec-phases" aria-hidden="true">
        {PHASES.map((p, i) => <span key={p} style={{ display: 'contents' }}><span className="ec-phase-h">{i + 1}. {p}</span>{i < 2 && <span />}</span>)}
      </div>
      {lanes.map(([key, steps]) => {
        const [sys, res] = [steps[0].system_id, steps[0].resource_id]
        return (
          <section className="ec-lane" key={key} aria-label={`Resource ${key}`}>
            <h4 className="ec-lane-title"><Icon name="database" size={16} /><span>{sys}</span><code>{res}</code></h4>
            <div className="ec-flow">
              {PHASES.map((p, i) => {
                const cell = steps.filter((s) => s.phase === p)
                return (
                  <span key={p} style={{ display: 'contents' }}>
                    <div className="ec-cell">
                      <span className="ec-cell-ph">{p}</span>
                      {cell.length ? <ol className="ec-nodes">{cell.map((s) => <Node key={s.step_no} s={s} sel={sel} onSel={onSel} />)}</ol> : <span className="ec-none muted">none</span>}
                    </div>
                    {i < 2 && <Arrow />}
                  </span>
                )
              })}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function Ranking({ ranking, sel, onSel }: { ranking: RankRow[]; sel: string | null; onSel: (id: string | null) => void }) {
  const [tf, setTf] = useState<TierLetter | 'all'>('all')
  const [all, setAll] = useState(false)
  const counts = useMemo(() => { const c: Partial<Record<TierLetter, number>> = {}; ranking.forEach((r) => { c[r.tier] = (c[r.tier] ?? 0) + 1 }); return c }, [ranking])
  const rows = ranking.map((r, i) => ({ r, rank: i + 1 })).filter((x) => tf === 'all' || x.r.tier === tf)
  const shown = all ? rows : rows.slice(0, TOP)
  if (!ranking.length) return <p className="muted">No evidence items are linked to this case.</p>
  return (
    <>
      <div className="ec-filters" role="group" aria-label="Filter ranking by tier">
        <button type="button" className="ec-fchip" aria-pressed={tf === 'all'} onClick={() => setTf('all')}>All <b>{ranking.length}</b></button>
        {ORDER.filter((t) => counts[t]).map((t) => (
          <button type="button" key={t} className={`ec-fchip t-${t.toLowerCase()}`} aria-pressed={tf === t} onClick={() => setTf(t)}><TierSwatch tier={t} /> {TIERS[t].label} <b>{counts[t]}</b></button>
        ))}
      </div>
      <ol className="ec-rank">
        {shown.map(({ r, rank }) => {
          const on = r.evidence_id === sel
          return (
            <li key={r.evidence_id} className={`ec-rank-row t-${r.tier.toLowerCase()} ${on ? 'is-sel' : ''}`}>
              <span className="ec-rank-no" aria-label={`Rank ${rank}`}>{rank}</span>
              <EvidenceChip id={r.evidence_id} tier={r.tier} score={r.score} />
              <span className="ec-bar" role="img" aria-label={`Score ${r.score} of 100`}><i style={{ width: `${r.score}%` }} /></span>
              <span className="ec-reason">{reason(r)}</span>
              <Button variant="ghost" className="ec-hl" aria-pressed={on} icon="eye" onClick={() => onSel(on ? null : r.evidence_id)}>{on ? 'Highlighted' : 'Highlight'}</Button>
            </li>
          )
        })}
      </ol>
      {rows.length > TOP && <Button variant="ghost" onClick={() => setAll(!all)}>{all ? `Show top ${TOP}` : `Show all ${rows.length}`}</Button>}
      {!rows.length && <p className="muted">No items in this tier.</p>}
    </>
  )
}

function Tables({ d, sel, onSel }: { d: EvidenceData; sel: string | null; onSel: (id: string | null) => void }) {
  return (
    <div className="ec-tables">
      <div className="ec-tw"><table>
        <caption>Steps and the evidence behind each one</caption>
        <thead><tr><th scope="col">Step</th><th scope="col">Phase</th><th scope="col">System / resource</th><th scope="col">Operation</th><th scope="col">State</th><th scope="col">Evidence</th><th scope="col">Tier</th><th scope="col">Score</th><th scope="col">Citable</th><th scope="col">Why</th></tr></thead>
        <tbody>{d.chain.map((s) => (
          <tr key={s.step_no} className={s.evidence_id && s.evidence_id === sel ? 'is-sel' : ''}>
            <td>{s.step_no}</td><td>{s.phase}</td><td>{s.system_id} / <code>{s.resource_id}</code></td><td>{humanOp(s.operation)}</td><td>{s.state}</td>
            <td>{s.evidence_id ? <button type="button" className="ec-link" onClick={() => onSel(s.evidence_id === sel ? null : s.evidence_id)}><code>{s.evidence_id}</code></button> : <span className="muted">planned</span>}</td>
            <td><TierSwatch tier={s.tier} /> {s.tier_label}</td><td>{s.tier === 'X' ? 'n/a' : s.score}</td><td>{s.tier === 'X' ? 'n/a' : s.citable ? 'yes' : 'no'}</td><td>{s.why}</td>
          </tr>))}</tbody>
      </table></div>
      <div className="ec-tw"><table>
        <caption>Evidence ranking (highest score first)</caption>
        <thead><tr><th scope="col">Rank</th><th scope="col">Evidence</th><th scope="col">Tier</th><th scope="col">Score</th><th scope="col">Used by steps</th><th scope="col">Note</th></tr></thead>
        <tbody>{d.ranking.map((r, i) => (
          <tr key={r.evidence_id} className={r.evidence_id === sel ? 'is-sel' : ''}>
            <td>{i + 1}</td>
            <td><button type="button" className="ec-link" onClick={() => onSel(r.evidence_id === sel ? null : r.evidence_id)}><code>{r.evidence_id}</code></button></td>
            <td><TierSwatch tier={r.tier} /> {TIERS[r.tier].label}</td><td>{r.score}</td><td>{r.used_by_steps.join(', ') || 'none'}</td><td>{reason(r)}</td>
          </tr>))}</tbody>
      </table></div>
    </div>
  )
}

export default function EvidenceChain({ runId, caseId, status, sel, onSel }: {
  runId: string; caseId: string; status?: string; sel: string | null; onSel: (id: string | null) => void
}) {
  const [a, reload] = useLoad(() => getEvidence(runId, caseId), [runId, caseId])
  const [view, setView] = useState<'chain' | 'table'>('chain')
  const actions = a.state === 'ok' && a.data.chain.length > 0
    ? <Segmented<'chain' | 'table'> label="Evidence view" value={view} onChange={setView} options={[{ value: 'chain', label: 'Chain' }, { value: 'table', label: 'View as table' }]} />
    : undefined

  return (
    <Card as="section" title="Evidence chain" actions={actions} className="ec">
      {a.state === 'loading' && <div className="ec-skel" role="status" aria-label="Loading evidence chain"><Skeleton h={34} /><Skeleton h={90} /><Skeleton h={90} /></div>}
      {a.state === 'error' && (
        <EmptyState icon="warn" title={a.status === 404 ? 'No evidence chain for this case' : 'Could not load the evidence chain'}
          text={a.status === 404 ? 'The API does not know this case in the selected run.' : a.error}
          action={a.status === 404 ? undefined : <Button variant="secondary" onClick={reload}>Retry</Button>} />
      )}
      {a.state === 'ok' && !a.data.chain.length && (
        <EmptyState icon="info" title="No steps, so no evidence chain"
          text={status === 'NOT_APPLICABLE'
            ? 'This request did not authorise deletion, so the audit produced no findings, remediation or verification steps.'
            : 'The audit produced no steps for this case. Evidence items that are linked to it, if any, are ranked below.'} />
      )}
      {a.state === 'ok' && (a.data.chain.length > 0 || a.data.ranking.length > 0) && (
        <div className="ec-body">
          {a.data.chain.length > 0 && <TierBar summary={a.data.summary} total={a.data.chain.length} />}
          <Legend label="Evidence tiers" items={ORDER.map((t) => ({ swatch: <TierSwatch tier={t} />, label: `${t} ${TIERS[t].label}`, description: TIERS[t].text }))} />
          {a.data.chain.length > 0 && (view === 'chain'
            ? <><h3 className="ec-h">The chain <span className="muted">(per resource, left to right)</span></h3><Chain chain={a.data.chain} sel={sel} onSel={onSel} /></>
            : null)}
          {view === 'table' && a.data.chain.length > 0
            ? <Tables d={a.data} sel={sel} onSel={onSel} />
            : <><h3 className="ec-h">Ranking <span className="muted">(score = tier base minus recency penalty)</span></h3><Ranking ranking={a.data.ranking} sel={sel} onSel={onSel} /></>}
        </div>
      )}
    </Card>
  )
}

function TierBar({ summary, total }: { summary: Record<TierLetter, number>; total: number }) {
  const label = ORDER.map((t) => `${summary[t] ?? 0} tier ${t}`).join(', ')
  return (
    <div>
      <p className="ec-bar-cap muted">Steps by evidence tier ({total} total)</p>
      <div className="ec-sum" role="img" aria-label={`Steps by evidence tier: ${label}`}>
        {ORDER.filter((t) => summary[t] > 0).map((t) => (
          <span key={t} className={`ec-seg t-${t.toLowerCase()}`} style={{ flex: `${summary[t]} 1 56px` }}><TierSwatch tier={t} /> {summary[t]}</span>
        ))}
      </div>
    </div>
  )
}
