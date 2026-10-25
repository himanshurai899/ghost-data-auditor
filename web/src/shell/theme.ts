// Theme preference: 'light' | 'dark' | 'system'. Persisted in localStorage (guarded); applied as <html data-theme>.
import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark' | 'system'
const KEY = 'ghost.theme'

export const store = {
  get: (k: string) => { try { return localStorage.getItem(k) } catch { return null } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* storage blocked */ } },
}

const read = (): Theme => { const v = store.get(KEY); return v === 'light' || v === 'dark' ? v : 'system' }
const apply = (t: Theme) => {
  if (t === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', t)
}
apply(read()) // before first paint

export function useTheme(): [Theme, (t: Theme) => void] {
  const [t, setT] = useState<Theme>(read)
  useEffect(() => { apply(t); if (t === 'system') { try { localStorage.removeItem(KEY) } catch { /* ignore */ } } else store.set(KEY, t) }, [t])
  return [t, setT]
}
