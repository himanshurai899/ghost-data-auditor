// Section (c): model id per role, with catalog suggestions. Validated client-side; saved per row.
import { useState } from 'react'
import { Button, Card, Field } from '../../ui'
import * as S from '../../settingsApi'

const USE: Record<string, string> = {
  fast: 'Intent fallback and ask.', reason: 'Ask answers.', vision: 'Unused fallback.', guard: 'Topic check.',
  embed: 'Intent neighbours and the ask index.', embed_large: 'Optional ask index.', rerank: 'Ask reranking.', parse: 'Screenshot and PDF page reading.',
}

export function ModelsCard({ data, cat, readOnly, setData }: { data: S.SettingsData; cat: S.Catalog | null; readOnly: boolean; setData: (d: S.SettingsData) => void }) {
  // `defaults` = the model ids the server reported when this page loaded (env/override-resolved); "reset" restores that value.
  const [defaults] = useState(data.models)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [err, setErr] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [live, setLive] = useState('')

  const save = async (role: string) => {
    const v = (draft[role] ?? data.models[role] ?? '').trim()
    if (!S.MODEL_RX.test(v)) { setErr((e) => ({ ...e, [role]: 'Use 3 to 80 characters: letters, digits, dot, slash, dash, underscore.' })); return }
    setErr((e) => ({ ...e, [role]: '' })); setBusy(role)
    try {
      await S.setModel(role, v)
      setData({ ...data, models: { ...data.models, [role]: v } })
      setDraft((d) => { const n = { ...d }; delete n[role]; return n })
      setLive(`${role} model saved.`)
    } catch (e) { setErr((x) => ({ ...x, [role]: S.plain(e) })) } finally { setBusy(null) }
  }

  return (
    <Card as="section" title="Models">
      <p className="muted">Which NVIDIA model each role calls. Start typing to see suggestions from the public catalog.</p>
      {cat && cat.models.length === 0 && <p className="muted set-note"><span>Model suggestions are unavailable ({cat.note || 'empty catalog'}). You can still type any model id.</span></p>}
      <datalist id="set-catalog">{cat?.models.map((m) => <option key={m.id} value={m.id}>{m.owned_by}</option>)}</datalist>
      <ul className="set-list">
        {S.MODEL_ROLES.map((role) => {
          const cur = data.models[role] ?? ''
          const val = draft[role] ?? cur
          const dirty = val !== cur
          return (
            <li key={role} className="set-item">
              <div className="set-item-main">
                <Field label={`Model for ${role}`} hint={`${USE[role]} Default: ${defaults[role] ?? 'unknown'}`} error={err[role]}>
                  {(a) => <input {...a} list="set-catalog" value={val} disabled={readOnly} autoComplete="off" spellCheck={false} maxLength={80}
                    onChange={(e) => setDraft((d) => ({ ...d, [role]: e.target.value }))} />}
                </Field>
              </div>
              <div className="row">
                <Button variant="primary" loading={busy === role} disabled={readOnly || !dirty || (busy !== null && busy !== role)} onClick={() => void save(role)} aria-label={`Save model for ${role}`}>Save</Button>
                <Button variant="ghost" disabled={readOnly || busy !== null || val === defaults[role]} onClick={() => setDraft((d) => ({ ...d, [role]: defaults[role] ?? '' }))} aria-label={`Reset ${role} model to default`}>Reset to default</Button>
              </div>
            </li>
          )
        })}
      </ul>
      <p className="sr" role="status" aria-live="polite">{live}</p>
    </Card>
  )
}
