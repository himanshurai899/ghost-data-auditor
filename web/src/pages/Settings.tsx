// Page for #/settings: NVIDIA configurator. Keys live encrypted on the server and are referenced only by UUID; this page can never read one back.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Card, EmptyState, Icon, PageHeader, Skeleton } from '../ui'
import type { ScreenProps } from '../types'
import * as S from '../settingsApi'
import { KeysCard } from './settings/KeysCard'
import { RolesCard } from './settings/RolesCard'
import { ModelsCard } from './settings/ModelsCard'
import './settings.css'

const KIND: Record<string, string> = { dpapi: 'Encrypted with Windows DPAPI', fernet: 'Encrypted with Fernet' }

export default function Settings(_: ScreenProps) {
  const [data, setData] = useState<S.SettingsData | null>(null)
  const [err, setErr] = useState<S.ApiError | null>(null)
  const [demo, setDemo] = useState(false)
  const [toast, setToast] = useState<{ text: string; ref?: string } | null>(null)
  const [cat, setCat] = useState<S.Catalog | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const load = useCallback(async () => {
    setErr(null)
    try { setData(await S.getSettings()); setDemo(false) } catch (e) {
      if (e instanceof S.ApiError && e.status === 0) { setData(S.DEMO); setDemo(true) } else setErr(e as S.ApiError)
    }
  }, [])
  useEffect(() => { void load() }, [load])
  const loaded = !!data
  useEffect(() => { if (!demo && loaded) S.getCatalog().then(setCat, () => setCat({ models: [], note: 'catalog unavailable' })) }, [demo, loaded])
  useEffect(() => () => clearTimeout(timer.current), [])

  const say = (text: string, ref?: string) => { setToast({ text, ref }); clearTimeout(timer.current); timer.current = setTimeout(() => setToast(null), 8000) }

  const storage = data?.storage ?? data?.keys[0]?.storage
  const banner = !data ? null : !data.vault_available
    ? { tone: 'warn', head: 'Unavailable: use .env', text: 'No encryption backend on this machine. Saving keys is disabled; put NVIDIA_API_KEY in your .env file.' }
    : { tone: 'ok', head: storage ? KIND[storage] ?? `Encrypted (${storage})` : 'Encrypted vault available', text: 'Keys are stored encrypted on the server and shown only as a reference.' }

  return (
    <div className="stack settings">
      <PageHeader title="Settings" subtitle="NVIDIA API keys, which key each role uses, and which model each role calls." />

      {demo && <p className="set-note tone-warn" role="status"><Icon name="warn" size={18} /> <span><strong>Demo data, read-only.</strong> The console API is not reachable, so this page shows fake, non-secret values and every control is disabled.</span></p>}

      {err && <Card><EmptyState icon="warn" title="Could not load settings" text={S.plain(err)} action={<Button onClick={() => void load()}>Retry</Button>} /></Card>}
      {!data && !err && <Card><div className="stack"><Skeleton h={22} w="40%" /><Skeleton h={60} /><Skeleton h={60} /></div></Card>}

      {data && banner && (
        <section className={`set-banner tone-${banner.tone}`} aria-label="Key vault status">
          <Icon name="lock" size={22} />
          <div>
            <p><strong>{banner.head}.</strong> <span className="muted">{banner.text}</span></p>
            <p className="muted set-limit">Protects the key from other users and from copied files; not from other programs running as you.</p>
            <p className="muted set-limit">A key can never be read back after saving. To change one, delete it and add a new one.</p>
          </div>
        </section>
      )}

      {data && (
        <>
          <Precedence env={data.env_keys} />
          <KeysCard data={data} readOnly={demo} reload={load} say={say} />
          <RolesCard data={data} readOnly={demo} setData={setData} />
          <ModelsCard data={data} cat={cat} readOnly={demo} setData={setData} />
        </>
      )}

      <div className="set-toast" role="status" aria-live="polite">
        {toast && (
          <span><Icon name="check" size={16} /> {toast.text}{toast.ref && <> <code title={toast.ref}>{toast.ref.slice(0, 8)}…</code>
            <button type="button" className="set-link" onClick={() => void navigator.clipboard?.writeText(toast.ref!).then(() => say('Reference copied.'), () => {})}>Copy reference</button></>}
            <button type="button" className="set-link" onClick={() => setToast(null)}>Dismiss</button></span>
        )}
      </div>
    </div>
  )
}

function Precedence({ env }: { env: Record<string, boolean> }) {
  const set = Object.keys(env).filter((r) => env[r]).map((r) => r.toLowerCase())
  return (
    <Card as="section" title="Which key wins">
      <ol className="set-prec">
        <li><strong>1. Environment / .env</strong> <span className="muted">NVIDIA_API_KEY_&lt;ROLE&gt;, then NVIDIA_API_KEY</span></li>
        <li><strong>2. Vault key active for the role</strong></li>
        <li><strong>3. Vault key active for default</strong></li>
      </ol>
      <p className="muted">{set.length ? <>Using key from .env for: <strong>{set.join(', ')}</strong>. Those roles ignore vault keys.</> : 'No key found in the environment, so vault keys are used.'}</p>
    </Card>
  )
}
