// Identity graph: user at the centre, identifiers on ring 1, resources on ring 2 (inline SVG, no library).
// Props: { runId, caseId }. Hover, focus or click a node to highlight its neighbours; a table alternative is included.
import { useMemo, useState } from 'react'
import { getIdentity, useAsync } from './client.ts'
import type { IdNode, IdentityData } from './client.ts'
import { DemoBadge, Gate } from './Timeline.tsx'
import { Legend } from '../ui'
import './screens.css'

const W = 820, H = 640, CX = W / 2, CY = H / 2, R1 = 125, R2 = 240
const short = (s: string, n = 24) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
const radius = (n: IdNode) => (n.kind === 'user' ? 22 : n.kind === 'resource' ? 11 : 15)
const isHist = (n: IdNode) => n.kind !== 'user' && n.kind !== 'resource' && !n.current

interface Pos { x: number; y: number; a: number }
interface LabelPos { x: number; y: number; anchor: 'start' | 'middle' | 'end' }

/** Deterministic layout: user centre, identifiers on ring 1, resources on ring 2 starting near their linking identifier. */
function layout(d: IdentityData) {
  const pos = new Map<string, Pos>()
  const ids = d.nodes.filter((n) => n.kind !== 'user' && n.kind !== 'resource')
  const res = d.nodes.filter((n) => n.kind === 'resource')
  d.nodes.filter((n) => n.kind === 'user').forEach((u) => pos.set(u.id, { x: CX, y: CY, a: 0 }))
  const put = (n: IdNode, r: number, a: number) => pos.set(n.id, { x: CX + r * Math.cos(a), y: CY + r * Math.sin(a), a })
  ids.forEach((n, i) => put(n, R1, -Math.PI / 2 + (2 * Math.PI * i) / Math.max(ids.length, 1)))
  const parent = (r: IdNode) => d.edges.find((e) => e.to === r.id)?.from
  const order = [...res].sort((x, y) => (pos.get(parent(x) ?? '')?.a ?? 0) - (pos.get(parent(y) ?? '')?.a ?? 0))
  const start = order.length ? (pos.get(parent(order[0]) ?? '')?.a ?? -Math.PI / 2) : 0
  order.forEach((n, i) => put(n, R2, start + (2 * Math.PI * i) / order.length))

  // collision-aware labels: push outward along the radius until the text box clears every placed box
  const boxes: { x0: number; y0: number; x1: number; y1: number }[] = []
  const labels = new Map<string, LabelPos>()
  const hit = (b: { x0: number; y0: number; x1: number; y1: number }) => boxes.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0)
  for (const n of [...d.nodes.filter((q) => q.kind === 'user'), ...ids, ...res]) {
    const p = pos.get(n.id)!, r = radius(n), w = short(n.label).length * 6.2
    const cos = Math.cos(p.a), sin = Math.sin(p.a)
    const anchor: LabelPos['anchor'] = n.kind === 'user' ? 'middle' : cos > 0.3 ? 'start' : cos < -0.3 ? 'end' : 'middle'
    let chosen: LabelPos | null = null, box = { x0: 0, y0: 0, x1: 0, y1: 0 }
    for (const extra of [0, 14, 28, 42, 56]) {
      const lx = n.kind === 'user' ? p.x : p.x + (r + 6 + extra) * cos
      const ly = n.kind === 'user' ? p.y + r + 16 + extra : p.y + (r + 6 + extra) * sin + 4
      box = { x0: anchor === 'start' ? lx : anchor === 'end' ? lx - w : lx - w / 2, y0: ly - 11, x1: anchor === 'start' ? lx + w : anchor === 'end' ? lx : lx + w / 2, y1: ly + 3 }
      chosen = { x: lx, y: ly, anchor }
      if (!hit(box)) break
    }
    boxes.push(box); labels.set(n.id, chosen!)
  }
  return { pos, labels }
}

const KIND_LABEL: Record<string, string> = { user: 'user', email: 'email', phone: 'phone', hash: 'email hash', resource: 'resource' }
const kindName = (n: IdNode) => `${KIND_LABEL[n.kind]}${n.kind === 'user' || n.kind === 'resource' ? '' : isHist(n) ? ' (historical)' : ' (current)'}`

function Swatch({ kind, hist }: { kind: IdNode['kind']; hist?: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" className={`ig-${kind} ${hist ? 'ig-hist' : ''}`}>
      {kind === 'resource' ? <rect className="shape" x="4" y="4" width="14" height="14" rx="3" /> : <circle className="shape" cx="11" cy="11" r="7" />}
    </svg>
  )
}

