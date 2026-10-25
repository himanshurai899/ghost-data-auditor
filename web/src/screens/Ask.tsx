// Ask the auditor: a conversation over one run's audit trail. All model text is rendered as plain text (never HTML).
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { getCases } from '../api'
import { href } from '../shell/router'
import { Button, Card, Field, Icon, Skeleton } from '../ui'
import { ApiError, ask } from './client.ts'
import type { AskResponse } from './client.ts'
import { DemoBadge } from './Timeline.tsx'
import './screens.css'
import '../live/live.css'

const MAX = 500
const BASE_SUGGESTIONS = [
  'Which cases were reported COMPLETE but are still INCOMPLETE?',
  'Which cases have an active restore risk?',
  'Which gates failed in this run?',
]
const CAN_ASK = ['which cases are INCOMPLETE and why', 'what remains in a given case (use its id)', 'which gates warned or failed', 'where restore risks or active data flows exist']

interface Turn {
  id: number; q: string; a?: AskResponse
  err?: { kind: 'rate' | 'down' | 'other'; text: string }
  pending?: boolean
}

function toErr(e: unknown): NonNullable<Turn['err']> {
  if (e instanceof ApiError) {
    if (e.status === 429) return { kind: 'rate', text: 'Too many questions in a short time. Wait a few seconds, then retry.' }
    if (e.status === 503) return { kind: 'down', text: 'The auditor is temporarily unavailable. Retry in a moment.' }
    if (e.status === 400) return { kind: 'other', text: `The question was rejected: ${e.message}` }
    return { kind: 'other', text: `Request failed (${e.status}): ${e.message}` }
  }
  return { kind: 'down', text: 'Could not reach the auditor. Check that the API is running, then retry.' }
}

