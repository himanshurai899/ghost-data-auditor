// Dashboard (#/dashboard): the selected run at a glance. Data: GET /api/dashboard (web/src/metricsApi.ts); no invented numbers.
import { useCallback } from 'react'
import { Card, EmptyState, EvidenceChip, Button, Legend, PageHeader, Skeleton, StatCard, StatusBadge, TIERS, Tooltip } from '../ui'
import { BarList, Donut, GateStrip, Ring, Sparkline, StackedBar } from '../charts'
import type { Seg } from '../charts'
import { getDashboard, human, num, secs, useLoad } from '../metricsApi'
import type { DashboardData } from '../metricsApi'
import type { Reported, ScreenProps, Status } from '../types'
import './dashboard.css'

const STATUSES: Status[] = ['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE']
const REPORTED: Reported[] = ['COMPLETE', 'PARTIALLY_COMPLETE', 'NOT_STARTED']
const SLABEL: Record<Status, string> = { COMPLETE: 'Complete', INCOMPLETE: 'Incomplete', NOT_APPLICABLE: 'Not applicable' }
const RLABEL: Record<Reported, string> = { COMPLETE: 'Reported complete', PARTIALLY_COMPLETE: 'Reported partial', NOT_STARTED: 'Reported not started' }
const SCOLOR: Record<Status, string> = { COMPLETE: 'var(--ok)', INCOMPLETE: 'var(--bad)', NOT_APPLICABLE: 'var(--border-strong)' }
const TCOLOR = { A: 'var(--ev-a)', B: 'var(--ev-b)', C: 'var(--ev-c)', D: 'var(--ev-d)' } as const
const PAT = { A: 0, B: 1, C: 2, D: 3 } as const
const FAMS = [
  { key: 'records', label: 'Remaining records', color: 'var(--bad)', pattern: 0 },
  { key: 'pii', label: 'Exposed PII', color: 'var(--warn)', pattern: 1 },
  { key: 'flows', label: 'Active data flows', color: 'var(--primary-text)', pattern: 2 },
  { key: 'restores', label: 'Restore risks', color: 'var(--ghost)', pattern: 3 },
] as const

