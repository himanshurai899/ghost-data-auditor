import { useEffect, useRef, useState } from 'react'
import { GATE_IDS, getRun, openEvents } from '../api'
import type { ScreenProps, TrailEvent } from '../types'

const STAGES = ['load', 'ingest', 'intent', 'identity', 'link', 'plan', 'contract', 'emit', 'release']
const CAP = 500 // max flagged rows kept in memory
type Level = 'PASS' | 'WARN' | 'FAIL'
const RANK: Record<Level, number> = { PASS: 1, WARN: 2, FAIL: 3 }

interface Board {
  seen: number
  stages: Record<string, number>
  gates: Record<string, Level>
  cases: Set<string>
  warns: number
  fails: number
  flagged: { key: number; case_id: string; gate: string; verdict: Level; summary: string }[]
  last: string
}
const empty = (): Board => ({ seen: 0, stages: {}, gates: {}, cases: new Set(), warns: 0, fails: 0, flagged: [], last: '' })

export function GateBoard({ runId, setCaseId, go }: ScreenProps) {
  const [b, setB] = useState<Board>(empty)
  const [done, setDone] = useState(false)
  const [total, setTotal] = useState(0)
  const buf = useRef<Board>(empty())
  const dirty = useRef(false)

  useEffect(() => {
    buf.current = empty(); setB(empty()); setDone(false); setTotal(0)
    if (!runId) return
    getRun(runId).then((r) => setTotal(r.cases)).catch(() => {})
    const close = openEvents(runId, (e: TrailEvent) => {
      const s = buf.current
      s.seen++
      s.stages[e.stage] = (s.stages[e.stage] ?? 0) + 1
      if (e.case_id) s.cases.add(e.case_id)
      s.last = e.summary
      const v = e.verdict as Level | null | undefined
      if (e.gate && v && v in RANK && (!s.gates[e.gate] || RANK[v] > RANK[s.gates[e.gate]])) s.gates[e.gate] = v
      if (v === 'WARN') s.warns++
      if (v === 'FAIL') s.fails++
      if ((v === 'WARN' || v === 'FAIL') && s.flagged.length < CAP)
        s.flagged.push({ key: s.seen, case_id: e.case_id ?? '', gate: e.gate ?? e.stage, verdict: v, summary: e.summary })
      dirty.current = true
    }, () => { dirty.current = true; setDone(true) })
    const t = setInterval(() => { if (dirty.current) { dirty.current = false; setB({ ...buf.current }) } }, 150)
    return () => { close(); clearInterval(t) }
  }, [runId])

  if (!runId) return <p className="muted">Press "Run audit" to stream a run, or pick a past run.</p>
  const denom = total || b.cases.size
  const pct = done ? 100 : denom ? Math.min(100, Math.round((b.cases.size / denom) * 100)) : 0
  return (
    <section aria-label="Live gate board">
      <div className="gates" role="list" aria-label="Gates">
        {GATE_IDS.map((g) => {
          const lv = b.gates[g]
          return <span key={g} role="listitem" className={`gate g-${lv ?? 'none'}`} aria-label={`${g} ${lv ?? 'pending'}`}>{g}<small>{lv ?? '...'}</small></span>
        })}
      </div>
      <div className="counters">
        <div className="card"><b>{b.cases.size}</b><span>cases processed{total ? ` / ${total}` : ''}</span></div>
        <div className="card"><b className="warn">{b.warns}</b><span>warnings</span></div>
        <div className="card"><b className="bad">{b.fails}</b><span>failures</span></div>
        <div className="card"><b>{done ? 'done' : 'live'}</b><span>{b.seen} events</span></div>
      </div>
      <div className="bar" role="progressbar" aria-label="Cases processed" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <i style={{ width: `${pct}%` }} />
      </div>
      <ul className="stages" aria-label="Stages">
        {STAGES.map((s) => <li key={s} className={b.stages[s] ? 'on' : ''}><span>{s}</span><b>{b.stages[s] ?? 0}</b></li>)}
      </ul>
      <p className="muted" aria-live="polite">{b.last}</p>
      <h3>Flagged ({b.flagged.length}{b.flagged.length >= CAP ? '+' : ''})</h3>
      {b.flagged.length === 0 ? <p className="muted">Nothing flagged yet.</p> : (
        <ul className="flagged">
          {b.flagged.map((f) => (
            <li key={f.key} className={f.verdict === 'FAIL' ? 'fl-fail' : 'fl-warn'}>
              <span className="tag">{f.verdict}</span>
              {f.case_id
                ? <button className="link" onClick={() => { setCaseId(f.case_id); go('cases') }}>{f.case_id}</button>
                : <span>run</span>}
              {' '}<span className="muted">{f.gate}</span> {f.summary}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
