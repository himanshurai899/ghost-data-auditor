// Minimal hash router: '#/cases/case_0012' -> { path: 'cases', param: 'case_0012' }; '#/' -> { path: '' }.
import { useEffect, useState } from 'react'

export interface Route { path: string; param: string | null }

export const parseHash = (h = window.location.hash): Route => {
  const [path = '', ...rest] = h.replace(/^#\/?/, '').split('/')
  const param = rest.join('/')
  let decoded: string | null = null
  try { decoded = param ? decodeURIComponent(param) : null } catch { decoded = null }
  return { path, param: decoded }
}

export const href = (path: string, param?: string | null) => `#/${path}${param ? `/${encodeURIComponent(param)}` : ''}`
export const navigate = (path: string, param?: string | null) => { window.location.hash = href(path, param) }

export function useRoute(): Route {
  const [r, setR] = useState<Route>(parseHash)
  useEffect(() => {
    const on = () => { setR(parseHash()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return r
}
