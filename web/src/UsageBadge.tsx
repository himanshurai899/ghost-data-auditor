import { useEffect, useState } from 'react'
import { getUsage } from './api'
import type { Usage } from './types'

export function UsageBadge({ runId, tick }: { runId: string | null; tick: number }) {
  const [u, setU] = useState<Usage | null>(null)
  useEffect(() => {
    setU(null)
    if (runId) getUsage(runId).then(setU).catch(() => {})
  }, [runId, tick])
  if (!u) return <footer className="badge" aria-label="Cost and determinism"><span className="muted">usage n/a</span></footer>
  return (
    <footer className="badge" aria-label="Cost and determinism">
      <span>{u.calls} LLM calls</span>
      <span>{u.cached} cached</span>
      <span>{u.tokens.toLocaleString()} tokens</span>
      <span className="ok">billed $0</span>
      <code title="output.csv sha256 prefix">sha256 {(u.output_sha256 ?? 'pending').slice(0, 12)}</code>
      {u.deterministic === true && <span className="ok" title="Rerun produced an identical output hash">&#10003; deterministic</span>}
      {u.deterministic === false && <span className="bad">not deterministic</span>}
    </footer>
  )
}
