// THE ONE FILE other PRs edit to add or replace screens. Each component receives ScreenProps (types.ts).
// Replace `component` for `cases`, `ask`, `redteam` with the real screen; keep the ids stable
// (GateBoard and ClaimTruth call go('cases') and use the shared filter/caseId).
import type { ScreenDef } from '../types'
import Ask from './Ask'
import { CasesExplorer } from './CasesExplorer'
import { ClaimTruth } from './ClaimTruth'
import { GateBoard } from './GateBoard'
import RedTeam from './RedTeam'

export const screens: ScreenDef[] = [
  { id: 'gate', title: 'Gate board', component: GateBoard },
  { id: 'claim', title: 'Claim vs truth', component: ClaimTruth },
  { id: 'cases', title: 'Cases', component: CasesExplorer },
  { id: 'ask', title: 'Ask', component: ({ runId }) => (runId ? <Ask runId={runId} /> : <p className="muted">Select or start a run.</p>) },
  { id: 'redteam', title: 'Red team', component: ({ runId }) => <RedTeam runId={runId ?? undefined} /> },
]
