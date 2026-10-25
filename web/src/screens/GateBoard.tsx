// Live run board: the landing pipeline (stages S0-S8, gates G1-G7) lights up as SSE events stream in.
// Events are buffered in a ref and flushed to state every 150 ms; the polite live region updates every 5 s.
import { useEffect, useMemo, useRef, useState } from 'react'
import { getRun, openEvents } from '../api'
import { GATES, STAGES } from '../pages/pipelineData'
import type { RunDetail, ScreenProps, TrailEvent } from '../types'
import { Button, Card, EmptyState, Icon, Segmented, Skeleton, StatCard, StatusBadge, Tooltip } from '../ui'
import '../live/live.css'

type Level = 'PASS' | 'WARN' | 'FAIL'
const RANK: Record<Level, number> = { PASS: 1, WARN: 2, FAIL: 3 }
// Real trail stage names (code/ghost/pipeline.py) -> pipeline nodes. The planner emits no event of its own on success, so
// a case's `contract` event (planning is done, steps are checked) lights S5-S7; `plan` appears only when planning fails.
const NODES: Record<string, string[]> = {
  load: ['S0'], ingest: ['S1'], intent: ['S2'], identity: ['S3'], link: ['S4'], plan: ['S5', 'S6', 'S7'], contract: ['S5', 'S6', 'S7'], emit: ['S8'], release: ['S8'],
}
const LOG_CAP = 200   // events kept for the on-screen log
const FLAG_CAP = 500  // flagged cases kept
const SHOW = 100      // rows rendered per list
const gateStage = (after: string) => after.split(' ')[0]

interface Flag { case_id: string; verdict: 'WARN' | 'FAIL'; gate: string; summary: string }
interface Tally { PASS: number; WARN: number; FAIL: number }
interface LogRow { key: number; e: TrailEvent }
interface Board {
  seen: number; done: number; total: number; first: number; last: number
  nodes: Record<string, number>; current: string
  gates: Record<string, Tally>
  warns: number; fails: number
  log: LogRow[]
  flags: Map<string, Flag>; runFlags: Flag[]
}
const empty = (): Board => ({ seen: 0, done: 0, total: 0, first: 0, last: 0, nodes: {}, current: '', gates: {}, warns: 0, fails: 0, log: [], flags: new Map(), runFlags: [] })

function ingest(s: Board, e: TrailEvent) {
  const now = performance.now()
  if (!s.first) s.first = now
  s.last = now
  s.seen++
  const ns = NODES[e.stage]
  if (ns) { if (e.stage !== 'release') for (const n of ns) s.nodes[n] = (s.nodes[n] ?? 0) + 1; s.current = ns[ns.length - 1] }
  if (e.stage === 'load') s.total = Number(/Loaded (\d+) requests/.exec(e.summary)?.[1] ?? 0)
  if (e.stage === 'emit') s.done++
  const v = e.verdict as Level | null | undefined
  if (e.gate && v && v in RANK) (s.gates[e.gate] ??= { PASS: 0, WARN: 0, FAIL: 0 })[v]++
  if (v === 'WARN') s.warns++
  if (v === 'FAIL') s.fails++
  if (v === 'WARN' || v === 'FAIL') {
    const f: Flag = { case_id: e.case_id ?? '', verdict: v, gate: e.gate ?? e.stage, summary: e.summary }
    if (!f.case_id) { if (s.runFlags.length < FLAG_CAP) s.runFlags.push(f) }
    else {
      const old = s.flags.get(f.case_id)
      if (old) { if (RANK[v] > RANK[old.verdict]) s.flags.set(f.case_id, f) } else if (s.flags.size < FLAG_CAP) s.flags.set(f.case_id, f)
    }
  }
  s.log.unshift({ key: s.seen, e })
  if (s.log.length > LOG_CAP) s.log.length = LOG_CAP
}

