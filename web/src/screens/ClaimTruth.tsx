import { useEffect, useState } from 'react'
import { getRun } from '../api'
import type { Reported, RunDetail, ScreenProps, Status } from '../types'

const ROWS: Reported[] = ['COMPLETE', 'PARTIALLY_COMPLETE', 'NOT_STARTED']
const COLS: Status[] = ['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE']

export function ClaimTruth({ runId, setFilter, go }: ScreenProps) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    setRun(null)
    if (runId) getRun(runId).then(setRun).catch((e) => setErr(String(e)))
  }, [runId])

  if (!runId) return <p className="muted">Select or start a run.</p>
  if (err) return <p role="alert" className="bad">{err}</p>
  if (!run) return <p className="muted">Loading...</p>

  const m = run.claim_matrix.reported
  const claimed = COLS.reduce((a, c) => a + m.COMPLETE[c], 0)
  const ghosts = m.COMPLETE.INCOMPLETE
  const pct = claimed ? Math.round((ghosts / claimed) * 1000) / 10 : 0
  const open = (reported: Reported, status: Status) => { setFilter({ reported, status }); go('cases') }

  return (
    <section aria-label="Claim versus truth">
      <div className="ghost card">
        <div className="big" aria-live="polite">{ghosts}</div>
        <div>
          <h2>ghosts found</h2>
          <p>
            The workflow reported <strong>{claimed}</strong> requests as COMPLETE, but the audit at each case's
            audit time found <strong>{ghosts}</strong> ({pct}%) still INCOMPLETE: personal data remained or could come back.
          </p>
        </div>
      </div>
      <h3>Reported (rows) vs audited (columns)</h3>
      <div className="tablewrap">
        <table className="matrix">
          <caption className="sr">Counts of cases by workflow-reported status and audited status. Select a count to filter the Cases tab.</caption>
          <thead><tr><th scope="col">Reported</th>{COLS.map((c) => <th scope="col" key={c}>Audited {c}</th>)}</tr></thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r}>
                <th scope="row">{r}</th>
                {COLS.map((c) => (
                  <td key={c} className={r === 'COMPLETE' && c === 'INCOMPLETE' ? 'ghostcell' : ''}>
                    <button className="cell" onClick={() => open(r, c)} aria-label={`Reported ${r}, audited ${c}: ${m[r][c]} cases`}>{m[r][c]}</button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
