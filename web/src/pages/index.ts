// THE page registry. Each page lives in its own file (pages/<Name>.tsx); page agents edit only that file, never this one.
// PageDef (types.ts): { path, title, icon, nav, component }. `path` is the hash segment ('' = #/, 'cases' also serves #/cases/<id>).
// Every component receives ScreenProps (types.ts). Order here is the order in the left rail / tab bar.
import type { PageDef } from '../types'
import Ask from './Ask'
import Cases from './Cases'
import Cost from './Cost'
import Dashboard from './Dashboard'
import Landing from './Landing'
import Live from './Live'
import RedTeam from './RedTeam'
import Settings from './Settings'

export const pages: PageDef[] = [
  { path: '', title: 'Overview', icon: 'pipeline', nav: true, component: Landing },
  { path: 'dashboard', title: 'Dashboard', icon: 'chart', nav: true, component: Dashboard },
  { path: 'cases', title: 'Cases', icon: 'file', nav: true, component: Cases },
  { path: 'live', title: 'Live run', icon: 'gate', nav: true, component: Live },
  { path: 'ask', title: 'Ask', icon: 'search', nav: true, component: Ask },
  { path: 'redteam', title: 'Red team', icon: 'shield', nav: true, component: RedTeam },
  { path: 'cost', title: 'Cost', icon: 'database', nav: true, component: Cost },
  { path: 'settings', title: 'Settings', icon: 'cog', nav: true, component: Settings },
]
