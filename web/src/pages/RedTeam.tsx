// Page entry point for #/redteam.
import RedTeam from '../screens/RedTeam'
import type { ScreenProps } from '../types'
import { PageHeader } from '../ui'

export default function RedTeamPage({ runId }: ScreenProps) {
  return (
    <>
      <PageHeader title="Red team" subtitle="Try to trick the intent classifier with injected request text, and see why the audit verdict cannot move." />
      <RedTeam runId={runId ?? undefined} />
    </>
  )
}
