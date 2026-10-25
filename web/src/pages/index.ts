// THE page registry. One file, one array: page agents edit ONLY their own entry (replace `component`), never the paths.
// PageDef (types.ts): { path, title, icon, nav, component }. `path` is the hash segment ('' = #/, 'cases' also serves #/cases/<id>).
// Every component receives ScreenProps (types.ts). Order here is the order in the left rail / tab bar.
import type { PageDef } from '../types'
import { AskPage, CasesPage, ComingCost, ComingDashboard, ComingSettings, LivePage, RedTeamPage } from './legacy'
import Landing from './Landing'

export const pages: PageDef[] = [
  { path: '', title: 'Overview', icon: 'pipeline', nav: true, component: Landing },
  { path: 'dashboard', title: 'Dashboard', icon: 'chart', nav: true, component: ComingDashboard }, // page agent replaces
  { path: 'cases', title: 'Cases', icon: 'file', nav: true, component: CasesPage },
  { path: 'live', title: 'Live run', icon: 'gate', nav: true, component: LivePage },
  { path: 'ask', title: 'Ask', icon: 'search', nav: true, component: AskPage },
  { path: 'redteam', title: 'Red team', icon: 'shield', nav: true, component: RedTeamPage },
  { path: 'cost', title: 'Cost', icon: 'database', nav: true, component: ComingCost }, // page agent replaces
  { path: 'settings', title: 'Settings', icon: 'cog', nav: true, component: ComingSettings }, // page agent replaces
]