const fmt = (ms: number) => { const s = Math.floor(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` }
const gateLevel = (g?: Tally): Level | 'none' => (!g ? 'none' : g.FAIL ? 'FAIL' : g.WARN ? 'WARN' : 'PASS')

export function GateBoard({ runId, setCaseId, startAudit, starting, onDone }: ScreenProps & { onDone?: () => void }) {
  const [b, setB] = useState<Board>(empty)
  const [finished, setFinished] = useState(false)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [loadErr, setLoadErr] = useState(false)
  const [paused, setPaused] = useState(false)
  const [snap, setSnap] = useState<LogRow[]>([])
  const [filter, setFilter] = useState<'ALL' | Level>('ALL')
  const [, setTick] = useState(0)
  const [announce, setAnnounce] = useState('')
  const buf = useRef<Board>(empty())
  const dirty = useRef(false)
  const doneRef = useRef(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    buf.current = empty(); doneRef.current = false
    setB(empty()); setFinished(false); setRun(null); setLoadErr(false); setPaused(false); setAnnounce('')
    if (!runId) return
    getRun(runId).then(setRun).catch(() => setLoadErr(true))
    const close = openEvents(runId, (e: TrailEvent) => { ingest(buf.current, e); dirty.current = true }, () => {
      doneRef.current = true; dirty.current = true; setFinished(true); onDoneRef.current?.()
      getRun(runId).then(setRun).catch(() => {})
    })
    const flush = setInterval(() => {
      if (dirty.current) { dirty.current = false; setB({ ...buf.current }) } else if (!doneRef.current) setTick((t) => t + 1) // keep elapsed ticking
    }, 150)
    const say = setInterval(() => {
      const s = buf.current
      if (s.seen && !doneRef.current) setAnnounce(`${s.done} cases audited, ${s.warns} warnings, ${s.fails} failures.`)
    }, 5000)
    return () => { close(); clearInterval(flush); clearInterval(say) }
  }, [runId])

  useEffect(() => {
    if (finished) setAnnounce(`Run finished: ${buf.current.done} cases audited, ${buf.current.warns} warnings, ${buf.current.fails} failures.`)
  }, [finished])

  const total = run?.cases || b.total
  const processed = b.done
  const pct = finished ? 100 : total ? Math.min(100, Math.round((processed / total) * 100)) : 0
  const elapsed = b.first ? (finished ? b.last : performance.now()) - b.first : 0
  const rate = elapsed > 800 ? processed / (elapsed / 1000) : 0
  const flags = useMemo(() => [...b.flags.values()].sort((x, y) => RANK[y.verdict] - RANK[x.verdict]), [b.seen]) // eslint-disable-line react-hooks/exhaustive-deps -- the Map is mutated in place
  const shownLog = (paused ? snap : b.log).filter((r) => filter === 'ALL' || r.e.verdict === filter)
  const busy = run?.running === true

  const startBtn = (
    <Button variant="primary" icon="play" loading={starting} disabled={busy} onClick={() => { void startAudit() }}>
      {busy ? 'Run in progress' : 'Run audit'}
    </Button>
  )

  if (!runId) {
    return (
      <EmptyState icon="play" title="No run to watch yet"
        text="Start a full audit and this page lights up the pipeline stage by stage as the API streams events. You can also pick an earlier run in the top bar and replay it."
        action={startBtn} />
    )
  }
  if (loadErr && !b.seen) {
    return <EmptyState icon="warn" title="Could not load this run" text="The API did not return this run. Check that the backend is running, or pick another run in the top bar." action={startBtn} />
  }

  const idle = !b.seen && !finished
  const state = finished ? 'finished' : busy || b.seen ? 'streaming' : 'waiting'
  return (
    <section className="lv" aria-label="Live run board">
      <p className="sr" role="status" aria-live="polite">{announce}</p>

      <Card
        title={<span className="lv-title">Pipeline <span className={`lv-live is-${state}`}>{state}</span></span>}
        actions={startBtn}>
        {idle && (
          <p className="lv-hint" role="note"><Icon name="info" size={16} />
            <span>Waiting for the first event of run <code>{runId}</code>.{' '}
              {busy ? 'The run is active, events appear in a moment.' : 'If nothing arrives this run is not active: press Run audit to start a new one.'}</span></p>
        )}
        <ol className="lv-pipe" aria-label="Pipeline stages">
          {STAGES.map((s) => {
            const n = b.nodes[s.id] ?? 0
            const perCase = s.id !== 'S0' && s.id !== 'S1'
            const on = n > 0
            const cur = !finished && b.current === s.id
            const full = finished || (perCase ? total > 0 && n >= total : on)
            return (
              <li key={s.id} className={`lv-node ${on ? 'is-on' : ''} ${cur ? 'is-cur' : ''} ${full ? 'is-full' : ''}`}>
                <Tooltip content={<><span className="tt-title">{s.id} {s.name}</span>{s.purpose}</>}>
                  <button type="button" className="lv-nodebtn" aria-label={`${s.id} ${s.name}: ${on ? (perCase ? `${n} events` : 'complete') : 'not reached'}`}>
                    <span className="lv-ico"><Icon name={full ? 'check' : s.icon} size={18} /></span>
                    <b>{s.id}</b><span>{s.name}</span>
                    <small>{perCase ? (on ? n : '-') : on ? 'done' : '-'}</small>
                  </button>
                </Tooltip>
              </li>
            )
          })}
        </ol>
        <ol className="lv-gates" aria-label="Gate checkpoints">
          {GATES.map((g) => {
            const c = b.gates[g.id]
            const lv = gateLevel(c)
            return (
              <li key={g.id} className={`lv-gate g-${lv}`} title={`after ${gateStage(g.after)}`}>
                <Tooltip content={<><span className="tt-title">{g.id} {g.name}</span>{g.check}<span className="tt-row"><b>On fail:</b> {g.onFail}</span></>}>
                  <button type="button" className="lv-gatebtn" aria-label={`${g.id} ${g.name}: ${lv === 'none' ? 'pending' : lv}${c ? `, ${c.PASS} pass, ${c.WARN} warn, ${c.FAIL} fail` : ''}`}>
                    <Icon name={lv === 'FAIL' ? 'x' : lv === 'WARN' ? 'warn' : lv === 'PASS' ? 'check' : 'gate'} size={16} />
                    <b>{g.id}</b><span>{g.name}</span>
                    <small>{c ? `${c.PASS}/${c.WARN}/${c.FAIL}` : 'pending'}</small>
                  </button>
                </Tooltip>
              </li>
            )
          })}
        </ol>
        <p className="lv-keynote">Gate counts read pass / warn / fail. A gate turns amber after any warning and red after any failure.</p>
        <div className="lv-bar" role="progressbar" aria-label="Cases audited" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}><i style={{ width: `${pct}%` }} /></div>
      </Card>

      <div className="lv-stats">
        <StatCard label="Cases audited" value={`${processed}${total ? ` / ${total}` : ''}`} sub={`${pct}%`} icon="file" loading={idle} />
        <StatCard label="Throughput" value={rate ? `${rate.toFixed(rate < 10 ? 1 : 0)}/s` : '-'} sub="cases per second" icon="flow" />
        <StatCard label="Elapsed" value={b.first ? fmt(elapsed) : '-'} sub={`${b.seen} events`} icon="clock" />
        <StatCard label="Warnings / failures" value={<>{b.warns} / {b.fails}</>} tone={b.fails ? 'bad' : b.warns ? 'warn' : 'neutral'} icon="warn" />
      </div>

      <div className="lv-cols">
        <Card title="Flagged cases" actions={<span className="lv-count">{flags.length}{b.flags.size >= FLAG_CAP ? '+' : ''}</span>}>
          {flags.length === 0 && b.runFlags.length === 0 ? (
            <div className="lv-empty">{idle ? <Skeleton h={14} w="60%" /> : 'Nothing flagged so far.'}</div>
          ) : (
            <ul className="lv-flags">
              {b.runFlags.map((f, i) => (
                <li key={`r${i}`}><StatusBadge status={f.verdict} /><span className="lv-gid">{f.gate}</span><span className="lv-sum">{f.summary}</span></li>
              ))}
              {flags.slice(0, SHOW).map((f) => (
                <li key={f.case_id}>
                  <StatusBadge status={f.verdict} />
                  <button type="button" className="lv-case" onClick={() => setCaseId(f.case_id)} aria-label={`Open ${f.case_id}, ${f.verdict} at ${f.gate}`}>{f.case_id}</button>
                  <span className="lv-gid">{f.gate}</span><span className="lv-sum">{f.summary}</span>
                </li>
              ))}
              {flags.length > SHOW && <li className="lv-more">Showing the {SHOW} most severe of {flags.length}.</li>}
            </ul>
          )}
        </Card>

        <Card title="Event stream" actions={
          <div className="lv-tools">
            <Segmented<'ALL' | Level> label="Filter by verdict" value={filter} onChange={setFilter}
              options={[{ value: 'ALL', label: 'All' }, { value: 'PASS', label: 'Pass' }, { value: 'WARN', label: 'Warn' }, { value: 'FAIL', label: 'Fail' }]} />
            <Button variant="secondary" aria-pressed={paused} onClick={() => { if (!paused) setSnap(buf.current.log.slice()); setPaused(!paused) }}>
              {paused ? 'Resume list' : 'Pause list'}
            </Button>
          </div>}>
          {paused && <p className="lv-hint" role="note"><Icon name="info" size={16} /><span>List paused. The stream and counters keep running.</span></p>}
          {shownLog.length === 0 ? (
            <div className="lv-empty">{idle ? 'No events yet.' : 'No events match this filter.'}</div>
          ) : (
            <ul className="lv-log" aria-label={`Latest events, newest first`}>
              {shownLog.slice(0, SHOW).map(({ key, e }) => (
                <li key={key}>
                  {e.verdict ? <StatusBadge status={e.verdict as Level} /> : <span className="lv-nov" aria-label="no verdict">-</span>}
                  <span className="lv-stage">{e.stage}</span>
                  {e.case_id ? <button type="button" className="lv-case" onClick={() => setCaseId(e.case_id ?? null)}>{e.case_id}</button> : <span className="lv-gid">run</span>}
                  <span className="lv-sum">{e.summary}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </section>
  )
}
