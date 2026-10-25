import type { ReactNode } from 'react'
import { getTimeline, useAsync, useDemo } from './client.ts'
import type { Async, TimelineItem } from './client.ts'
import './screens.css'

export function DemoBadge() {
  return useDemo() ? <span className="s-demo" role="status">demo data (API unreachable)</span> : null
}

/** Loading / error wrapper shared by the screens. */
export function Gate<T>({ a, children }: { a: Async<T>; children: (d: T) => ReactNode }) {
  if (a.state === 'loading') return <div className="s-state" role="status">Loading…</div>
  if (a.state === 'error') return <div className="s-state err" role="alert">Could not load: {a.error}</div>
  return <>{children(a.data)}</>
}

const RISK = new Set(['ACTIVE', 'RESTORE_RISK', 'RISK', 'ENABLED', 'RUNNING'])
const REDACTED = new Set(['REDACTED', 'ANONYMIZED', 'BLOCKED', 'DISABLED'])
function look(obs: string): { cls: string; icon: string } {
  const o = obs.toUpperCase()
  if (o === 'PRESENT') return { cls: 'amber', icon: '● ' }
  if (o === 'ABSENT') return { cls: 'green', icon: '✓ ' }
  if (RISK.has(o)) return { cls: 'red', icon: '▲ ' }
  if (REDACTED.has(o)) return { cls: 'blue', icon: '■ ' }
  return { cls: 'plain', icon: '○ ' }
}

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

type Entry = { t: number; kind: 'mk'; label: string; cls: string; at: string } | { t: number; kind: 'it'; it: TimelineItem }

export default function Timeline({ caseId, runId }: { runId: string; caseId: string }) {
  const a = useAsync(() => getTimeline(runId, caseId), [runId, caseId])
  return (
    <section className="screen" aria-label={`Resurrection timeline for ${caseId}`}>
      <div className="s-row"><h3>Resurrection timeline</h3><DemoBadge /></div>
      <Gate a={a}>
        {(d) => {
          if (!d.items.length) return <div className="s-state">No observations for this case.</div>
          const mk = (label: string, at: string, cls = ''): Entry => ({ t: ms(at), kind: 'mk', label, cls, at })
          const entries: Entry[] = [
            mk('requested', d.requested_at), mk('reported', d.reported_at), mk('audit_at', d.audit_at, 'audit'),
            ...d.items.map((it): Entry => ({ t: ms(it.observed_at), kind: 'it', it })),
          ].sort((x, y) => x.t - y.t)
          const lo = entries[0].t, span = Math.max(entries[entries.length - 1].t - lo, 1)
          // greedy lane packing so wide-screen cards do not overlap
          const lanes: number[] = []
          const laneOf = (x: number) => { let l = lanes.findIndex((end) => x - end > 17); if (l < 0) { l = lanes.length; lanes.push(0) } lanes[l] = x; return l }
          let nLane = 1
          const rows = entries.map((e, i) => {
            const x = ((e.t - lo) / span) * 100
            if (e.kind === 'mk') return (
              <li key={`m${i}`} className={`tl-mk ${e.cls}`} style={{ ['--x' as string]: `${x}%` }}>
                {e.label} · {fmt(e.at)}
              </li>
            )
            const { it } = e
            const lane = laneOf(x); nLane = Math.max(nLane, lane + 1)
            const lk = look(it.observation)
            const name = `${it.is_claim ? 'Claim' : 'Observed'}: ${it.system_id} ${it.resource_id} ${it.observation} at ${fmt(it.observed_at)}${it.citable ? '' : ', after audit, not citable'}`
            return (
              <li key={`i${i}`} tabIndex={0} aria-label={name} title={name}
                className={`tl-it tl-${lk.cls} ${it.is_claim ? 'claim' : ''} ${it.citable ? '' : 'late'} ${x > 70 ? 'flip' : ''}`}
                style={{ ['--x' as string]: `${x}%`, ['--lane' as string]: lane }}>
                <div className="obs">{lk.icon}{it.observation}{it.is_claim ? ' (claim)' : ''}</div>
                <div className="t">{it.system_id} / {it.resource_id}</div>
                <div className="t s-muted">{fmt(it.observed_at)}</div>
                <div className="s-row" style={{ gap: 4, marginTop: 4 }}>
                  <span className="chip plain ev">{it.evidence_id || 'no evidence id'}</span>
                  {!it.citable && <span className="chip plain">not citable (after audit)</span>}
                  {it.is_claim && <span className="chip plain">claim</span>}
                </div>
              </li>
            )
          })
          return (
            <>
              <p className="tl-caption" role="note">{story(d.items)}</p>
              <ol className="tl-list" style={{ ['--lanes' as string]: nLane }}>{rows}</ol>
              <div className="tl-legend" aria-label="Legend">
                <span className="chip amber">● PRESENT</span><span className="chip green">✓ ABSENT</span>
                <span className="chip red">▲ active flow / restore risk</span><span className="chip blue">■ redacted / anonymized</span>
                <span className="chip plain">dashed = claim, solid = file observation</span>
              </div>
            </>
          )
        }}
      </Gate>
    </section>
  )
}
