// Resurrection timeline: one lane per resource on a shared time axis (inline SVG, zoomable, no library).
// Props: { runId, caseId, sel?, onSel? }  sel/onSel optionally share the highlighted evidence id with the Case page.
import { useId, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getTimeline, useAsync, useDemo } from './client.ts'
import type { Async, TimelineData, TimelineItem } from './client.ts'
import { Legend, Skeleton } from '../ui'
import './screens.css'

export function DemoBadge() {
  return useDemo() ? <span className="s-demo" role="status">demo data (API unreachable)</span> : null
}

/** Loading / error wrapper shared by the screens. */
export function Gate<T>({ a, children, retry }: { a: Async<T>; children: (d: T) => ReactNode; retry?: () => void }) {
  if (a.state === 'loading') return <div className="s-state" role="status" aria-label="Loading"><Skeleton h={18} w="40%" /><div style={{ height: 8 }} /><Skeleton h={120} /></div>
  if (a.state === 'error') return <div className="s-state err" role="alert">Could not load: {a.error}{retry && <> <button type="button" onClick={retry}>Retry</button></>}</div>
  return <>{children(a.data)}</>
}

const RISK = new Set(['ACTIVE', 'RESTORE_RISK', 'RISK', 'ENABLED', 'RUNNING'])
const TREATED = new Set(['REDACTED', 'ANONYMIZED', 'BLOCKED', 'DISABLED'])
type Shape = 'circle' | 'square' | 'tri' | 'diamond'
interface Look { cls: 'amber' | 'green' | 'red' | 'blue' | 'plain'; shape: Shape; word: string }
function look(obs: string): Look {
  const o = obs.toUpperCase()
  if (o === 'PRESENT') return { cls: 'amber', shape: 'circle', word: 'present' }
  if (o === 'ABSENT') return { cls: 'green', shape: 'square', word: 'absent' }
  if (RISK.has(o)) return { cls: 'red', shape: 'tri', word: 'active or restore risk' }
  if (TREATED.has(o)) return { cls: 'blue', shape: 'diamond', word: 'redacted, blocked or disabled' }
  return { cls: 'plain', shape: 'circle', word: 'other' }
}
const INK: Record<Look['cls'], string> = { amber: 'var(--warn)', green: 'var(--ok)', red: 'var(--bad)', blue: 'var(--primary-text)', plain: 'var(--text-muted)' }

const fmt = (iso: string) => iso.replace('T', ' ').replace(/:\d\d(\.\d+)?Z?$/, '').replace(/Z$/, '') + ' UTC'
const ms = (iso: string) => Date.parse(iso)

/** One-sentence story computed from the citable items. */
export function story(items: TimelineItem[]): string {
  const ok = items.filter((i) => i.citable)
  const gone = ok.find((i) => i.observation.toUpperCase() === 'ABSENT')
  const back = gone && ok.find((i) => ms(i.observed_at) > ms(gone.observed_at) && i.resource_id === gone.resource_id && i.observation.toUpperCase() === 'PRESENT')
  if (gone && back) return `${gone.resource_id} was deleted on ${fmt(gone.observed_at)} but came back (PRESENT) on ${fmt(back.observed_at)}: the record came back.`
  const risk = ok.find((i) => RISK.has(i.observation.toUpperCase()))
  const present = ok.find((i) => i.observation.toUpperCase() === 'PRESENT')
  if (present && risk) return `${present.resource_id} is still present and ${risk.resource_id} can recreate data (${risk.observation}).`
  if (present) return `${present.resource_id} is still present at audit time.`
  if (risk) return `${risk.resource_id} shows ${risk.observation}: data can be recreated.`
  if (ok.length) return 'Every citable observation shows the data gone or treated.'
  return 'No citable observations before audit time.'
}

function Mark({ shape, cx, cy, r = 7 }: { shape: Shape; cx: number; cy: number; r?: number }) {
  if (shape === 'square') return <rect x={cx - r} y={cy - r} width={r * 2} height={r * 2} rx={2} />
  if (shape === 'tri') return <polygon points={`${cx},${cy - r - 1} ${cx + r + 1},${cy + r} ${cx - r - 1},${cy + r}`} />
  if (shape === 'diamond') return <polygon points={`${cx},${cy - r - 2} ${cx + r + 2},${cy} ${cx},${cy + r + 2} ${cx - r - 2},${cy}`} />
  return <circle cx={cx} cy={cy} r={r} />
}

