// Landing page: hero + live KPIs, the horizontal pipeline (stages S0-S8, gates G1-G7 as tooltip cards), legends and tables.
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { getRun, getRuns, getUsage, health } from '../api'
import type { RunDetail, ScreenProps, Usage } from '../types'
import { Button, Card, EmptyState, Icon, Legend, StatCard, StatusBadge, Tooltip } from '../ui'
import { GATES, STAGES } from './pipelineData'
import type { Gate, Stage } from './pipelineData'
import './landing.css'

type Kpi = { state: 'loading' } | { state: 'empty' } | { state: 'error' } | { state: 'ready'; run: RunDetail; usage: Usage | null }

function useLatestRun(): Kpi {
  const [k, setK] = useState<Kpi>({ state: 'loading' })
  useEffect(() => {
    let live = true
    ;(async () => {
      try {
        await health()
        const runs = await getRuns()
        if (!live) return
        if (runs.length === 0) { setK({ state: 'empty' }); return }
        const [run, usage] = await Promise.all([getRun(runs[0].run_id), getUsage(runs[0].run_id).catch(() => null)])
        if (live) setK({ state: 'ready', run, usage })
      } catch { if (live) setK({ state: 'error' }) }
    })()
    return () => { live = false }
  }, [])
  return k
}

const Row = ({ label, children }: { label: string; children: ReactNode }) => <span className="tt-row"><b>{label}</b> {children}</span>

function stageTip(s: Stage) {
  return (
    <>
      <span className="tt-title">{s.id} {s.name}</span>
      {s.purpose}
      <Row label="Input to output:">{s.io}</Row>
      <Row label="Implemented by:"><code>{s.module}</code></Row>
      <Row label="Kind:">{s.llm ? `Model at the edge. ${s.llm}` : 'Deterministic code, no model.'}</Row>
    </>
  )
}
function gateTip(g: Gate) {
  return (
    <>
      <span className="tt-title">{g.id} {g.name} gate ({g.level}-level)</span>
      <Row label="Runs after:">{g.after}</Row>
      <Row label="Checks:">{g.check}</Row>
      <Row label="On failure:">{g.onFail}</Row>
      <Row label="Implemented by:"><code>{g.module}</code></Row>
    </>
  )
}

function Pipeline() {
  const track = useRef<HTMLOListElement>(null)
  const [edge, setEdge] = useState({ start: true, end: false })
  const measure = () => {
    const t = track.current
    if (t) setEdge({ start: t.scrollLeft < 8, end: t.scrollLeft + t.clientWidth >= t.scrollWidth - 8 })
  }
  useEffect(() => { measure(); window.addEventListener('resize', measure); return () => window.removeEventListener('resize', measure) }, [])
  const by = (dir: number) => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    track.current?.scrollBy({ left: dir * Math.max(240, (track.current?.clientWidth ?? 600) * 0.7), behavior: reduce ? 'auto' : 'smooth' })
  }
  const gateAfter = (id: string) => GATES.find((g) => g.after.startsWith(`${id} `))
  return (
    <section aria-labelledby="pl-h" className="pl-section">
      <div className="pl-head">
        <div>
          <h2 id="pl-h">The audit pipeline</h2>
          <p className="muted">Nine stages, seven gates. Hover, focus or tap any stage or gate for what it does, what it checks and what happens when it fails.</p>
        </div>
        <div className="row" role="group" aria-label="Scroll the pipeline">
          <Button variant="secondary" aria-label="Scroll pipeline left" disabled={edge.start} onClick={() => by(-1)}><span className="flip"><Icon name="play" size={16} /></span></Button>
          <Button variant="secondary" aria-label="Scroll pipeline right" disabled={edge.end} onClick={() => by(1)}><Icon name="play" size={16} /></Button>
        </div>
      </div>
      <div className={`pl-frame ${edge.start ? '' : 'has-left'} ${edge.end ? '' : 'has-right'}`}>
        <ol className="pl-track" ref={track} onScroll={measure} tabIndex={0} aria-label="Pipeline stages and gates, scroll horizontally">
          {STAGES.map((s) => {
            const g = gateAfter(s.id)
            const last = s.id === 'S8'
            return (
              <li key={s.id} className="pl-item">
                <Tooltip content={stageTip(s)} placement="bottom">
                  <button type="button" className={`pl-node ${s.llm ? 'is-llm' : ''}`}>
                    <span className="pl-id">{s.id}</span>
                    <Icon name={s.icon} size={22} />
                    <span className="pl-name">{s.name}</span>
                    {s.llm ? <span className="pl-tag">LLM edge</span> : <span className="pl-tag is-code">code</span>}
                  </button>
                </Tooltip>
                <div className={`pl-link ${g ? 'has-gate' : ''}`}>
                  {g && (
                    <Tooltip content={gateTip(g)} placement="bottom">
                      <button type="button" className="pl-gate" aria-label={`Gate ${g.id} ${g.name}`}>{g.id}</button>
                    </Tooltip>
                  )}
                </div>
                {last && <span className="pl-end"><Icon name="file" size={20} /><span>output.csv</span></span>}
              </li>
            )
          })}
        </ol>
      </div>
      <p className="pl-note muted">
        <span className="pl-sw is-llm" aria-hidden="true" /> A model is called only at the edges: reading image and PDF evidence, and the intent fallback (plus the Ask page).
        <span className="pl-sw" aria-hidden="true" /> Everything else is deterministic code, so the same input always gives the same <code>output.csv</code>.
        <span className="pl-gate-key" aria-hidden="true">G</span> A gate is a checkpoint between stages.
      </p>
    </section>
  )
}

