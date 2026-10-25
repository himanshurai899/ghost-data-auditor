// Cost and metrics (#/cost): calls, tokens and cost for the selected run. Data: GET /api/metrics/cost. Unknown = 'n/a', never 0.
import { useCallback } from 'react'
import { Button, Card, EmptyState, Icon, PageHeader, Skeleton, StatCard, Tooltip } from '../ui'
import { Sparkline } from '../charts'
import { getCost, num, secs, useLoad } from '../metricsApi'
import type { CostData, ModelRow } from '../metricsApi'
import type { ScreenProps } from '../types'
import './cost.css'

const usd = (n: number | null) => (n === null ? 'n/a' : `$${n < 0.01 && n > 0 ? n.toFixed(4) : n.toFixed(2)}`)
const NO_RATE = 'No public per-token rate recorded in pricing.json'

function Na({ why, children }: { why: string; children: string }) {
  return children === 'n/a'
    ? <Tooltip content={why}><button type="button" className="co-na">n/a<span className="sr"> ({why})</span></button></Tooltip>
    : <>{children}</>
}

function ModelTable({ rows, label, withTotal }: { rows: ModelRow[]; label: string; withTotal?: boolean }) {
  const sum = (k: 'calls' | 'cached') => rows.reduce((a, r) => a + r[k], 0)
  const nsum = (k: 'tokens_in' | 'tokens_out' | 'est_cost_usd') => (rows.some((r) => r[k] === null) ? null : rows.reduce((a, r) => a + (r[k] as number), 0))
  return (
    <div className="tablewrap">
      <table>
        <caption className="sr">{label}</caption>
        <thead><tr><th>Provider</th><th>Model</th><th>Role</th><th>Calls</th><th>Cached</th><th>Tokens in</th><th>Tokens out</th><th>Est. cost</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.provider}/${r.model}/${r.role}`}>
              <td>{r.provider}</td><td><code>{r.model}</code></td><td>{r.role ?? 'n/a'}</td><td>{num(r.calls)}</td><td>{num(r.cached)}</td>
              <td><Na why="Token counts were not recorded for these calls.">{num(r.tokens_in)}</Na></td><td><Na why="Token counts were not recorded for these calls.">{num(r.tokens_out)}</Na></td>
              <td><Na why={NO_RATE}>{usd(r.est_cost_usd)}</Na></td>
            </tr>
          ))}
          {withTotal && rows.length > 1 && (
            <tr className="co-total"><th scope="row" colSpan={3}>Overall</th><td>{num(sum('calls'))}</td><td>{num(sum('cached'))}</td>
              <td><Na why="At least one model has no recorded token count.">{num(nsum('tokens_in'))}</Na></td><td><Na why="At least one model has no recorded token count.">{num(nsum('tokens_out'))}</Na></td><td><Na why={NO_RATE}>{usd(nsum('est_cost_usd'))}</Na></td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export default function Cost(p: ScreenProps) {
  const fn = useCallback(getCost, [])
  const { data: d, error, loading, reload } = useLoad<CostData>(fn, p.runId)
  const head = <PageHeader title="Cost and metrics" subtitle={d ? <>Run <code>{d.run.run_id}</code>. Everything here is read from run artifacts; unknown values stay n/a.</> : 'Model calls, tokens and cost for the selected run.'} />

  if (!p.runId && p.runs.length === 0) {
    return <div className="stack">{head}<EmptyState icon="database" title="No audit runs yet" text="Run an audit first; its usage ledger appears here." action={<Button variant="primary" icon="play" loading={p.starting} onClick={() => void p.startAudit()}>Run audit</Button>} /></div>
  }
  if (error) return <div className="stack">{head}<EmptyState icon="warn" title="Could not load cost metrics" text={error} action={<Button onClick={reload}>Retry</Button>} /></div>
  if (loading || !d) {
    return (
      <div className="stack" aria-busy="true">{head}
        <div className="grid-auto">{[0, 1, 2, 3, 4].map((i) => <StatCard key={i} label="Loading" value="" loading />)}</div>
        <Card><Skeleton h={20} w="40%" /><div style={{ height: 12 }} /><Skeleton h={120} /></Card>
      </div>
    )
  }

  const r = d.run
  const tot = r.tokens_in !== null && r.tokens_out !== null ? r.tokens_in + r.tokens_out : null
  const callsSeries = r.calls_over_time
  const notes = d.notes
  return (
    <div className="stack">
      {head}
      <div className="grid-auto">
        <StatCard label="Model calls" icon="cog" value={num(r.calls)} sub={`${num(r.cached)} cached, ${num(r.live)} live`} />
        <StatCard label="Tokens in / out" icon="file" value={<Na why="Providers did not return token counts for these calls.">{num(tot)}</Na>}
          sub={r.tokens_in === null ? 'in: n/a, out: n/a' : `in ${num(r.tokens_in)}, out ${num(r.tokens_out)}`} />
        <StatCard label="Avg tokens per request" icon="chart" value={<Na why="Needs total tokens and a request count, one is unknown.">{num(r.avg_tokens_per_request)}</Na>} sub={`${num(r.requests)} requests`} />
        <StatCard label="Estimated cost" icon="database" value={<Na why={NO_RATE}>{usd(r.est_cost_usd)}</Na>} sub={r.est_cost_usd === null ? 'Not computed: no rate to multiply tokens by.' : r.calls === 0 ? 'No model calls, so nothing to price.' : 'tokens x recorded rate'} />
        <StatCard label="Billed cost" icon="lock" tone="ok" value={usd(r.billed_usd)} sub="NVIDIA build free tier, not metered. Stated from setup, not measured from billing." />
      </div>

      <Card title="Where model calls happen" tone="primary">
        <ul className="co-notes">{notes.map((n) => <li key={n}><Icon name="info" size={16} /><span>{n}</span></li>)}</ul>
        <p className="muted co-sm">The pipeline stages that can use a model are marked as LLM edges in the legend on the <a href="#/">Overview page</a>.</p>
      </Card>

      <Card title="Per-model usage in this run">
        {r.by_model.length ? <ModelTable rows={r.by_model} label="Model usage in this run" withTotal /> : <p className="muted">No model calls in this run: {r.calls === 0 ? 'the offline audit makes none.' : 'n/a'}</p>}
      </Card>

      <div className="co-grid">
        <Card title="Calls over time">
          {callsSeries.length ? (
            <Sparkline label="Model calls per minute" height={72} values={callsSeries.map((c) => c.calls)}
              tableAlt={{ caption: 'Model calls per minute', columns: ['Minute', 'Calls'], rows: callsSeries.map((c) => [c.t.replace('T', ' '), c.calls]) }} />
          ) : <p className="muted">No timestamped model calls in this run, so there is no timeline. That is expected for an offline run.</p>}
        </Card>
        <Card title="One-time cache build">
          <p className="muted co-sm">Page-cache build (Nemotron Parse over rendered screenshots). Outside the per-request numbers.</p>
          <p><strong>{num(d.cache_build.calls)}</strong> calls</p>
          {d.cache_build.by_model.length ? <ModelTable rows={d.cache_build.by_model} label="One-time cache build usage by model" /> : <p className="muted">No ledger found for the cache build.</p>}
          <p className="muted co-sm">Tokens are n/a because their counts were not retained when the cache was built; they are not estimated.</p>
        </Card>
      </div>

      <div className="co-grid">
        <Card title="All runs">
          {d.all_runs.length ? (
            <>
              <div className="co-spark"><Sparkline label="Model calls per run, oldest to newest" height={40} values={[...d.all_runs].reverse().map((x) => x.calls)} /></div>
              <div className="tablewrap">
                <table>
                  <thead><tr><th>Run</th><th>Calls</th><th>Tokens</th><th>Duration</th></tr></thead>
                  <tbody>{d.all_runs.map((x) => <tr key={x.run_id} className={x.run_id === r.run_id ? 'co-cur' : ''}><td><code>{x.run_id}</code></td><td>{num(x.calls)}</td><td>{num(x.tokens)}</td><td>{secs(x.duration_s)}</td></tr>)}</tbody>
                </table>
              </div>
            </>
          ) : <p className="muted">No runs recorded.</p>}
        </Card>
        <Card title="Pricing">
          <dl className="co-dl">
            <dt>Per-token rates known</dt><dd>{d.pricing.rates_known ? 'Yes' : 'No'}</dd>
            <dt>Source</dt><dd>{d.pricing.source ?? 'n/a: none recorded'}</dd>
          </dl>
          <p className="muted co-sm">Estimated cost stays n/a until rates are recorded. Choose models and test the connection on the <a href="#/settings">Settings page</a>.</p>
        </Card>
      </div>
    </div>
  )
}
