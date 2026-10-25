// #/cases (list) and #/cases/<id> (case page with the ranked evidence chain). The filter lives in the shell, so Back keeps it.
import { PageHeader } from '../ui'
import CaseList from '../case/CaseList'
import CasePage from '../case/CasePage'
import type { ScreenProps } from '../types'
import './cases.css'

export default function Cases({ runId, caseId, setCaseId, filter, setFilter }: ScreenProps) {
  if (caseId) return <CasePage key={`${runId}/${caseId}`} runId={runId} caseId={caseId} filter={filter} setCaseId={setCaseId} />
  return (
    <>
      <PageHeader title="Cases" subtitle="Every audited request. Open one to see its ranked evidence chain, resurrection timeline and identity graph." />
      <CaseList runId={runId} filter={filter} setFilter={setFilter} setCaseId={setCaseId} />
    </>
  )
}
