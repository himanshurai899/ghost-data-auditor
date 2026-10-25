// Page entry point for #/ask.
import Ask from '../screens/Ask'
import type { ScreenProps } from '../types'
import { EmptyState, PageHeader } from '../ui'

export default function AskPage({ runId, startAudit, starting }: ScreenProps) {
  return (
    <>
      <PageHeader title="Ask the auditor" subtitle="Questions about a run, answered from its audit trail with citations." />
      {runId ? <Ask runId={runId} /> : (
        <EmptyState icon="search" title="No run to ask about" text="Start an audit or pick a run in the top bar. Answers are grounded in a single run's trail."
          action={<button type="button" className="ui-btn is-primary" disabled={starting} onClick={() => { void startAudit() }}>Run audit</button>} />
      )}
    </>
  )
}