const TIER_SW = (t: 'a' | 'b' | 'c' | 'd' | 'x', letter: string) => <span className={`ev-sw ev-sw-${t}`}>{letter}</span>

export default function Landing({ go, startAudit, starting }: ScreenProps) {
  const k = useLatestRun()
  const ready = k.state === 'ready'
  const matrix = ready ? k.run.claim_matrix?.reported : undefined
  const claimed = matrix ? Object.values(matrix.COMPLETE ?? {}).reduce((a, b) => a + b, 0) : 0
  const ghosts = matrix?.COMPLETE?.INCOMPLETE ?? 0
  const pct = claimed > 0 ? Math.round((ghosts / claimed) * 1000) / 10 : null
  const loading = k.state === 'loading'
  return (
    <div className="landing">
      <section className="hero" aria-labelledby="hero-h">
        <p className="hero-eyebrow"><Icon name="shield" size={16} /> Ghost Data Still Exists</p>
        <h1 id="hero-h">Ghost Audit Console</h1>
        <p className="hero-lead">Proves whether a deleted person&apos;s data is really gone, from evidence, not claims.</p>
        <div className="row">
          <Button variant="primary" icon="play" loading={starting} onClick={startAudit}>Run audit</Button>
          <Button variant="secondary" className="hero-alt" href="#/dashboard">Open dashboard</Button>
        </div>
      </section>

      <section aria-labelledby="kpi-h" className="kpi-section">
        <h2 id="kpi-h" className="sr">Latest run</h2>
        {k.state === 'empty' && <EmptyState icon="play" title="No audit run yet" text="Run the audit to see how many deletions only look complete." action={<Button variant="primary" icon="play" loading={starting} onClick={startAudit}>Run audit</Button>} />}
        {k.state === 'error' && <EmptyState icon="warn" title="Could not load the latest run" text="The API did not answer. Check that the console API is running on localhost, then reload." />}
        {(loading || ready) && (
          <>
            <p className="muted kpi-cap">{ready ? <>Latest run <code>{k.run.run_id}</code>{k.run.running ? ' (running)' : ''}</> : 'Loading latest run'}</p>
            <div className="grid-auto kpis">
              <StatCard label="Cases audited" value={ready ? k.run.cases.toLocaleString() : ''} icon="file" tone="primary" loading={loading} sub="requests in the run" />
              <StatCard label="Ghosts found" value={ready ? ghosts.toLocaleString() : ''} icon="warn" tone={ghosts > 0 ? 'bad' : 'ok'} loading={loading} sub="reported COMPLETE, still INCOMPLETE" />
              <StatCard label="Wrong COMPLETE claims" value={ready ? (pct === null ? 'n/a' : `${pct}%`) : ''} icon="chart" tone={pct ? 'warn' : 'neutral'} loading={loading} sub={ready ? `${ghosts} of ${claimed} COMPLETE claims` : undefined} />
              <StatCard label="Runtime model calls" value={ready ? (k.usage ? k.usage.calls.toLocaleString() : 'n/a') : ''} icon="cog" loading={loading} sub={ready && k.usage ? `${k.usage.cached} cached, billed $0` : 'usage not available'} />
            </div>
          </>
        )}
      </section>

      <Pipeline />

      <section aria-labelledby="how-h" className="how-section">
        <h2 id="how-h">How to read the result</h2>
        <div className="grid-auto how">
          <Card><span className="how-ic"><Icon name="eye" /></span><h3>Claim versus truth</h3><p className="muted">A workflow saying COMPLETE is only a claim. The audit rebuilds the state at <code>audit_at</code> from evidence; the gap between the two is a ghost.</p></Card>
          <Card><span className="how-ic"><Icon name="chart" /></span><h3>Evidence ranking</h3><p className="muted">Every cited id carries a tier (A direct, B inferred, C claim, D late, X none) and a score. Only tier A and B can prove a state.</p></Card>
          <Card><span className="how-ic"><Icon name="clock" /></span><h3>Audit trail</h3><p className="muted">Each stage and gate writes a trail event. Open a case to see why it got its status, step by step, with the evidence behind each finding.</p></Card>
        </div>
      </section>

      <section aria-labelledby="tab-h" className="tables-section">
        <h2 id="tab-h">Stages and gates, as tables</h2>
        <p className="muted">The same information as the tooltips above, for keyboards, screen readers and printing.</p>
        <Card flush className="tbl-card">
          <div className="tablewrap" tabIndex={0} role="region" aria-label="Stages table">
            <table>
              <caption className="sr">Pipeline stages</caption>
              <thead><tr><th scope="col">Stage</th><th scope="col">Purpose</th><th scope="col">Input to output</th><th scope="col">Kind</th><th scope="col">Module</th></tr></thead>
              <tbody>
                {STAGES.map((s) => (
                  <tr key={s.id}>
                    <th scope="row"><span className="mono">{s.id}</span> {s.name}</th>
                    <td>{s.purpose}</td><td>{s.io}</td>
                    <td>{s.llm ? <span className="kind is-llm">LLM edge</span> : <span className="kind">Code</span>}{s.llm && <span className="muted"> {s.llm}</span>}</td>
                    <td><code>{s.module}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card flush className="tbl-card">
          <div className="tablewrap" tabIndex={0} role="region" aria-label="Gates table">
            <table>
              <caption className="sr">Pipeline gates</caption>
              <thead><tr><th scope="col">Gate</th><th scope="col">After</th><th scope="col">Level</th><th scope="col">Checks</th><th scope="col">On failure</th><th scope="col">Module</th></tr></thead>
              <tbody>
                {GATES.map((g) => (
                  <tr key={g.id}>
                    <th scope="row"><span className="mono">{g.id}</span> {g.name}</th>
                    <td>{g.after}</td><td>{g.level}</td><td>{g.check}</td><td>{g.onFail}</td><td><code>{g.module}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section aria-labelledby="leg-h" className="legend-section">
        <h2 id="leg-h">Legends</h2>
        <div className="legend-grid">
          <Card title="Audit status">
            <Legend label="Audit status" items={[
              { swatch: <StatusBadge status="COMPLETE" />, label: '', description: 'Every relevant copy has the required treatment and nothing can recreate it.' },
              { swatch: <StatusBadge status="INCOMPLETE" />, label: '', description: 'Data remains, is exposed, or can come back. A remediation plan is produced.' },
              { swatch: <StatusBadge status="NOT_APPLICABLE" />, label: '', description: 'The request text does not authorise deletion (access, correction, opt-out).' },
            ]} />
          </Card>
          <Card title="Evidence tiers">
            <Legend label="Evidence tiers" items={[
              { swatch: TIER_SW('a', 'A'), label: 'Direct', description: 'Citable file showing the resource in the cited state.' },
              { swatch: TIER_SW('b', 'B'), label: 'Inferred', description: 'Absence proven by omission from a citable snapshot.' },
              { swatch: TIER_SW('c', 'C'), label: 'Claim', description: 'Workflow or activity claim; never cited alone.' },
              { swatch: TIER_SW('d', 'D'), label: 'Late', description: 'Captured after audit_at; discovery only (hatched).' },
              { swatch: TIER_SW('x', 'X'), label: 'None', description: 'Future step; no evidence by design.' },
            ]} />
          </Card>
        </div>
      </section>

      <footer className="sec-note" aria-label="Security posture">
        <Icon name="lock" size={20} />
        <p>The console API listens on localhost only. Identifiers are masked in every response, and API keys never leave the server: the browser only talks to the local API and never to a model provider.
          {' '}<button type="button" className="linkish" onClick={() => go('cases')}>Browse cases</button></p>
      </footer>
    </div>
  )
}
