/*
 * Dependency-free charts. Colours are CSS custom properties (tokens); meaning is never colour-only: every series carries a
 * fill pattern (0 solid, 1 stripes, 2 dots, 3 cross-hatch), a text label and a printed value. Every chart accepts
 * `tableAlt` ({caption, columns, rows}) and then shows a "View as table" toggle that swaps the graphic for a real table.
 *
 * Seg         { key; label; value: number; color: string (css colour, e.g. 'var(--ok)'); pattern?: 0|1|2|3; hint?: ReactNode; onClick?() }
 * TableAlt    { caption: string; columns: string[]; rows: (string|number|null)[][] }
 * Donut       { segments: Seg[]; center?: {value: ReactNode; label: string}; size?: number; tableAlt?; label: string }
 *             SVG ring; segments are focusable (aria-label "<label>: <value> (<pct>%)"); legend rows beside are Tooltip buttons.
 * StackedBar  { segments: Seg[]; tableAlt?; label: string }   one horizontal bar (HTML/CSS) with a value row beneath.
 * BarList     { rows: {key; label; parts: Seg[]; sub?: ReactNode}[]; tableAlt?; label: string }  ranked horizontal (stacked) bars.
 * Ring        { value: number (0-100); color; center: ReactNode; label: string; size? }   single-value radial meter (SVG).
 * Sparkline   { values: (number|null)[]; label: string; height?: number; tableAlt? }   SVG polyline, null points skipped.
 * GateStrip   { gates: {gate: string; pass: number; warn: number; fail: number}[] }   one cell per gate: icon + text verdict + counts.
 * Motion is transform/opacity only and disabled under prefers-reduced-motion (charts.css).
 */
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { Button, Icon, Tooltip } from '../ui'
import './charts.css'

export interface Seg { key: string; label: string; value: number; color: string; pattern?: 0 | 1 | 2 | 3; hint?: ReactNode; onClick?: () => void }
export interface TableAlt { caption: string; columns: string[]; rows: (string | number | null)[][] }

const pct = (v: number, t: number) => (t > 0 ? Math.round((1000 * v) / t) / 10 : 0)
const fmt = (n: number) => n.toLocaleString('en-US')
const safeId = (s: string) => s.replace(/[^a-zA-Z0-9_-]/g, '')

function Frame({ tableAlt, children }: { tableAlt?: TableAlt; children: ReactNode }) {
  const [table, setTable] = useState(false)
  if (!tableAlt) return <>{children}</>
  return (
    <div className="ch-frame">
      {table ? (
        <div className="tablewrap ch-table">
          <table>
            <caption className="sr">{tableAlt.caption}</caption>
            <thead><tr>{tableAlt.columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody>{tableAlt.rows.map((r, i) => <tr key={i}>{r.map((c, j) => (j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c ?? 'n/a'}</td>))}</tr>)}</tbody>
          </table>
        </div>
      ) : children}
      <Button variant="ghost" className="ch-toggle" onClick={() => setTable(!table)} aria-pressed={table}>{table ? 'View as chart' : 'View as table'}</Button>
    </div>
  )
}

function Swatch({ s }: { s: Pick<Seg, 'color' | 'pattern'> }) {
  return <span className={`ch-sw pat-${s.pattern ?? 0}`} style={{ ['--c' as string]: s.color }} aria-hidden="true" />
}

function Items({ segs, total, active, setActive }: { segs: Seg[]; total: number; active: string | null; setActive: (k: string | null) => void }) {
  return (
    <ul className="ch-items">
      {segs.map((s) => (
        <li key={s.key}>
          <Tooltip content={<><strong>{s.label}</strong>: {fmt(s.value)} ({pct(s.value, total)}%){s.hint && <><br />{s.hint}</>}</>}>
            <button type="button" className={`ch-item ${active === s.key ? 'is-active' : ''}`} onClick={s.onClick}
              onMouseEnter={() => setActive(s.key)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(s.key)} onBlur={() => setActive(null)}>
              <Swatch s={s} /><span className="ch-item-l">{s.label}</span><span className="ch-item-v">{fmt(s.value)}</span><span className="ch-item-p muted">{pct(s.value, total)}%</span>
            </button>
          </Tooltip>
        </li>
      ))}
    </ul>
  )
}

function arc(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number) {
  const p = (r: number, a: number) => `${(cx + r * Math.sin(a)).toFixed(3)} ${(cy - r * Math.cos(a)).toFixed(3)}`
  const big = a1 - a0 > Math.PI ? 1 : 0
  return `M${p(r1, a0)} A${r1} ${r1} 0 ${big} 1 ${p(r1, a1)} L${p(r0, a1)} A${r0} ${r0} 0 ${big} 0 ${p(r0, a0)}Z`
}

