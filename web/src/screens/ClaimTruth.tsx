// "Result so far": workflow-reported status (rows) vs audited status (columns) as a heat table with ghost emphasis.
// Clicking a cell sets the shared Cases filter and opens Cases. Refetches every 4 s while the run is active.
import { useEffect, useState } from 'react'
import { getRun } from '../api'
import type { Reported, RunDetail, ScreenProps, Status } from '../types'
import { Button, Card, EmptyState, Icon, Skeleton } from '../ui'
import '../live/live.css'

const ROWS: Reported[] = ['COMPLETE', 'PARTIALLY_COMPLETE', 'NOT_STARTED']
const COLS: Status[] = ['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE']
const pretty = (s: string) => s.replace(/_/g, ' ').toLowerCase()

export function ClaimTruth({ runId, setFilter, go, refreshKey }: ScreenProps & { refreshKey?: unknown }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    setRun(null); setErr(false)
    if (!runId) return
    let live = true
    getRun(runId).then((r) => { if (live) setRun(r) }).catch(() => { if (live) setErr(true) })
    return () => { live = false }
  }, [runId, refreshKey])

  useEffect(() => {
    if (!runId || !run?.running) return
    const t = setInterval(() => { getRun(runId).then(setRun).catch(() => {}) }, 4000)
    return () => clearInterval(t)
  }, [runId, run?.running])

  if (!runId) return null
  if (err) return <EmptyState icon="warn" title="Could not load the result" text="The run summary was not returned. It appears here once the API is reachable." />
  if (!run) return <Card title="Result so far"><Skeleton h={120} /></Card>

  const m = run.claim_matrix.reported
  const rowTotal = (r: Reported) => COLS.reduce((a, c) => a + m[r][c], 0)
  const claimed = rowTotal('COMPLETE')
  const ghosts = m.COMPLETE.INCOMPLETE
  const pct = claimed ? Math.round((ghosts / claimed) * 1000) / 10 : 0
  const open = (reported: Reported, status: Status) => { setFilter({ reported, status }); go('cases') }
  const empty = ROWS.every((r) => rowTotal(r) === 0)

  return (
    <Card title="Result so far" actions={run.running ? <span className="lv-live is-streaming">updating</span> : undefined}>
      {empty ? (
        <p className="lv-empty">No audited cases yet. Counts appear as the run produces output.</p>
      ) : (
        <>
          <div className="ct-ghost">
            <span className="ct-big" aria-live="polite"><Icon name="eye" size={22} /> {ghosts}</span>
            <p>
              The workflow reported <strong>{claimed}</strong> requests as COMPLETE, but the audit at each case's audit time found{' '}
              <strong>{ghosts}</strong> ({pct}%) still INCOMPLETE: personal data remained or could come back. These are the ghosts.
            </p>
          </div>
          <div className="ct-wrap">
            <table className="ct">
              <caption className="sr">Cases by workflow-reported status (rows) and audited status (columns). Each count is a button that filters the Cases page.</caption>
              <thead><tr><th scope="col">Workflow reported</th>{COLS.map((c) => <th scope="col" key={c}>Audited {pretty(c)}</th>)}</tr></thead>
              <tbody>
                {ROWS.map((r) => {
                  const t = rowTotal(r)
                  return (
                    <tr key={r}>
                      <th scope="row">{pretty(r)}<small>{t} cases</small></th>
                      {COLS.map((c) => {
                        const v = m[r][c]
                        const share = t ? v / t : 0
                        const ghost = r === 'COMPLETE' && c === 'INCOMPLETE'
                        return (
                          <td key={c} className={ghost ? 'is-ghost' : ''} style={{ ['--i' as string]: share }}>
                            <button type="button" className="ct-cell" onClick={() => open(r, c)}
                              aria-label={`Reported ${pretty(r)}, audited ${pretty(c)}: ${v} cases, ${Math.round(share * 100)} percent of row${ghost ? '. Ghosts.' : ''}`}>
                              <b>{v}</b><small>{Math.round(share * 100)}%</small>
                              {ghost && <span className="ct-tag">ghosts</span>}
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="lv-keynote">Percentages are the share of each row. Shading grows with the share. Select a cell to list those cases.</p>
          <Button variant="secondary" onClick={() => open('COMPLETE', 'INCOMPLETE')}>Open the {ghosts} ghost cases</Button>
        </>
      )}
    </Card>
  )
}
