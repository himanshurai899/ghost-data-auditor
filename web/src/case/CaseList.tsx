// Cases list: search, status and reported filters, sortable columns, ghost marker, 50 rows per page (cards on mobile).
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Button, Card, EmptyState, Field, Icon, Segmented, Skeleton, StatusBadge, Tooltip } from '../ui'
import { caseNum, getCaseList, useLoad } from '../caseApi'
import { href } from '../shell/router'
import type { CaseFilter, CaseRow, Reported, Status } from '../types'

const PAGE = 50
type SortKey = 'case' | 'status' | 'steps' | 'warns'
const SORTS: { key: SortKey; label: string }[] = [{ key: 'case', label: 'Case' }, { key: 'status', label: 'Audited' }, { key: 'steps', label: 'Steps' }, { key: 'warns', label: 'Warns' }]

export const isGhost = (c: { reported: string; status: string }) => c.reported === 'COMPLETE' && c.status === 'INCOMPLETE'

export function ReportedBadge({ r }: { r: Reported | string }) {
  if (r === 'COMPLETE') return <StatusBadge status="COMPLETE" label="Complete" />
  if (r === 'PARTIALLY_COMPLETE') return <StatusBadge status="WARN" label="Partial" />
  if (r === 'NOT_STARTED') return <StatusBadge status="NOT_APPLICABLE" label="Not started" />
  return <StatusBadge status={r} />
}

export function GhostMark() {
  return (
    <Tooltip content="Ghost: the workflow reported COMPLETE, but the audit at audit_at found the deletion INCOMPLETE.">
      <button type="button" className="cl-ghost"><Icon name="eye" size={14} />Ghost</button>
    </Tooltip>
  )
}

export function applyFilter(rows: CaseRow[], f: CaseFilter, q = '') {
  const s = q.trim().toLowerCase()
  return rows.filter((c) => (!f.status || c.status === f.status) && (!f.reported || c.reported === f.reported)
    && (!s || c.case_id.startsWith(s) || c.case_id.replace(/^case_0*/, '').startsWith(s.replace(/^0+/, ''))))
}

