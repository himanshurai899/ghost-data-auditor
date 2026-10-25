import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { getRuns, health, startRun } from './api'
import { pages } from './pages'
import { Shell } from './shell/Shell'
import { navigate, useRoute } from './shell/router'
import { store, useTheme } from './shell/theme'
import type { CaseFilter, RunSummary } from './types'
import { UsageBadge } from './UsageBadge'

const LEGACY: Record<string, string> = { gate: 'live', claim: 'dashboard' }

export default function App() {
  const route = useRoute()
  const [theme, setTheme] = useTheme()
  const [api, setApi] = useState<'checking' | 'online' | 'offline'>('checking')
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [runId, setRunId] = useState<string | null>(store.get('ghost.run'))
  const [filter, setFilter] = useState<CaseFilter>({})
  const [msg, setMsg] = useState('')
  const [starting, setStarting] = useState(false)
  const [tick, setTick] = useState(0)
  const pending = useRef<string | null>(null)

  const page = pages.find((p) => p.path === route.path) ?? pages[0]
  const caseId = page.path === 'cases' ? route.param : null
  const setCaseId = useCallback((id: string | null) => { pending.current = id; navigate('cases', id) }, [])
  const go = useCallback((path: string) => {
    const p = LEGACY[path] ?? path
    if (p === 'cases' && pending.current) navigate('cases', pending.current)
    else navigate(p)
    pending.current = null
  }, [])

  const refresh = useCallback(async () => {
    try {
      const r = await getRuns()
      setRuns(r)
      // default: keep the remembered run; otherwise the newest run of the largest size (gate checks create newer 32-case
      // sample runs, and the console should open on the full audit, not a sample)
      const biggest = Math.max(0, ...r.map((x) => x.cases))
      setRunId((cur) => (cur && r.some((x) => x.run_id === cur) ? cur : r.find((x) => x.cases === biggest)?.run_id ?? r[0]?.run_id ?? null))
    } catch (e) { setMsg(String(e)) }
  }, [])
  useEffect(() => { health().then((ok) => { setApi(ok ? 'online' : 'offline'); refresh() }) }, [refresh])
  useEffect(() => { if (runId) store.set('ghost.run', runId) }, [runId])

  const startAudit = useCallback(async () => {
    setStarting(true); setMsg('')
    try {
      const { run_id } = await startRun({ dataset: 'full', strict_temporal: false })
      await refresh(); setRunId(run_id); setTick((t) => t + 1); go('live')
    } catch (e) { setMsg(String(e).includes('409') ? 'A run is already active.' : String(e)) }
    finally { setStarting(false) }
  }, [refresh, go])

  const Page = page.component
  return (
    <Shell
      pages={pages} active={page.path} runs={runs} runId={runId} setRunId={(id) => { setRunId(id); if (caseId) setCaseId(null) }}
      api={api} theme={theme} setTheme={setTheme} startAudit={startAudit} starting={starting} msg={msg}
    >
      <Page runId={runId} caseId={caseId} setCaseId={setCaseId} filter={filter} setFilter={setFilter} go={go} runs={runs} startAudit={startAudit} starting={starting} />
      <UsageBadge runId={runId} tick={tick} />
    </Shell>
  )
}
