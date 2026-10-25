import { useEffect, useRef, useState } from 'react'
import { ApiError, ask } from './client.ts'
import type { AskResponse } from './client.ts'
import { DemoBadge } from './Timeline.tsx'
import './screens.css'

const MAX = 500
const SUGGESTIONS = [
  'Which cases were reported COMPLETE but are still INCOMPLETE?',
  'Which cases have an active restore risk?',
  'Why was a case marked NOT_APPLICABLE?',
  'Which gates failed in this run?',
]

type Turn = { q: string; a?: AskResponse; err?: string; pending?: boolean }

const errText = (e: unknown) => {
  if (e instanceof ApiError) {
    if (e.status === 429) return 'Rate limited: too many questions. Wait a moment and try again.'
    if (e.status === 409) return 'The run is still active or busy (409). Try again when it finishes.'
    if (e.status === 400) return `The question was rejected (400): ${e.message}`
    return `Request failed (${e.status}): ${e.message}`
  }
  return 'Could not reach the auditor.'
}

export default function Ask({ runId }: { runId: string }) {
  const [q, setQ] = useState('')
  const [log, setLog] = useState<Turn[]>([])
  const busy = log.some((t) => t.pending)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }) }, [log])

  async function send(text: string) {
    const question = text.trim()
    if (!question || question.length > MAX || busy) return
    setQ('')
    setLog((l) => [...l, { q: question, pending: true }])
    let turn: Turn
    try { turn = { q: question, a: await ask(runId, question) } } catch (e) { turn = { q: question, err: errText(e) } }
    setLog((l) => [...l.slice(0, -1), turn])
  }

  return (
    <section className="screen" aria-label="Ask the auditor">
      <div className="s-row"><h3>Ask the auditor</h3><DemoBadge /><span className="s-muted">Answers are grounded in run <code>{runId}</code>.</span></div>
      <div className="s-row" role="group" aria-label="Suggested questions">
        {SUGGESTIONS.map((s) => <button key={s} type="button" disabled={busy} onClick={() => send(s)}>{s}</button>)}
      </div>
      <div className="s-card ask-log" role="log" aria-live="polite" aria-label="Conversation">
        {log.length === 0 && <span className="s-muted">No questions yet. Pick a suggestion or type your own.</span>}
        {log.map((t, i) => (
          <div key={i} style={{ display: 'grid', gap: 8 }}>
            <div className="ask-q">{t.q}</div>
            {t.pending && <div className="ask-a" role="status">Thinking<span className="ask-dots" /></div>}
            {t.err && <div className="ask-a err" role="alert">{t.err}</div>}
            {t.a?.refused && (
              <div className="ask-a refused" role="note">
                <b>Refused.</b> {t.a.reason ?? 'The auditor declined this question.'}
              </div>
            )}
            {t.a && !t.a.refused && (
              <div className="ask-a">
                {t.a.answer}
                {t.a.citations.length > 0 && (
                  <div className="ask-cites" aria-label="Citations">
                    {t.a.citations.map((c, j) => (
                      <span key={j} className="chip blue">
                        {c.case_id && <b>{c.case_id}</b>}{c.evidence_id && <code>{c.evidence_id}</code>} {c.summary}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void send(q) }} style={{ display: 'grid', gap: 6 }}>
        <label htmlFor="ask-q" className="s-muted">Your question</label>
        <textarea id="ask-q" rows={3} value={q} maxLength={MAX} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Which cases came back after deletion?" />
        <div className="s-row" style={{ justifyContent: 'space-between' }}>
          <span className={q.length > MAX - 50 ? 'chip amber' : 's-muted'} aria-live="polite">{q.length}/{MAX}</span>
          <button className="primary" type="submit" disabled={busy || !q.trim()}>{busy ? 'Asking…' : 'Send'}</button>
        </div>
      </form>
    </section>
  )
}
