/*
 * Icon: hand-written inline SVG set (24x24 viewBox, stroke icons, currentColor).
 * Props: name: IconName; size?: number (px, default 20); title?: string (adds an accessible name; otherwise aria-hidden).
 */
export type IconName =
  | 'pipeline' | 'shield' | 'gate' | 'search' | 'user' | 'database' | 'file' | 'clock' | 'flow' | 'restore' | 'key' | 'cog'
  | 'chart' | 'check' | 'warn' | 'x' | 'info' | 'play' | 'sun' | 'moon' | 'menu' | 'link' | 'eye' | 'lock'

const P: Record<IconName, string> = {
  pipeline: 'M3 6h5v5H3zM16 13h5v5h-5zM8 8.5h4a2 2 0 0 1 2 2v2.5a2 2 0 0 0 2 2',
  shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z',
  gate: 'M4 20V6m16 14V6M4 6h16M8 6v14m4-14v14m4-14v14',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16l-4.2-4.2',
  user: 'M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 20c0-3.5 3.6-6 8-6s8 2.5 8 6',
  database: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6m-16 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6',
  file: 'M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 5v4.5l3 2',
  flow: 'M4 7h10m0 0l-3-3m3 3l-3 3M20 17H10m0 0l3-3m-3 3l3 3',
  restore: 'M4 12a8 8 0 1 0 2.5-5.8M4 4v4h4M12 8v4l3 2',
  key: 'M8 14a4 4 0 1 1 3.9-5H21v3h-2v2h-3v-2h-4.1A4 4 0 0 1 8 14z',
  cog: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12l2-1.2-2-3.4-2.3.7a7 7 0 0 0-1.7-1L14.5 4h-4L10 7.1a7 7 0 0 0-1.7 1L6 7.4 4 10.800 6 12l-2 1.200 2 3.400 2.300-.7a7 7 0 0 0 1.700 1l.5 3.100h4l.5-3.100a7 7 0 0 0 1.700-1l2.300.7 2-3.400z',
  chart: 'M4 20V4m0 16h16M8 16v-5m4 5V8m4 8v-3',
  check: 'M5 12.500l4.500 4.500L19 7.500',
  warn: 'M12 4l9 16H3zM12 10v4m0 3v.01',
  x: 'M6 6l12 12M18 6L6 18',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 8v5m0-8.500v.01',
  play: 'M7 4.500v15l12-7.500z',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2m0 16v2M2 12h2m16 0h2M4.900 4.900l1.400 1.400m11.400 11.400l1.400 1.400M4.900 19.100l1.400-1.400M17.700 6.300l1.400-1.400',
  moon: 'M20 14.500A8 8 0 0 1 9.500 4 8 8 0 1 0 20 14.500z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  link: 'M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1',
  eye: 'M2 12s3.600-7 10-7 10 7 10 7-3.600 7-10 7S2 12 2 12zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  lock: 'M6 11h12v9H6zM8.500 11V8a3.500 3.500 0 0 1 7 0v3M12 15v2',
}

export function Icon({ name, size = 20, title }: { name: IconName; size?: number; title?: string }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" role={title ? 'img' : undefined} aria-hidden={title ? undefined : true}
      aria-label={title} focusable="false" style={{ flex: 'none' }}
    >
      <path d={P[name]} />
    </svg>
  )
}
