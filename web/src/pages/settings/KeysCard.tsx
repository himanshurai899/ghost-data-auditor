// Section (a): stored keys, add-key form, delete confirm. The typed secret lives only in the password input's own state and is cleared right after save.
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Button, Card, EmptyState, Field, Icon, StatusBadge } from '../../ui'
import * as S from '../../settingsApi'

export const ROLE_HELP: Record<string, string> = {
  default: 'Fallback for any role without its own key',
  embed: 'Search index and intent neighbours',
  embed_large: 'Optional larger ask index',
  rerank: 'Ranks ask results',
  parse: 'Reads screenshots and PDF pages',
  chat: 'Chat models: intent fallback, ask answers, topic check',
}
/** The test endpoint takes model roles; "default" and "chat" are exercised through the fast chat model. */
export const testRole = (r: string) => (r === 'default' || r === 'chat' ? 'fast' : r)
const when = (iso?: string) => { const d = iso ? new Date(iso) : null; return d && !isNaN(+d) ? d.toLocaleString() : 'unknown' }

export function KeysCard({ data, readOnly, reload, say }: { data: S.SettingsData; readOnly: boolean; reload: () => Promise<void>; say: (t: string, ref?: string) => void }) {
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState('')
  const [confirm, setConfirm] = useState<S.KeyEntry | null>(null)

  const test = async (k: S.KeyEntry) => {
    setBusy(k.ref); setMsg('')
    try {
      const r = await S.testKey(k.ref, testRole(k.roles[0] ?? 'default'))
      setMsg(`${k.label}: ${r.ok ? 'connection ok' : 'connection failed'}, ${r.message}, ${r.latency_ms} ms.`)
      await reload()
    } catch (e) { setMsg(`${k.label}: ${S.plain(e)}`) } finally { setBusy(null) }
  }
  const del = async (k: S.KeyEntry) => {
    setBusy(k.ref)
    try { await S.deleteKey(k.ref); setConfirm(null); say(`Deleted key "${k.label}".`); await reload() } catch (e) { setMsg(S.plain(e)); setConfirm(null) } finally { setBusy(null) }
  }

  return (
    <Card as="section" title="Keys" actions={<Button variant="primary" icon="key" disabled={readOnly || !data.vault_available || adding} onClick={() => setAdding(true)}>Add key</Button>}>
      <p className="muted">Each key is stored encrypted on the server. This page only ever sees a reference and a preview.</p>
      {!data.vault_available && <p className="set-note tone-warn"><Icon name="warn" size={18} /> <span>Saving is disabled because no encryption backend is available. Put the key in .env as <code>NVIDIA_API_KEY</code>.</span></p>}
      {adding && <AddKey readOnly={readOnly} onDone={async (ref) => { setAdding(false); say('Key saved. Its reference is', ref); await reload() }} onCancel={() => setAdding(false)} />}

      {data.keys.length === 0 && !adding ? (
        <EmptyState icon="key" title="No keys stored yet" text="Add your NVIDIA API key to use it from this console, or set NVIDIA_API_KEY in .env."
          action={<Button variant="primary" disabled={readOnly || !data.vault_available} onClick={() => setAdding(true)}>Add your first key</Button>} />
      ) : (
        <ul className="set-list">
          {data.keys.map((k) => (
            <li key={k.ref} className="set-item">
              <div className="set-item-main">
                <strong>{k.label}</strong> <code className="set-prev">{k.preview}</code> <span className="set-chip"><Icon name="lock" size={12} /> {k.storage === 'dpapi' ? 'DPAPI' : k.storage === 'fernet' ? 'Fernet' : k.storage}</span>
                <dl className="set-dl">
                  <div><dt>Roles</dt><dd>{k.roles.join(', ') || 'none'}</dd></div>
                  <div><dt>Created</dt><dd>{when(k.created)}</dd></div>
                  <div><dt>Last test</dt><dd>{k.last_test
                    ? <><StatusBadge status={k.last_test.ok ? 'PASS' : 'FAIL'} label={k.last_test.ok ? 'ok' : 'failed'} /> {k.last_test.latency_ms} ms, {when(k.last_test.at)}</>
                    : <span className="muted">never tested</span>}</dd></div>
                </dl>
              </div>
              <div className="row">
                <Button loading={busy === k.ref} disabled={readOnly || (busy !== null && busy !== k.ref)} onClick={() => void test(k)} aria-label={`Test key ${k.label}`}>Test</Button>
                <Button variant="ghost" icon="x" disabled={readOnly || busy !== null} onClick={() => setConfirm(k)} aria-label={`Delete key ${k.label}`}>Delete</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="sr" role="status" aria-live="polite">{msg}</p>
      {msg && <p className="muted" aria-hidden="true">{msg}</p>}
      {confirm && <Confirm k={confirm} busy={busy === confirm.ref} onYes={() => void del(confirm)} onNo={() => setConfirm(null)} />}
    </Card>
  )
}

/** Native modal <dialog>: browser-provided focus trap, Escape to cancel, focus returns to the opener. */
function Confirm({ k, busy, onYes, onNo }: { k: S.KeyEntry; busy: boolean; onYes: () => void; onNo: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal() }, [])
  return (
    <dialog ref={ref} className="set-dialog" aria-labelledby="del-h" onCancel={(e) => { e.preventDefault(); onNo() }}>
      <h3 id="del-h">Delete key "{k.label}"?</h3>
      <p className="muted">The stored ciphertext is overwritten and cannot be recovered. Roles using this key fall back to .env.</p>
      <div className="row">
        <Button autoFocus onClick={onNo}>Cancel</Button>
        <Button variant="primary" loading={busy} onClick={onYes}>Delete key</Button>
      </div>
    </dialog>
  )
}

function AddKey({ readOnly, onDone, onCancel }: { readOnly: boolean; onDone: (ref: string) => Promise<void>; onCancel: () => void }) {
  const [label, setLabel] = useState('')
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const [roles, setRoles] = useState<string[]>(['default'])
  const [touched, setTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [srvErr, setSrvErr] = useState('')

  const labelErr = label.trim().length < 1 || label.length > 40 ? 'Enter a label of 1 to 40 characters.' : ''
  const keyErr = !value ? 'Paste your NVIDIA API key.' : !S.KEY_RX.test(value) ? 'A key looks like nvapi- followed by at least 20 letters, digits, "-" or "_".' : ''
  const roleErr = roles.length ? '' : 'Choose at least one role.'

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setTouched(true); setSrvErr('')
    if (labelErr || keyErr || roleErr || readOnly) return
    setSaving(true)
    try {
      const { ref } = await S.addKey(label.trim(), value, roles)
      setValue(''); setShow(false) // secret leaves React state immediately
      await onDone(ref)
    } catch (err) { setSrvErr(S.plain(err)); setSaving(false) }
  }
  const toggle = (r: string) => setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]))

  return (
    <form className="set-form" onSubmit={(e) => void submit(e)} noValidate aria-label="Add key">
      <Field label="Label" hint="A name only you see, for example Work laptop." error={touched ? labelErr : ''}>
        {(a) => <input {...a} value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} autoComplete="off" />}
      </Field>
      <Field label="API key" hint="Sent once to the server over this local connection, then encrypted. It is never shown again." error={touched ? keyErr : ''}>
        {(a) => (
          <div className="set-keyrow">
            <input {...a} type={show ? 'text' : 'password'} value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" spellCheck={false} placeholder="nvapi-…" maxLength={200} />
            <Button variant="ghost" icon="eye" aria-pressed={show} onClick={() => setShow((s) => !s)}>{show ? 'Hide' : 'Show'}<span className="sr"> what I typed</span></Button>
          </div>
        )}
      </Field>
      <fieldset className="set-roles" aria-describedby="roles-err">
        <legend>Roles this key can serve</legend>
        {S.ROLES.map((r) => (
          <label key={r} className="set-check"><input type="checkbox" checked={roles.includes(r)} onChange={() => toggle(r)} /><span><strong>{r}</strong> <span className="muted">{ROLE_HELP[r]}</span></span></label>
        ))}
        <p id="roles-err" className="ui-field-err" role="alert">{touched ? roleErr : ''}</p>
      </fieldset>
      {srvErr && <p className="ui-field-err" role="alert">{srvErr}</p>}
      <div className="row">
        <Button type="submit" variant="primary" loading={saving} disabled={readOnly}>Save key</Button>
        <Button variant="ghost" onClick={() => { setValue(''); onCancel() }} disabled={saving}>Cancel</Button>
      </div>
    </form>
  )
}