/** Legend swatch: a marker drawn the way it appears on the chart. */
function Sw({ cls = 'plain', shape = 'circle', style = 'solid' }: { cls?: Look['cls']; shape?: Shape; style?: 'solid' | 'claim' | 'late' }) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" style={{ color: INK[cls] }}>
      <g className={`tl-mark is-${style}`} fill={style === 'solid' ? 'currentColor' : 'var(--surface)'} stroke="currentColor" strokeWidth="2" strokeDasharray={style === 'late' ? '3 2' : undefined}>
        <Mark shape={shape} cx={11} cy={11} r={6} />
      </g>
    </svg>
  )
}

const GUT = 180, HDR = 62, AXIS = 30, PAD = 22, SUB = 20

interface Placed { it: TimelineItem; x: number; y: number; n: number }

function Chart({ d, sel, onSel }: { d: TimelineData; sel?: string | null; onSel?: (id: string | null) => void }) {
  const uid = useId().replace(/:/g, '')
  const [zoom, setZoom] = useState(1)
  const [act, setAct] = useState<number | null>(null)
  const W = Math.round(720 * zoom)

  const model = useMemo(() => {
    const marks = [
      { key: 'requested', label: 'requested', t: ms(d.requested_at), at: d.requested_at },
      { key: 'reported', label: 'reported', t: ms(d.reported_at), at: d.reported_at },
      { key: 'audit', label: 'audit_at', t: ms(d.audit_at), at: d.audit_at },
    ]
    const all = [...marks.map((m) => m.t), ...d.items.map((i) => ms(i.observed_at))].filter((n) => Number.isFinite(n))
    const lo0 = Math.min(...all), hi0 = Math.max(...all)
    const pad = Math.max((hi0 - lo0) * 0.03, 3600e3)
    const lo = lo0 - pad, span = hi0 + pad - lo
    const lanesMap = new Map<string, { key: string; sys: string; res: string; items: { it: TimelineItem; n: number }[] }>()
    d.items.forEach((it, n) => {
      const key = `${it.system_id} / ${it.resource_id}`
      if (!lanesMap.has(key)) lanesMap.set(key, { key, sys: it.system_id, res: it.resource_id, items: [] })
      lanesMap.get(key)!.items.push({ it, n })
    })
    return { marks, lo, span, lanes: [...lanesMap.values()] }
  }, [d])

  const x = (t: number) => PAD + ((t - model.lo) / model.span) * (W - PAD * 2)
  // pack items into sub-rows inside each lane so markers close in time do not sit on top of each other
  let top = HDR
  const lanes = model.lanes.map((l) => {
    const sorted = [...l.items].sort((a, b) => ms(a.it.observed_at) - ms(b.it.observed_at))
    const last: number[] = []
    const placed: Placed[] = sorted.map(({ it, n }, idx) => {
      const px = x(ms(it.observed_at))
      let s = last.findIndex((lx) => px - lx >= 20)
      if (s < 0) s = last.length < 4 ? last.length : idx % 4
      last[s] = px
      return { it, x: px, y: s, n }
    })
    const subs = Math.max(1, last.length)
    const h = 22 + subs * SUB
    const out = { ...l, placed, top, h }
    top += h
    return out
  })
  const H = top + AXIS
  const nt = Math.max(3, Math.min(10, Math.floor(W / 140)))
  const ticks = Array.from({ length: nt }, (_, i) => model.lo + (model.span * i) / (nt - 1))
  const days = model.span > 4 * 86400e3
  const tickLabel = (t: number) => { const s = new Date(t).toISOString(); return days ? s.slice(0, 10) : `${s.slice(5, 10)} ${s.slice(11, 16)}` }
  const audit = model.marks[2]
  const cur = act === null ? null : d.items[act]
  const hatch = (c: Look['cls']) => `${uid}-h-${c}`

  return (
    <>
      <div className="tl-tools">
        <label className="tl-zoom">Zoom <input type="range" min={1} max={6} step={0.25} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} aria-valuetext={`${zoom} times`} /> <span className="mono">x{zoom}</span></label>
        <button type="button" onClick={() => setZoom(1)} disabled={zoom === 1}>Fit to window</button>
        <span className="s-muted tl-hint">Scroll the chart sideways when zoomed.</span>
      </div>
      <div className="tl-wrap">
        <div className="tl-gut" style={{ width: GUT }} aria-hidden="true">
          <div style={{ height: HDR }} />
          {lanes.map((l) => <div key={l.key} className="tl-lane-label" style={{ height: l.h }} title={l.key}><span>{l.sys}</span><code>{l.res}</code></div>)}
        </div>
        <div className="tl-scroll" tabIndex={0} role="group" aria-label="Timeline chart, scrollable">
          <svg width={W} height={H} className="tl-svg" role="img" aria-label={`Timeline with ${d.items.length} observations across ${lanes.length} resources. A table is available below.`}>
            <defs>
              {(['amber', 'green', 'red', 'blue', 'plain'] as const).map((c) => (
                <pattern key={c} id={hatch(c)} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="var(--surface)" /><line x1="0" y1="0" x2="0" y2="5" stroke={INK[c]} strokeWidth="2" /></pattern>
              ))}
              <pattern id={`${uid}-late`} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="var(--border)" strokeWidth="3" /></pattern>
            </defs>
            {/* region after audit_at: facts here can never be cited */}
            <rect x={x(audit.t)} y={HDR - 6} width={Math.max(0, W - x(audit.t))} height={top - HDR + 6} fill={`url(#${uid}-late)`} opacity=".55" />
            {lanes.map((l, i) => <line key={l.key} x1={0} x2={W} y1={l.top} y2={l.top} className="tl-sep" style={{ display: i === 0 ? 'none' : undefined }} />)}
            {lanes.length > 0 && <line x1={0} x2={W} y1={top} y2={top} className="tl-sep" />}
            {/* markers */}
            {model.marks.map((m, i) => {
              const mx = x(m.t), end = mx > W - 150
              return (
                <g key={m.key} className={`tl-m ${m.key === 'audit' ? 'is-audit' : ''}`}>
                  <line x1={mx} x2={mx} y1={16 + i * 16} y2={top} />
                  <text x={mx + (end ? -6 : 6)} y={14 + i * 16} textAnchor={end ? 'end' : 'start'}>{m.label} {fmt(m.at).slice(5, 16)}</text>
                </g>
              )
            })}
            {/* items */}
            {lanes.map((l) => l.placed.map((p) => {
              const lk = look(p.it.observation)
              const cy = l.top + 22 + p.y * SUB
              const on = !!p.it.evidence_id && p.it.evidence_id === sel
              const kind = p.it.is_claim ? 'claim' : p.it.citable ? 'solid' : 'late'
              const name = `${p.it.is_claim ? 'Claim' : 'Observed'}: ${p.it.system_id} ${p.it.resource_id} ${p.it.observation} at ${fmt(p.it.observed_at)}${p.it.citable ? '' : ', after audit, not citable'}`
              return (
                <g key={p.n} className={`tl-it ${on ? 'is-sel' : ''}`} style={{ color: INK[lk.cls], opacity: p.it.citable ? 1 : 0.8 }} tabIndex={0} role="button" aria-label={name} aria-pressed={p.it.evidence_id ? on : undefined}
                  onMouseEnter={() => setAct(p.n)} onMouseLeave={() => setAct(null)} onFocus={() => setAct(p.n)} onBlur={() => setAct(null)}
                  onClick={() => p.it.evidence_id && onSel?.(on ? null : p.it.evidence_id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (p.it.evidence_id) onSel?.(on ? null : p.it.evidence_id) } }}>
                  <circle cx={p.x} cy={cy} r={16} fill="transparent" stroke="none" />
                  {on && <circle cx={p.x} cy={cy} r={14} className="tl-ring" />}
                  <g fill={kind === 'solid' ? 'currentColor' : kind === 'late' ? `url(#${hatch(lk.cls)})` : 'var(--surface)'} stroke="currentColor" strokeWidth={2} strokeDasharray={kind === 'late' ? '3 2' : undefined}>
                    <Mark shape={lk.shape} cx={p.x} cy={cy} />
                  </g>
                </g>
              )
            }))}
            {/* axis */}
            <g className="tl-axis">
              {ticks.map((t, i) => (
                <g key={i}><line x1={x(t)} x2={x(t)} y1={top} y2={top + 5} /><text x={x(t)} y={top + 20} textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'}>{tickLabel(t)}</text></g>
              ))}
            </g>
          </svg>
        </div>
      </div>
      <p className="tl-detail" aria-live="polite">
        {cur ? (
          <><b>{cur.is_claim ? 'Claim' : 'Observation'}: {cur.observation}</b> on {cur.system_id} / <code>{cur.resource_id}</code>. Observed {fmt(cur.observed_at)}, captured {fmt(cur.captured_at)}.{' '}
            {cur.evidence_id ? <>Evidence <code>{cur.evidence_id}</code>.</> : 'No evidence id.'} {cur.citable ? 'Citable at audit_at.' : 'After audit_at, not citable.'}</>
        ) : <span className="s-muted">Hover or focus a marker for details. Click one to highlight its evidence id across the page.</span>}
      </p>
      <Legend label="Timeline legend" items={[
        { swatch: <Sw cls="amber" shape="circle" />, label: 'Present', description: 'record still there' },
        { swatch: <Sw cls="green" shape="square" />, label: 'Absent', description: 'record gone' },
        { swatch: <Sw cls="red" shape="tri" />, label: 'Active', description: 'data flow or restore risk' },
        { swatch: <Sw cls="blue" shape="diamond" />, label: 'Treated', description: 'redacted, anonymized, blocked, disabled' },
        { swatch: <Sw cls="plain" style="claim" />, label: 'Hollow', description: 'a claim, not a file observation' },
        { swatch: <Sw cls="plain" style="late" />, label: 'Dashed and hatched', description: 'after audit_at, discovery only, never cited' },
        { swatch: <svg width="22" height="22" aria-hidden="true"><line x1="11" x2="11" y1="2" y2="20" stroke="var(--text)" strokeWidth="3" /></svg>, label: 'Solid line', description: 'audit_at cutoff (thin dashed lines: requested, reported)' },
      ]} />
      <details className="tl-table">
        <summary>View as table</summary>
        <div className="tl-tw"><table>
          <caption className="sr">All timeline observations</caption>
          <thead><tr><th scope="col">Observed</th><th scope="col">System / resource</th><th scope="col">Observation</th><th scope="col">Kind</th><th scope="col">Evidence</th><th scope="col">Citable</th></tr></thead>
          <tbody>{[...d.items].sort((a, b) => ms(a.observed_at) - ms(b.observed_at)).map((it, i) => (
            <tr key={i}><td>{fmt(it.observed_at)}</td><td>{it.system_id} / <code>{it.resource_id}</code></td><td>{it.observation}</td><td>{it.is_claim ? 'claim' : 'file observation'}</td><td><code>{it.evidence_id || 'none'}</code></td><td>{it.citable ? 'yes' : 'no, after audit_at'}</td></tr>
          ))}</tbody>
        </table></div>
      </details>
    </>
  )
}

export default function Timeline({ caseId, runId, sel, onSel }: { runId: string; caseId: string; sel?: string | null; onSel?: (id: string | null) => void }) {
  const a = useAsync(() => getTimeline(runId, caseId), [runId, caseId])
  return (
    <section className="screen" aria-label={`Resurrection timeline for ${caseId}`}>
      <div className="s-row"><h3>Resurrection timeline</h3><DemoBadge /></div>
      <Gate a={a}>
        {(d) => {
          if (!d.items.length) return <div className="s-state">No observations for this case, so there is nothing to place on a timeline. Linked resources had no activity or file facts before or after the audit time.</div>
          return (
            <>
              <p className="tl-caption" role="note">{story(d.items)}</p>
              <Chart d={d} sel={sel} onSel={onSel} />
            </>
          )
        }}
      </Gate>
    </section>
  )
}
