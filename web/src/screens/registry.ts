// THE ONE FILE other PRs edit to add or replace screens. Each component receives ScreenProps (types.ts).
// Replace `component` for `cases`, `ask`, `redteam` with the real screen; keep the ids stable
// (GateBoard and ClaimTruth call go('cases') and use the shared filter/caseId).
import type { ScreenDef } from '../types'
import { CasesPlaceholder } from './CasesPlaceholder'
import { ClaimTruth } from './ClaimTruth'
import { GateBoard } from './GateBoard'
import { Placeholder } from './Placeholder'

export const screens: ScreenDef[] = [
  { id: 'gate', title: 'Gate board', component: GateBoard },
  { id: 'claim', title: 'Claim vs truth', component: ClaimTruth },
  { id: 'cases', title: 'Cases', component: CasesPlaceholder },
  { id: 'ask', title: 'Ask', component: Placeholder },
  { id: 'redteam', title: 'Red team', component: Placeholder },
]
