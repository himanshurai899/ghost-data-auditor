// Section (b): which stored key each role uses (optimistic PUT /active with rollback) and a per-role connection test.
import { useState } from 'react'
import { Button, Card, Field, StatusBadge } from '../../ui'
import * as S from '../../settingsApi'
import { ROLE_HELP, testRole } from './KeysCard'

type Props = { data: S.SettingsData; readOnly: boolean; setData: (d: S.SettingsData) => void }

export function RolesCard({ data, readOnly, setData }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const [res, setRes] = useState<Record<string, string>>({})
  const [live, setLive] = useState('')

  const choose = async (role: string, v: string) => {
    const prev = data.active
    const next = { ...prev }
    if (v) next[role] = v; else delete next[role]
    setData({ ...data, active: next }) // optimistic
    setBusy(role)
    try { await S.setActive(role, v || null); setLive(`${role} now uses ${v ? 'the selected stored key' : 'the environment key'}.`) } catch (e) {
      setData({ ...data, active: prev }); setLive(`Could not change ${role}: ${S.plain(e)}`) // rollback
    } finally { setBusy(null) }
  }
  const test = async (role: string) => {
    setBusy(role); setRes((r) => ({ ...r, [role]: 'Testing…' }))
    let text: string
    try {
      const r = await S.testKey(data.active[role] ?? null, testRole(role))
      text = `${r.ok ? 'OK' : 'Failed'}: status ${r.status ?? 'none'}, ${r.latency_ms} ms, model ${r.model}, ${r.message}`
    } catch (e) { text = `Failed: ${S.plain(e)}` } finally { setBusy(null) }
    setRes((r) => ({ ...r, [role]: text })); setLive(`${role}: ${text}`)
  }

  return (
    <Card as="section" title="Role assignment">
      <p className="muted">Pick which stored key each role uses. A key in .env always wins over these choices. "Testing" makes one tiny real call to NVIDIA.</p>
      <ul className="set-list">
        {S.ROLES.map((role) => {
          const envSet = !!data.env_keys[role.toUpperCase()]
          const r = res[role]
          return (
            <li key={role} className="set-item">
              <div className="set-item-main">
                <Field label={`Use key for ${role}`} hint={`${ROLE_HELP[role]}${envSet ? '. A .env key is set for this role and takes precedence.' : ''}`}>
                  {(a) => (
                    <select {...a} value={data.active[role] ?? ''} disabled={readOnly || busy !== null} onChange={(e) => void choose(role, e.target.value)}>
                      <option value="">Environment / .env (if set), otherwise none</option>
                      {data.keys.map((k) => <option key={k.ref} value={k.ref}>{k.label} ({k.preview})</option>)}
                    </select>
                  )}
                </Field>
                {r && <p className="set-result">{r.startsWith('OK') && <StatusBadge status="PASS" label="ok" />}{r.startsWith('Failed') && <StatusBadge status="FAIL" label="failed" />} {r}</p>}
              </div>
              <Button loading={busy === role && r === 'Testing…'} disabled={readOnly || busy !== null} onClick={() => void test(role)} aria-label={`Test connection for ${role}`}>Test connection</Button>
            </li>
          )
        })}
      </ul>
      <p className="sr" role="status" aria-live="polite">{live}</p>
    </Card>
  )
}
