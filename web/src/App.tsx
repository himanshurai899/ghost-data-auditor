import { useEffect, useState } from 'react'
import './App.css'

// Screens planned in docs/delivery_plan.md §5 (P3-02 … P3-08).
const SCREENS = [
  ['Live gate board', 'P3-02'],
  ['Claim vs truth', 'P3-03'],
  ['Resurrection timeline', 'P3-04'],
  ['Identity graph', 'P3-05'],
  ['Ask the auditor', 'P3-06'],
  ['Red-team panel', 'P3-07'],
  ['Cost & determinism', 'P3-08'],
] as const

export default function App() {
  const [api, setApi] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => setApi(r.ok ? 'online' : 'offline'))
      .catch(() => setApi('offline'))
  }, [])

  return (
    <main className="console">
      <header>
        <h1>Ghost Audit Console</h1>
        <p>Deletion requests audited against evidence, not claims.</p>
        <span className={`api api-${api}`}>API {api}</span>
      </header>
      <ul className="screens">
        {SCREENS.map(([name, issue]) => (
          <li key={issue}>
            <strong>{name}</strong>
            <small>{issue}</small>
          </li>
        ))}
      </ul>
    </main>
  )
}
