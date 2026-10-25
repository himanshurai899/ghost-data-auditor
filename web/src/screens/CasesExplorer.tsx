// Cases explorer: filterable table + the selected case's detail (steps, resurrection timeline) and identity graph.
import { useEffect, useState } from 'react'
import { getCases } from '../api'
import type { CaseRow, ScreenProps, Status } from '../types'
import CaseDetail from './CaseDetail'
import IdentityGraph from './IdentityGraph'

const STATUSES: Status[] = ['COMPLETE', 'INCOMPLETE', 'NOT_APPLICABLE']

export function CasesExplorer({ runId, caseId, setCaseId, filter, setFilter }: ScreenProps) {
  const [rows, setRows] = useState<CaseRow[]>([])
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!runId) return
    getCases(runId, filter).then((r) => { setRows(r); setErr('') }).catch((e) => setErr(String(e)))
  }, [runId, filter])

  if (!runId) return <p className="muted">Select or start a run.</p>
  return (
    <section aria-label="Cases">
      <div className="toolbar">
        <label>Status{' '}
          <select value={filter.status ?? ''} onChange={(e) => setFilter({ ...filter, status: (e.target.value || undefined) as Status | undefined })}>
            <option value="">all</option>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        {filter.reported && <span className="chip">reported {filter.reported}</span>}
        {(filter.status || filter.reported) && <button onClick={() => setFilter({})}>Clear filter</button>}
        <span className="muted">{rows.length} cases</span>
      </div>
      {err && <p role="alert" className="bad">{err}</p>}
      <div className="split">
        <div className="tablewrap">
          <table>
            <thead><tr><th>Case</th><th>Reported</th><th>Audited</th><th>Steps</th><th>Warn</th><th>Fail</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.case_id} className={c.case_id === caseId ? 'sel' : ''}>
                  <td><button className="link" onClick={() => setCaseId(c.case_id)}>{c.case_id}</button></td>
                  <td>{c.reported}</td><td>{c.status}</td><td>{c.steps}</td><td>{c.warns}</td><td>{c.fails}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {caseId && (
          <aside aria-label="Case detail" className="card">
            <CaseDetail runId={runId} caseId={caseId} />
            <h3>Identity graph</h3>
            <IdentityGraph runId={runId} caseId={caseId} />
          </aside>
        )}
      </div>
    </section>
  )
}
