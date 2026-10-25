import { useState } from 'react'
import { getIdentity, useAsync } from './client.ts'
import type { IdNode, IdentityData } from './client.ts'
import { DemoBadge, Gate } from './Timeline.tsx'
import './screens.css'

const W = 680, H = 560, CX = W / 2, CY = H / 2, R1 = 120, R2 = 235
const short = (s: string, n = 20) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

/** Deterministic layout: user centre, identifiers on ring 1, resources on ring 2 near their linking identifier. */
function layout(d: IdentityData) {
  const pos = new Map<string, { x: number; y: number; a: number }>()
  const user = d.nodes.filter((n) => n.kind === 'user')
  const ids = d.nodes.filter((n) => n.kind !== 'user' && n.kind !== 'resource')
  const res = d.nodes.filter((n) => n.kind === 'resource')
  user.forEach((u, i) => pos.set(u.id, { x: CX + i * 0, y: CY, a: 0 }))
  const put = (n: IdNode, r: number, a: number) => pos.set(n.id, { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a), a })
  ids.forEach((n, i) => put(n, R1, -Math.PI / 2 + (2 * Math.PI * i) / Math.max(ids.length, 1)))
  const parent = (r: IdNode) => d.edges.find((e) => e.to === r.id)?.from
  const order = [...res].sort((x, y) => (pos.get(parent(x) ?? '')?.a ?? 0) - (pos.get(parent(y) ?? '')?.a ?? 0))
  const start = order.length ? (pos.get(parent(order[0]) ?? '')?.a ?? -Math.PI / 2) : 0
  order.forEach((n, i) => put(n, R2, start + (2 * Math.PI * i) / order.length))
  return pos
}

const KIND_LABEL: Record<string, string> = { user: 'user', email: 'email', phone: 'phone', hash: 'email hash', resource: 'resource' }

function Graph({ d }: { d: IdentityData }) {
  const [tip, setTip] = useState<IdNode | null>(null)
  if (!d.nodes.length) return <div className="s-state">No identity graph for this case.</div>
  const pos = layout(d)
  const ids = new Set(d.nodes.map((n) => n.id))
  const edges = d.edges.filter((e) => ids.has(e.from) && ids.has(e.to))
  return (
    <>
      <svg className="ig-svg" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Identity graph">
        {edges.map((e, i) => {
          const a = pos.get(e.from)!, b = pos.get(e.to)!
          const on = tip && (tip.id === e.from || tip.id === e.to)
          return (
            <g key={i}>
              <line className={`ig-edge ${on ? 'on' : ''}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2} textAnchor="middle" style={{ fontSize: 9 }} aria-hidden="true">{e.label}</text>
            </g>
          )
        })}
        {d.nodes.map((n) => {
          const p = pos.get(n.id)!
          const r = n.kind === 'user' ? 22 : n.kind === 'resource' ? 11 : 15
          const hist = n.kind !== 'user' && n.kind !== 'resource' && !n.current
          const onLeft = p.x < CX - 5
          const label = `${KIND_LABEL[n.kind]}${hist ? ' (historical)' : n.kind === 'user' || n.kind === 'resource' ? '' : ' (current)'}: ${n.label}`
          return (
            <g key={n.id} className={`ig-node ig-${n.kind} ${hist ? 'ig-hist' : ''}`} tabIndex={0} role="img" aria-label={label}
              onMouseEnter={() => setTip(n)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(n)} onBlur={() => setTip(null)}>
              <title>{label}</title>
              {n.kind === 'resource'
                ? <rect className="shape" x={p.x - r} y={p.y - r} width={r * 2} height={r * 2} rx={3} />
                : <circle className="shape" cx={p.x} cy={p.y} r={r} />}
              <text x={n.kind === 'user' ? p.x : p.x + (onLeft ? -r - 4 : r + 4)} y={n.kind === 'user' ? p.y + r + 14 : p.y + 4} textAnchor={n.kind === 'user' ? 'middle' : onLeft ? 'end' : 'start'}>
                {short(n.label)}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="ig-tip" aria-live="polite">{tip ? <><b>{KIND_LABEL[tip.kind]}</b> {tip.label}{tip.kind !== 'user' && tip.kind !== 'resource' && (tip.current ? ' · current' : ' · historical')}</> : <span className="s-muted">Hover or focus a node to read its full label.</span>}</p>
      <div className="tl-legend" aria-label="Legend">
        <span className="chip ghost">● user</span><span className="chip blue">● email</span><span className="chip green">● phone</span>
        <span className="chip amber">● email hash</span><span className="chip red">■ resource</span>
        <span className="chip plain">dashed hollow = historical identifier</span><span className="chip plain">edge label = linking identifier kind</span>
      </div>
    </>
  )
}

export default function IdentityGraph({ runId, caseId }: { runId: string; caseId: string }) {
  const a = useAsync(() => getIdentity(runId, caseId), [runId, caseId])
  return (
    <section className="screen" aria-label={`Identity graph for ${caseId}`}>
      <div className="s-row"><h3>Identity graph</h3><DemoBadge /></div>
      <Gate a={a}>{(d) => <Graph d={d} />}</Gate>
    </section>
  )
}