export default function Ask({ runId }: { runId: string }) {
  const [q, setQ] = useState('')
  const [log, setLog] = useState<Turn[]>([])
  const [ids, setIds] = useState<string[]>([])
  const [copied, setCopied] = useState<number | null>(null)
  const nextId = useRef(1)
  const box = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const busy = log.some((t) => t.pending)

  // A real INCOMPLETE case id from this run makes the suggestions concrete.
  useEffect(() => {
    setLog([]); setIds([])
    let live = true
    getCases(runId, { status: 'INCOMPLETE' }).then((r) => { if (live) setIds(r.slice(0, 1).map((c) => c.case_id)) }).catch(() => {})
    return () => { live = false }
  }, [runId])

  useEffect(() => { const el = box.current; if (el && stick.current) el.scrollTop = el.scrollHeight }, [log])

  async function send(text: string, replace?: number) {
    const question = text.trim()
    if (!question || question.length > MAX || busy) return
    const id = replace ?? nextId.current++
    setQ('')
    stick.current = true
    setLog((l) => (replace ? l.map((t) => (t.id === id ? { id, q: question, pending: true } : t)) : [...l, { id, q: question, pending: true }]))
    let turn: Turn
    try { turn = { id, q: question, a: await ask(runId, question) } } catch (e) { turn = { id, q: question, err: toErr(e) } }
    setLog((l) => l.map((t) => (t.id === id ? turn : t)))
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(q) }
  }
  const copy = async (id: number, text: string) => {
    try { await navigator.clipboard.writeText(text); setCopied(id); setTimeout(() => setCopied(null), 1500) } catch { /* clipboard blocked: nothing to do */ }
  }
  const suggestions = ids[0]
    ? [`What remains in ${ids[0]} and what should be fixed first?`, ...BASE_SUGGESTIONS]
    : BASE_SUGGESTIONS

  return (
    <div className="as">
      <div className="as-main">
        <Card flush>
          <div className="as-head"><DemoBadge /><span>Answers are grounded in run <code>{runId}</code>.</span>
            <Button variant="ghost" disabled={log.length === 0 || busy} onClick={() => setLog([])}>Clear conversation</Button></div>
          <div className="as-thread" ref={box} role="log" aria-live="polite" aria-label="Conversation"
            onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60 }}>
            {log.length === 0 && (
              <div className="as-empty">
                <Icon name="search" size={28} />
                <p>Ask about this run in plain language. Try a suggestion below or type your own question.</p>
              </div>
            )}
            {log.map((t) => (
              <div className="as-turn" key={t.id}>
                <div className="as-q"><span className="sr">You asked: </span>{t.q}</div>
                {t.pending && (
                  <div className="as-a" role="status" aria-label="The auditor is thinking"><Skeleton h={12} w="80%" /><Skeleton h={12} w="55%" /><Skeleton h={12} w="68%" /></div>
                )}
                {t.err && (
                  <div className={`as-a is-err`} role="alert">
                    <Icon name="warn" size={18} /><div><p>{t.err.text}</p>
                      {t.err.kind !== 'other' && <Button variant="secondary" disabled={busy} onClick={() => { void send(t.q, t.id) }}>Retry</Button>}</div>
                  </div>
                )}
                {t.a?.refused && (
                  <div className="as-a is-refused" role="note">
                    <Icon name="lock" size={18} />
                    <div>
                      <p><b>Declined.</b> {t.a.reason ?? 'The auditor declined this question.'}</p>
                      <p className="as-sub">It only answers questions about this run's audit trail. You can ask: {CAN_ASK.join('; ')}.</p>
                    </div>
                  </div>
                )}
                {t.a && !t.a.refused && (
                  <div className="as-a">
                    <p className="as-text">{t.a.answer}</p>
                    {t.a.citations.length > 0 && (
                      <ul className="as-cites" aria-label="Citations">
                        {t.a.citations.map((c, j) => (
                          <li key={j}>
                            {c.case_id
                              ? <a className="as-cite" href={href('cases', c.case_id)} aria-label={`Open ${c.case_id}${c.evidence_id ? `, evidence ${c.evidence_id}` : ''}: ${c.summary}`}>
                                  <b>{c.case_id}</b>{c.evidence_id && <code>{c.evidence_id}</code>}<span>{c.summary}</span></a>
                              : <span className="as-cite is-static">{c.evidence_id && <code>{c.evidence_id}</code>}<span>{c.summary}</span></span>}
                          </li>
                        ))}
                      </ul>
                    )}
                    <Button variant="ghost" icon="file" onClick={() => { void copy(t.id, t.a?.answer ?? '') }}>{copied === t.id ? 'Copied' : 'Copy answer'}</Button>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="as-chips" role="group" aria-label="Suggested questions">
            {suggestions.map((s) => <button key={s} type="button" className="as-chip" disabled={busy} onClick={() => { void send(s) }}>{s}</button>)}
          </div>
          <form className="as-form" onSubmit={(e) => { e.preventDefault(); void send(q) }}>
            <Field label="Your question" hint="Enter sends, Shift+Enter adds a new line.">
              {(a) => <textarea {...a} rows={3} value={q} maxLength={MAX} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="e.g. Which cases came back after deletion?" />}
            </Field>
            <div className="as-send">
              <span className={`as-count ${q.length > MAX - 50 ? 'is-near' : ''}`}>{q.length}/{MAX}</span>
              <Button variant="primary" type="submit" loading={busy} disabled={!q.trim()}>{busy ? 'Asking' : 'Send'}</Button>
            </div>
          </form>
        </Card>
      </div>
      <aside className="as-side">
        <Card title="How answers are grounded">
          <ul className="as-notes">
            <li>Answers are retrieved from this run's audit trail only, not from general knowledge.</li>
            <li>Every claim cites the case and evidence id behind it. Select a citation to open the case.</li>
            <li>Instruction-override attempts and off-topic questions are refused, with a reason.</li>
            <li>Model text is shown as plain text and never changes any audit verdict.</li>
          </ul>
        </Card>
      </aside>
    </div>
  )
}