function PatternDefs({ id, segs }: { id: string; segs: Pick<Seg, 'key' | 'color' | 'pattern'>[] }) {
  return (
    <defs>
      {segs.map((s) => (
        <pattern key={s.key} id={`${id}-${safeId(s.key)}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" style={{ fill: s.color }} />
          {s.pattern === 1 && <rect width="2.4" height="6" fill="rgba(0,0,0,.34)" />}
          {s.pattern === 2 && <circle cx="3" cy="3" r="1.3" fill="rgba(0,0,0,.4)" />}
          {s.pattern === 3 && <path d="M0 0H6M0 0V6" stroke="rgba(0,0,0,.34)" strokeWidth="1.6" />}
        </pattern>
      ))}
    </defs>
  )
}

export function Donut({ segments, center, size = 180, tableAlt, label }: { segments: Seg[]; center?: { value: ReactNode; label: string }; size?: number; tableAlt?: TableAlt; label: string }) {
  const id = safeId(useId())
  const [active, setActive] = useState<string | null>(null)
  const total = segments.reduce((a, s) => a + s.value, 0)
  const R1 = 48, R0 = 30
  let a = 0
  return (
    <Frame tableAlt={tableAlt}>
      <div className="ch-donut">
        <svg viewBox="0 0 120 120" width={size} height={size} role="group" aria-label={label} className="ch-svg ch-fade">
          <PatternDefs id={id} segs={segments} />
          {total === 0 && <circle cx="60" cy="60" r={(R0 + R1) / 2} fill="none" stroke="var(--border)" strokeWidth={R1 - R0} />}
          {segments.filter((s) => s.value > 0).map((s) => {
            const a0 = a, a1 = a + (2 * Math.PI * s.value) / total
            a = a1
            const full = s.value === total
            return (
              <path key={s.key} d={full ? `${arc(60, 60, R0, R1, 0, Math.PI)} ${arc(60, 60, R0, R1, Math.PI, 2 * Math.PI)}` : arc(60, 60, R0, R1, a0, a1)}
                fill={`url(#${id}-${safeId(s.key)})`} stroke="var(--surface)" strokeWidth="1.2" tabIndex={0} role="img"
                aria-label={`${s.label}: ${fmt(s.value)} (${pct(s.value, total)}%)`} className={`ch-seg ${active === s.key ? 'is-active' : ''}`}
                onFocus={() => setActive(s.key)} onBlur={() => setActive(null)} onMouseEnter={() => setActive(s.key)} onMouseLeave={() => setActive(null)}
                onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && s.onClick) { e.preventDefault(); s.onClick() } }} onClick={s.onClick}>
                <title>{`${s.label}: ${fmt(s.value)} (${pct(s.value, total)}%)`}</title>
              </path>
            )
          })}
          {center && (
            <g textAnchor="middle">
              <text x="60" y="61" className="ch-center-v">{center.value}</text>
              <text x="60" y="73" className="ch-center-l">{center.label}</text>
            </g>
          )}
        </svg>
        <Items segs={segments} total={total} active={active} setActive={setActive} />
      </div>
    </Frame>
  )
}

export function StackedBar({ segments, tableAlt, label }: { segments: Seg[]; tableAlt?: TableAlt; label: string }) {
  const [active, setActive] = useState<string | null>(null)
  const total = segments.reduce((a, s) => a + s.value, 0)
  return (
    <Frame tableAlt={tableAlt}>
      <div className="ch-stack">
        <div className="ch-bar" role="group" aria-label={label}>
          {total === 0 && <span className="ch-bar-empty" />}
          {segments.filter((s) => s.value > 0).map((s) => (
            <button key={s.key} type="button" className={`ch-bar-seg pat-${s.pattern ?? 0} ${active === s.key ? 'is-active' : ''}`} style={{ flexGrow: s.value, ['--c' as string]: s.color }}
              aria-label={`${s.label}: ${fmt(s.value)} (${pct(s.value, total)}%)`} title={`${s.label}: ${fmt(s.value)}`}
              onClick={s.onClick} onFocus={() => setActive(s.key)} onBlur={() => setActive(null)} onMouseEnter={() => setActive(s.key)} onMouseLeave={() => setActive(null)} />
          ))}
        </div>
        <Items segs={segments} total={total} active={active} setActive={setActive} />
      </div>
    </Frame>
  )
}