function Graph({ d }: { d: IdentityData }) {
  const [hov, setHov] = useState<string | null>(null)
  const [pin, setPin] = useState<string | null>(null)
  const L = useMemo(() => layout(d), [d])
  const byId = useMemo(() => new Map(d.nodes.map((n) => [n.id, n])), [d])
  if (!d.nodes.length) return <div className="s-state">No identity graph for this case: the request email did not resolve to a known user, so there are no identifiers or linked resources to draw.</div>
  const edges = d.edges.filter((e) => byId.has(e.from) && byId.has(e.to))
  const act = hov ?? pin
  const near = new Set<string>(act ? [act] : [])
  if (act) edges.forEach((e) => { if (e.from === act) near.add(e.to); if (e.to === act) near.add(e.from) })
  const actNode = act ? byId.get(act) : undefined
  const showAllLabels = edges.length <= 14

  return (
    <>
      <svg className="ig-svg" viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Identity graph">
        {edges.map((e, i) => {
          const a = L.pos.get(e.from)!, b = L.pos.get(e.to)!
          const on = act && (e.from === act || e.to === act)
          const t = byId.get(e.to)?.kind === 'resource' ? 0.42 : 0.5
          return (
            <g key={i} className={`ig-e ${on ? 'on' : ''} ${act && !on ? 'dim' : ''}`}>
              <line className="ig-edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
              {(showAllLabels || on) && <text x={a.x + (b.x - a.x) * t} y={a.y + (b.y - a.y) * t} textAnchor="middle" className="ig-elabel" aria-hidden="true">{short(e.label, 18)}</text>}
            </g>
          )
        })}
        {d.nodes.map((n) => {
          const p = L.pos.get(n.id)!, lb = L.labels.get(n.id)!, r = radius(n)
          const dim = act && !near.has(n.id)
          return (
            <g key={n.id} className={`ig-node ig-${n.kind} ${isHist(n) ? 'ig-hist' : ''} ${dim ? 'dim' : ''} ${n.id === act ? 'is-act' : ''}`} tabIndex={0} role="button" aria-pressed={pin === n.id}
              aria-label={`${kindName(n)}: ${n.label}`}
              onMouseEnter={() => setHov(n.id)} onMouseLeave={() => setHov(null)} onFocus={() => setHov(n.id)} onBlur={() => setHov(null)}
              onClick={() => setPin(pin === n.id ? null : n.id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPin(pin === n.id ? null : n.id) } else if (e.key === 'Escape') setPin(null) }}>
              <circle cx={p.x} cy={p.y} r={r + 8} fill="transparent" />
              {n.kind === 'resource' ? <rect className="shape" x={p.x - r} y={p.y - r} width={r * 2} height={r * 2} rx={3} /> : <circle className="shape" cx={p.x} cy={p.y} r={r} />}
              <text x={lb.x} y={lb.y} textAnchor={lb.anchor}>{short(n.label)}</text>
            </g>
          )
        })}
      </svg>
      <p className="ig-tip" aria-live="polite">
        {actNode ? <><b>{kindName(actNode)}</b> {actNode.label}. Linked to {near.size - 1} node{near.size === 2 ? '' : 's'}.{pin === actNode.id ? ' Pinned: click again to release.' : ''}</> : <span className="s-muted">Hover, focus or click a node to highlight what it connects to and read its full label.</span>}
      </p>
      <Legend label="Identity graph legend" items={[
        { swatch: <Swatch kind="user" />, label: 'User', description: 'stable internal reference' },
        { swatch: <Swatch kind="email" />, label: 'Current email' },
        { swatch: <Swatch kind="email" hist />, label: 'Historical identifier', description: 'dashed hollow ring, any kind' },
        { swatch: <Swatch kind="phone" />, label: 'Phone' },
        { swatch: <Swatch kind="hash" />, label: 'Email hash' },
        { swatch: <Swatch kind="resource" />, label: 'Resource', description: 'square, linked by the identifier on the edge label' },
      ]} />
      <details className="tl-table">
        <summary>View as table</summary>
        <div className="tl-tw"><table>
          <caption className="sr">Identity graph nodes and links</caption>
          <thead><tr><th scope="col">Kind</th><th scope="col">Label</th><th scope="col">Linked from</th><th scope="col">Link</th></tr></thead>
          <tbody>{d.nodes.map((n) => {
            const inc = edges.filter((e) => e.to === n.id)
            return <tr key={n.id}><td>{kindName(n)}</td><td><code>{n.label}</code></td><td>{inc.map((e) => byId.get(e.from)?.label).join(', ') || 'none'}</td><td>{inc.map((e) => e.label).join(', ') || 'n/a'}</td></tr>
          })}</tbody>
        </table></div>
      </details>
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
