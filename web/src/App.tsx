import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { getRuns, health, isOffline, startRun } from './api'
import { screens } from './screens/registry'
import type { CaseFilter, RunSummary } from './types'
import { UsageBadge } from './UsageBadge'

const store = {
  get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* storage blocked */ } },
}
const hashId = () => window.location.hash.replace(/^#\/?/, '')

export default function App() {
  const [api, setApi] = useState<'checking' | 'online' | 'offline'>('checking')
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [runId, setRunId] = useState<string | null>(store.get('ghost.run'))
  const [tab, setTab] = useState(() => (screens.some((s) => s.id === hashId()) ? hashId() : screens[0].id))
  const [caseId, setCaseId] = useState<string | null>(null)
  const [filter, setFilter] = useState<CaseFilter>({})
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)

  const go = useCallback((id: string) => { window.location.hash = `/${id}`; setTab(id) }, [])
  useEffect(() => {
    const on = () => { const h = hashId(); if (screens.some((s) => s.id === h)) setTab(h) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const r = await getRuns()
      setRuns(r)
      setRunId((cur) => (cur && r.some((x) => x.run_id === cur) ? cur : r[0]?.run_id ?? null))
    } catch (e) { setMsg(String(e)) }
  }, [])
  useEffect(() => { health().then((ok) => { setApi(ok ? 'online' : 'offline'); refresh() }) }, [refresh])
  useEffect(() => { if (runId) store.set('ghost.run', runId) }, [runId])

  const run = async () => {
    setBusy(true); setMsg('')
    try {
      const { run_id } = await startRun({ dataset: 'full', strict_temporal: false })
      await refresh(); setRunId(run_id); setTick((t) => t + 1); go('gate')
    } catch (e) { setMsg(String(e).includes('409') ? 'A run is already active.' : String(e)) }
    finally { setBusy(false) }
  }

  const Screen = (screens.find((s) => s.id === tab) ?? screens[0]).component
  return (
    <>
      <header className="top">
        <h1>Ghost Audit Console</h1>
        <span className={`pill api-${api}`} role="status">API {api}{isOffline() ? ' (offline demo data)' : ''}</span>
        <label className="grow">
          <span className="sr">Run</span>
          <select value={runId ?? ''} onChange={(e) => { setRunId(e.target.value || null); setCaseId(null) }}>
            {runs.length === 0 && <option value="">no runs</option>}
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id} ({r.cases} cases)</option>)}
          </select>
        </label>
        <button className="primary" onClick={run} disabled={busy}>{busy ? 'Starting...' : 'Run audit'}</button>
      </header>
      {msg && <p role="alert" className="bad pad">{msg}</p>}
      <nav aria-label="Screens" className="tabs">
        {screens.map((s) => (
          <a key={s.id} href={`#/${s.id}`} aria-current={s.id === tab ? 'page' : undefined}>{s.title}</a>
        ))}
      </nav>
      <main id="main">
        <Screen runId={runId} caseId={caseId} setCaseId={setCaseId} filter={filter} setFilter={setFilter} go={go} />
      </main>
      <UsageBadge runId={runId} tick={tick} />
    </>
  )
}