export function BarList({ rows, tableAlt, label }: { rows: { key: string; label: string; parts: Seg[]; sub?: ReactNode }[]; tableAlt?: TableAlt; label: string }) {
  const max = Math.max(1, ...rows.map((r) => r.parts.reduce((a, p) => a + p.value, 0)))
  return (
    <Frame tableAlt={tableAlt}>
      <ul className="ch-barlist" aria-label={label}>
        {rows.map((r) => {
          const tot = r.parts.reduce((a, p) => a + p.value, 0)
          return (
            <li key={r.key}>
              <span className="ch-bl-l">{r.label}{r.sub && <span className="muted ch-bl-sub"> {r.sub}</span>}</span>
              <span className="ch-bl-track" role="group" aria-label={`${r.label}: ${r.parts.filter((p) => p.value).map((p) => `${p.label} ${p.value}`).join(', ') || 'none'}`}>
                <span className="ch-bl-fill" style={{ width: `${(100 * tot) / max}%` }}>
                  {r.parts.filter((p) => p.value > 0).map((p) => (
                    <Tooltip key={p.key} content={<><strong>{r.label}</strong><br />{p.label}: {fmt(p.value)}</>}>
                      <button type="button" className={`ch-bar-seg pat-${p.pattern ?? 0}`} style={{ flexGrow: p.value, ['--c' as string]: p.color }} aria-label={`${r.label}, ${p.label}: ${p.value}`} />
                    </Tooltip>
                  ))}
                </span>
              </span>
              <span className="ch-bl-v">{fmt(tot)}</span>
            </li>
          )
        })}
      </ul>
    </Frame>
  )
}

export function Ring({ value, color, center, label, size = 150 }: { value: number; color: string; center: ReactNode; label: string; size?: number }) {
  const r = 48, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value))
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} role="img" aria-label={label} className="ch-svg ch-fade">
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--surface-sunken)" strokeWidth="14" />
      <circle cx="60" cy="60" r={r} fill="none" strokeWidth="14" strokeDasharray={`${(c * v) / 100} ${c}`} transform="rotate(-90 60 60)" style={{ stroke: color }} />
      <text x="60" y="68" textAnchor="middle" className="ch-ring-v">{center}</text>
    </svg>
  )
}

export function Sparkline({ values, label, height = 28, tableAlt }: { values: (number | null)[]; label: string; height?: number; tableAlt?: TableAlt }) {
  const pts = values.map((v, i) => (v === null ? null : { i, v })).filter((p): p is { i: number; v: number } => p !== null)
  const w = 100
  let body: ReactNode = <span className="muted">n/a: a trend needs at least two data points.</span>
  if (pts.length > 1) {
    const lo = Math.min(...pts.map((p) => p.v)), hi = Math.max(...pts.map((p) => p.v)), span = hi - lo || 1
    const x = (i: number) => (values.length < 2 ? w / 2 : 2 + (i * (w - 4)) / (values.length - 1))
    const y = (v: number) => (hi === lo ? height / 2 : height - 3 - ((v - lo) / span) * (height - 6))
    const line = pts.map((p) => `${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
    const last = pts[pts.length - 1]
    body = (
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="ch-spark ch-fade" style={{ height }} role="img" aria-label={`${label}: latest ${fmt(last.v)}, min ${fmt(lo)}, max ${fmt(hi)}`}>
        {pts.length > 1 && <polyline points={line} fill="none" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" style={{ stroke: 'var(--primary-text)' }} />}
        <line x1={x(last.i)} x2={x(last.i)} y1={y(last.v)} y2={y(last.v)} strokeWidth="7" strokeLinecap="round" vectorEffect="non-scaling-stroke" style={{ stroke: 'var(--primary-text)' }} />
      </svg>
    )
  }
  return <Frame tableAlt={tableAlt}>{body}</Frame>
}

export function GateStrip({ gates }: { gates: { gate: string; pass: number; warn: number; fail: number }[] }) {
  return (
    <ul className="ch-gates" aria-label="Gate verdicts for this run">
      {gates.map((g) => {
        const v = g.fail ? 'FAIL' : g.warn ? 'WARN' : 'PASS'
        const cls = g.fail ? 'bad' : g.warn ? 'warn' : 'ok'
        return (
          <li key={g.gate}>
            <Tooltip content={<><strong>{g.gate}</strong>: {g.pass} pass, {g.warn} warn, {g.fail} fail checks in this run.</>}>
              <button type="button" className={`ch-gate tone-${cls}`}>
                <span className="ch-gate-id">{g.gate}</span>
                <span className="ch-gate-v"><Icon name={v === 'PASS' ? 'check' : v === 'WARN' ? 'warn' : 'x'} size={14} />{v === 'PASS' ? 'Pass' : v === 'WARN' ? 'Warn' : 'Fail'}</span>
                <span className="ch-gate-n">{fmt(g.pass)} / {fmt(g.warn)} / {fmt(g.fail)}</span>
              </button>
            </Tooltip>
          </li>
        )
      })}
    </ul>
  )
}