export default function CaseList({ runId, filter, setFilter, setCaseId }: {
  runId: string | null; filter: CaseFilter; setFilter: (f: CaseFilter) => void; setCaseId: (id: string | null) => void
}) {
  const [a, reload] = useLoad(() => (runId ? getCaseList(runId) : Promise.resolve([])), [runId])
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'case', dir: 1 })
  const [page, setPage] = useState(0)
  useEffect(() => setPage(0), [filter.status, filter.reported, q, sort])

  const all = a.state === 'ok' ? a.data : []
  const rows = useMemo(() => {
    const r = applyFilter(all, filter, q)
    const cmp = (x: CaseRow, y: CaseRow) => sort.key === 'case' ? caseNum(x.case_id) - caseNum(y.case_id)
      : sort.key === 'status' ? x.status.localeCompare(y.status) : x[sort.key] - y[sort.key]
    return [...r].sort((x, y) => sort.dir * cmp(x, y) || caseNum(x.case_id) - caseNum(y.case_id))
  }, [all, filter, q, sort])
  const pages = Math.max(1, Math.ceil(rows.length / PAGE))
  const cur = Math.min(page, pages - 1)
  const shown = rows.slice(cur * PAGE, cur * PAGE + PAGE)
  const filtered = !!(filter.status || filter.reported || q)
  const clear = () => { setFilter({}); setQ('') }
  const toggle = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }))

  if (!runId) return <EmptyState icon="file" title="No run selected" text="Start an audit or pick a run in the top bar to list its cases." />

  const th = (key: SortKey, label: string): ReactNode => (
    <th scope="col" aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="cl-sort" onClick={() => toggle(key)}>{label}<span aria-hidden="true">{sort.key === key ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}</span></button>
    </th>
  )

  return (
    <div className="stack">
      <Card as="section" title="Filters">
        <div className="cl-filters">
          <Field label="Search case id" hint="Prefix, for example case_33 or 33.">
            {(p) => <input {...p} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="case_33" autoComplete="off" />}
          </Field>
          <div className="cl-seg"><span className="cl-seg-l">Audited status</span>
            <Segmented<Status | 'all'> label="Audited status" value={filter.status ?? 'all'} onChange={(v) => setFilter({ ...filter, status: v === 'all' ? undefined : v })}
              options={[{ value: 'all', label: 'All' }, { value: 'COMPLETE', label: 'Complete' }, { value: 'INCOMPLETE', label: 'Incomplete' }, { value: 'NOT_APPLICABLE', label: 'Not applicable' }]} /></div>
          <div className="cl-seg"><span className="cl-seg-l">Reported status</span>
            <Segmented<Reported | 'all'> label="Reported status" value={filter.reported ?? 'all'} onChange={(v) => setFilter({ ...filter, reported: v === 'all' ? undefined : v })}
              options={[{ value: 'all', label: 'All' }, { value: 'COMPLETE', label: 'Complete' }, { value: 'PARTIALLY_COMPLETE', label: 'Partial' }, { value: 'NOT_STARTED', label: 'Not started' }]} /></div>
          <label className="cl-sortsel">Sort by
            <select value={`${sort.key}:${sort.dir}`} onChange={(e) => { const [k, d] = e.target.value.split(':'); setSort({ key: k as SortKey, dir: d === '1' ? 1 : -1 }) }}>
              {SORTS.flatMap((s) => [<option key={`${s.key}1`} value={`${s.key}:1`}>{s.label} ascending</option>, <option key={`${s.key}-1`} value={`${s.key}:-1`}>{s.label} descending</option>])}
            </select>
          </label>
        </div>
        <div className="cl-meta">
          <p role="status" aria-live="polite"><strong>{a.state === 'ok' ? rows.length : '…'}</strong> of {a.state === 'ok' ? all.length : '…'} cases{filtered ? ' match' : ''}</p>
          <Button variant="ghost" onClick={clear} disabled={!filtered}>Clear filters</Button>
        </div>
      </Card>

      {a.state === 'loading' && <Card><div className="cl-skel" role="status" aria-label="Loading cases">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} h={36} />)}</div></Card>}
      {a.state === 'error' && <EmptyState icon="warn" title="Could not load the cases" text={a.error} action={<Button variant="secondary" onClick={reload}>Retry</Button>} />}
      {a.state === 'ok' && rows.length === 0 && (
        <EmptyState icon="search" title={all.length ? 'No cases match these filters' : 'This run has no cases'} text={all.length ? 'Loosen the status filters or clear the search.' : 'Pick another run or start a new audit.'}
          action={filtered ? <Button variant="secondary" onClick={clear}>Clear filters</Button> : undefined} />
      )}
      {a.state === 'ok' && rows.length > 0 && (
        <Card flush>
          <div className="cl-scroll">
            <table className="cl-table">
              <caption className="sr">Audited cases</caption>
              <thead><tr>{th('case', 'Case')}<th scope="col">Reported</th>{th('status', 'Audited')}{th('steps', 'Steps')}{th('warns', 'Warns')}<th scope="col">Fails</th></tr></thead>
              <tbody>
                {shown.map((c) => (
                  <tr key={c.case_id} onClick={() => setCaseId(c.case_id)} className={isGhost(c) ? 'is-ghost' : ''}>
                    <td data-label="Case"><a className="cl-id" href={href('cases', c.case_id)} onClick={(e) => e.stopPropagation()}>{c.case_id}</a>{isGhost(c) && <span onClick={(e) => e.stopPropagation()}><GhostMark /></span>}</td>
                    <td data-label="Reported"><ReportedBadge r={c.reported} /></td>
                    <td data-label="Audited"><StatusBadge status={c.status} /></td>
                    <td data-label="Steps" className="num">{c.steps}</td>
                    <td data-label="Warns" className="num">{c.warns}</td>
                    <td data-label="Fails" className="num">{c.fails}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="cl-pager" aria-label="Pagination">
            <span className="muted">Showing {cur * PAGE + 1} to {cur * PAGE + shown.length} of {rows.length}</span>
            <Button variant="secondary" disabled={cur === 0} onClick={() => setPage(cur - 1)}>Previous</Button>
            <span aria-current="page">Page {cur + 1} of {pages}</span>
            <Button variant="secondary" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>Next</Button>
          </nav>
        </Card>
      )}
    </div>
  )
}
