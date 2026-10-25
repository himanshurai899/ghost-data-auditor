// Thin wrappers that adapt the existing screens to the page registry, plus the 'Coming next' placeholder.
import { ClaimTruth } from '../screens/ClaimTruth'
import { CasesExplorer } from '../screens/CasesExplorer'
import { GateBoard } from '../screens/GateBoard'
import Ask from '../screens/Ask'
import RedTeam from '../screens/RedTeam'
import type { ScreenProps } from '../types'
import { Button, EmptyState, PageHeader } from '../ui'
import type { IconName } from '../ui'

const NoRun = () => <EmptyState icon="play" title="No run selected" text="Start an audit or pick a run in the top bar." />

export const LivePage = (p: ScreenProps) => (<><PageHeader title="Live run" subtitle="Gates and stages as the pipeline works, streamed from the API." /><GateBoard {...p} /></>)
export const CasesPage = (p: ScreenProps) => (<><PageHeader title="Cases" subtitle="Filter every audited request and open the evidence behind its status." /><CasesExplorer {...p} /></>)
export const AskPage = ({ runId }: ScreenProps) => (<><PageHeader title="Ask the auditor" subtitle="Questions about a run, answered from its evidence with citations." />{runId ? <Ask runId={runId} /> : <NoRun />}</>)
export const RedTeamPage = ({ runId }: ScreenProps) => (<><PageHeader title="Red team" subtitle="Try to trick the intent classifier with injected request text." /><RedTeam runId={runId ?? undefined} /></>)

function Coming({ title, icon, text, go, children }: { title: string; icon: IconName; text: string; go: ScreenProps['go']; children?: React.ReactNode }) {
  return (
    <>
      <PageHeader title={title} />
      <EmptyState icon={icon} title="Coming next" text={text} action={<Button variant="secondary" onClick={() => go('')}>Back to overview</Button>} />
      {children}
    </>
  )
}
// Dashboard keeps the existing claim-vs-truth matrix reachable until the dashboard page replaces this entry.
export const ComingDashboard = (p: ScreenProps) => (
  <Coming title="Dashboard" icon="chart" go={p.go} text="KPI cards, status mix, findings by system and gate health land here. Meanwhile, the claim-versus-truth matrix:">
    <div style={{ marginTop: 24 }}>{p.runId ? <ClaimTruth {...p} /> : <NoRun />}</div>
  </Coming>
)
export const ComingCost = (p: ScreenProps) => <Coming title="Cost and metrics" icon="database" go={p.go} text="Calls, tokens, per-model cost and determinism facts for the selected run land here." />
export const ComingSettings = (p: ScreenProps) => <Coming title="Settings" icon="cog" go={p.go} text="The NVIDIA configurator (keys, models, connection test) lands here." />
