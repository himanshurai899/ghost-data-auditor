// App shell: left rail (bottom tab bar < 768px), top bar (run selector, API health, theme), skip link, <main>.
import type { ReactNode } from 'react'
import { isOffline } from '../api'
import type { PageDef, RunSummary } from '../types'
import { Button, Icon, Segmented } from '../ui'
import { href } from './router'
import type { Theme } from './theme'
import './shell.css'

export function Shell({ pages, active, runs, runId, setRunId, api, theme, setTheme, startAudit, starting, msg, children }: {
  pages: PageDef[]; active: string; runs: RunSummary[]; runId: string | null; setRunId: (id: string | null) => void
  api: 'checking' | 'online' | 'offline'; theme: Theme; setTheme: (t: Theme) => void
  startAudit: () => void; starting: boolean; msg: string; children: ReactNode
}) {
  const nav = pages.filter((p) => p.nav)
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="rail" aria-label="Primary">
        <a className="brand" href={href('')} aria-label="Ghost Audit Console, home">
          <span className="brand-mark"><Icon name="shield" size={22} /></span>
          <span className="brand-name">Ghost Audit<small>Deletion proof console</small></span>
        </a>
        <nav aria-label="Pages">
          {nav.map((p) => (
            <a key={p.path} href={href(p.path)} aria-current={p.path === active ? 'page' : undefined}>
              <Icon name={p.icon} size={20} /><span>{p.title}</span>
            </a>
          ))}
        </nav>
      </aside>
      <div className="content">
        <header className="topbar" aria-label="Console controls">
          <label className="run-select">
            <span className="sr">Run</span>
            <select value={runId ?? ''} onChange={(e) => setRunId(e.target.value || null)}>
              {runs.length === 0 && <option value="">no runs yet</option>}
              {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id} ({r.cases} cases)</option>)}
            </select>
          </label>
          <span className={`health is-${api}`} role="status">
            <Icon name={api === 'online' ? 'check' : api === 'checking' ? 'clock' : 'warn'} size={14} />
            API {api}{isOffline() ? ' (demo data)' : ''}
          </span>
          <span className="spacer" />
          <Segmented<Theme> label="Theme" value={theme} onChange={setTheme}
            options={[{ value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }, { value: 'system', label: 'Auto' }]} />
          <Button variant="primary" icon="play" loading={starting} onClick={startAudit}>Run audit</Button>
        </header>
        {msg && <p role="alert" className="shell-alert"><Icon name="warn" size={16} /> {msg}</p>}
        <main id="main" tabIndex={-1}>{children}</main>
      </div>
      <nav className="tabbar" aria-label="Pages (mobile)">
        {nav.map((p) => (
          <a key={p.path} href={href(p.path)} aria-current={p.path === active ? 'page' : undefined}>
            <Icon name={p.icon} size={20} /><span>{p.title}</span>
          </a>
        ))}
      </nav>
    </div>
  )
}