function Ghost({ d, onOpen }: { d: DashboardData; onOpen: (r: Reported, s: Status) => void }) {
  const g = d.ghosts
  const max = Math.max(1, ...REPORTED.flatMap((r) => STATUSES.map((s) => d.claim_matrix.reported[r][s])))
  return (
    <Card title="Claim vs truth" actions={<span className="muted db-sm">Rows: what the workflow reported. Columns: what the audit found.</span>}>
      <div className="db-claim">
        <div className="tablewrap">
          <table className="db-heat">
            <caption className="sr">Reported status (rows) against audited status (columns), number of cases. Each cell opens the Cases list with that filter.</caption>
            <thead><tr><th scope="col"><span className="sr">Reported</span></th>{STATUSES.map((s) => <th key={s} scope="col">{SLABEL[s]}</th>)}</tr></thead>
            <tbody>
              {REPORTED.map((r) => (
                <tr key={r}>
                  <th scope="row">{RLABEL[r]}</th>
                  {STATUSES.map((s) => {
                    const n = d.claim_matrix.reported[r][s]
                    const ghost = r === 'COMPLETE' && s === 'INCOMPLETE'
                    return (
                      <td key={s}>
                        <Tooltip content={ghost ? 'Ghost data: the workflow said Complete but the audit found data remaining.' : `${RLABEL[r]} and audited ${SLABEL[s].toLowerCase()}: ${n} cases. Click to list them.`}>
                          <button type="button" className={`db-cell ${ghost ? 'is-ghost' : ''}`} style={{ ['--i' as string]: Math.round((100 * n) / max) }}
                            aria-label={`${RLABEL[r]}, audited ${SLABEL[s]}: ${n} cases${ghost ? ', ghost cell' : ''}`} onClick={() => onOpen(r, s)}>
                            <span className="db-cell-n">{num(n)}</span>
                            {ghost && <span className="db-cell-tag">Ghost</span>}
                          </button>
                        </Tooltip>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="db-meter">
          {g.pct === null ? (
            <p className="muted">n/a: no case in this run was reported Complete, so there is nothing to compare.</p>
          ) : (
            <>
              <Ring value={g.pct} color="var(--ghost)" center={`${g.pct}%`} label={`Ghost meter: ${g.count} of ${g.of} reported-complete cases are incomplete (${g.pct}%)`} />
              <p><strong>{num(g.count)}</strong> of <strong>{num(g.of)}</strong> cases reported Complete still hold data.</p>
            </>
          )}
        </div>
      </div>
    </Card>
  )
}

export default function Dashboard(p: ScreenProps) {
  const fn = useCallback(getDashboard, [])
  const { data: d, error, loading, reload } = useLoad(fn, p.runId)
  const run = <Button variant="primary" icon="play" loading={p.starting} onClick={() => void p.startAudit()}>Run audit</Button>
  const head = <PageHeader title="Dashboard" subtitle={d ? <>Run <code>{d.run_id}</code>. Switch runs with the selector in the top bar.</> : 'The selected run at a glance.'} actions={run} />

  if (!p.runId && p.runs.length === 0) {
    return <div className="stack">{head}<EmptyState icon="chart" title="No audit runs yet" text="Run the audit once to fill this dashboard: status mix, ghosts, findings, evidence quality and gate health." action={run} /></div>
  }
  if (error) {
    return <div className="stack">{head}<EmptyState icon="warn" title="Could not load the dashboard" text={error} action={<Button onClick={reload}>Retry</Button>} /></div>
  }
  if (loading || !d) {
    return (
      <div className="stack" aria-busy="true">
        {head}
        <div className="grid-auto">{[0, 1, 2, 3, 4].map((i) => <StatCard key={i} label="Loading" value="" loading />)}</div>
        <div className="db-grid">{[0, 1, 2, 3].map((i) => <Card key={i}><Skeleton h={22} w="40%" /><div style={{ height: 12 }} /><Skeleton h={150} /></Card>)}</div>
      </div>
    )
  }

  const total = d.cases
  const inc = d.counts.INCOMPLETE
  const prev = d.runs.find((r) => r.run_id !== d.run_id && r.cases === d.cases && r.strict_temporal === (d.runs.find((x) => x.run_id === d.run_id)?.strict_temporal))
  const cur = d.runs.find((r) => r.run_id === d.run_id)
  const determinism = !cur || !prev ? null : prev.output_sha256 === cur.output_sha256
  const openCases = (r: Reported, s: Status) => { p.setFilter({ reported: r, status: s }); p.go('cases') }

  const status: Seg[] = STATUSES.map((s, i) => ({ key: s, label: SLABEL[s], value: d.counts[s], color: SCOLOR[s], pattern: ([0, 1, 2] as const)[i], onClick: () => { p.setFilter({ status: s }); p.go('cases') }, hint: 'Click to list these cases.' }))
  const sys = [...d.findings_by_system].sort((a, b) => b.records + b.pii + b.flows + b.restores - (a.records + a.pii + a.flows + a.restores))
  const mixTotal = d.evidence_mix.A + d.evidence_mix.B + d.evidence_mix.C + d.evidence_mix.D
  const mix: Seg[] = (['A', 'B', 'C', 'D'] as const).map((t) => ({ key: t, label: `${t} ${TIERS[t].label}`, value: d.evidence_mix[t], color: TCOLOR[t], pattern: PAT[t], hint: TIERS[t].text }))
  const aShare = mixTotal ? Math.round((1000 * d.evidence_mix.A) / mixTotal) / 10 : null

  return (
    <div className="stack">
      {head}
      <div className="grid-auto">
        <StatCard label="Cases audited" value={num(total)} icon="file" sub={<>in run <code>{d.run_id.slice(0, 16)}</code></>} />
        <StatCard label="Incomplete" tone="bad" icon="warn" value={total ? `${Math.round((1000 * inc) / total) / 10}%` : 'n/a'} sub={`${num(inc)} of ${num(total)} cases`} />
        <StatCard label="Ghosts found" tone="primary" icon="eye" value={num(d.ghosts.count)} sub={`of ${num(d.ghosts.of)} reported-complete${d.ghosts.pct !== null ? ` (${d.ghosts.pct}%)` : ''}`} />
        <StatCard label="Runtime model calls" icon="cog" value="0" sub={<>Offline run is deterministic code. <a href="#/cost">See cost</a></>} />
        <StatCard label="Determinism" icon="check" tone={determinism === false ? 'warn' : determinism ? 'ok' : 'neutral'}
          value={determinism === null ? 'n/a' : determinism ? 'Match' : 'Differs'}
          sub={determinism === null ? 'No earlier run with the same case count and temporal mode to compare.' : <>output hash vs run <code>{prev?.run_id.slice(0, 16)}</code></>} />
      </div>

      <div className="db-grid">
        <Card title="Status mix">
          <Donut label="Audited status of all cases" segments={status} center={{ value: num(total), label: 'cases' }}
            tableAlt={{ caption: 'Audited status counts', columns: ['Status', 'Cases', 'Share'], rows: STATUSES.map((s) => [SLABEL[s], d.counts[s], total ? `${Math.round((1000 * d.counts[s]) / total) / 10}%` : 'n/a']) }} />
        </Card>
        <Card title="Gate health" actions={<span className="muted db-sm">pass / warn / fail checks</span>}>
          {d.gates.length ? <GateStrip gates={d.gates} /> : <p className="muted">n/a: this run recorded no gate events.</p>}
        </Card>
      </div>

      <Ghost d={d} onOpen={openCases} />

      <div className="db-grid">
        <Card title="Findings by system">
          {sys.length ? (
            <>
              <BarList label="Findings per system, split by finding type" rows={sys.map((s) => ({ key: s.system_id, label: human(s.system_id), parts: FAMS.map((f) => ({ key: f.key, label: f.label, value: s[f.key], color: f.color, pattern: f.pattern })) }))}
                tableAlt={{ caption: 'Findings per system', columns: ['System', ...FAMS.map((f) => f.label)], rows: sys.map((s) => [human(s.system_id), ...FAMS.map((f) => s[f.key])]) }} />
              <Legend label="Finding types" items={FAMS.map((f) => ({ swatch: <span className={`ch-sw pat-${f.pattern}`} style={{ ['--c' as string]: f.color }} />, label: f.label }))} />
            </>
          ) : <p className="muted">No findings: this run has no incomplete cases.</p>}
        </Card>
        <Card title="Evidence quality">
          <StackedBar label="Evidence cited by tier" segments={mix}
            tableAlt={{ caption: 'Evidence by tier', columns: ['Tier', 'Items', 'Meaning'], rows: (['A', 'B', 'C', 'D'] as const).map((t) => [`${t} ${TIERS[t].label}`, d.evidence_mix[t], TIERS[t].text]) }} />
          <div className="row db-chips">{(['A', 'B', 'C', 'D'] as const).map((t) => <EvidenceChip key={t} id={TIERS[t].label} tier={t} />)}</div>
          <p className="muted db-sm">
            {aShare === null ? 'n/a: no evidence cited in this run.' : <>{aShare}% of the evidence is tier A (a direct file row at or before audit time). A high share of A means findings rest on files you can open, not on workflow claims. Tier D is late discovery-only evidence and is never cited.</>}
          </p>
        </Card>
      </div>

      <Card title="Run history" actions={<span className="muted db-sm">newest first</span>}>
        <div className="db-hist">
          <Sparkline label="Incomplete cases per run, oldest to newest" height={48}
            values={[...d.runs].reverse().map((r) => r.counts.INCOMPLETE)} />
          <span className="muted db-sm">Incomplete cases per run, oldest left, newest right.</span>
        </div>
        <div className="tablewrap">
          <table>
            <thead><tr><th>Run</th><th>Started</th><th>Cases</th><th>Complete</th><th>Incomplete</th><th>N/A</th><th>Hash</th><th>Strict</th><th>Duration</th></tr></thead>
            <tbody>
              {d.runs.map((r) => (
                <tr key={r.run_id} className={r.run_id === d.run_id ? 'db-cur' : ''}>
                  <td><code>{r.run_id}</code>{r.run_id === d.run_id && <> <StatusBadge status="PASS" label="Selected" /></>}</td>
                  <td>{r.started.slice(0, 16).replace('T', ' ')}</td><td>{num(r.cases)}</td>
                  <td>{num(r.counts.COMPLETE)}</td><td>{num(r.counts.INCOMPLETE)}</td><td>{num(r.counts.NOT_APPLICABLE)}</td>
                  <td><code>{r.output_sha256.slice(0, 8)}</code></td><td>{r.strict_temporal ? 'Yes' : 'No'}</td><td>{secs(r.duration_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
