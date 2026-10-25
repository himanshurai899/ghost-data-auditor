/*
 * Tooltip: accessible, portal-free, collision-aware card that explains its trigger.
 * Props:
 *   content: ReactNode        the card body (also put the same facts in the page or a legend table: tooltips are never the only way)
 *   children: ReactElement    ONE focusable trigger (button, a, ...). It receives aria-describedby; wrapper handles events.
 *   placement?: 'top' | 'bottom'   preferred side (flips when it would overflow; default 'top')
 *   maxWidth?: number         px (default 360)
 * Behaviour: opens on hover and keyboard focus; click/tap pins it open (click again unpins); closes on Escape, outside
 * click and when focus leaves. Positioned with position:fixed so scroll containers never clip it; clamped to the viewport.
 */
import { cloneElement, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactElement, ReactNode } from 'react'
import './ui.css'

interface Pos { top: number; left: number; side: 'top' | 'bottom'; arrow: number }
const GAP = 10
const MARGIN = 8

export function Tooltip({ content, children, placement = 'top', maxWidth = 360 }: {
  content: ReactNode
  children: ReactElement<Record<string, unknown>>
  placement?: 'top' | 'bottom'
  maxWidth?: number
}) {
  const id = useId()
  const wrap = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [pos, setPos] = useState<Pos | null>(null)

  const place = useCallback(() => {
    const w = wrap.current, t = tip.current
    if (!w || !t) return
    const r = w.getBoundingClientRect()
    const tw = t.offsetWidth, th = t.offsetHeight
    const vw = document.documentElement.clientWidth
    let side: 'top' | 'bottom' = placement
    const fitsTop = r.top - th - GAP >= MARGIN
    const fitsBottom = r.bottom + th + GAP <= window.innerHeight - MARGIN
    if (side === 'top' && !fitsTop && fitsBottom) side = 'bottom'
    else if (side === 'bottom' && !fitsBottom && fitsTop) side = 'top'
    const cx = r.left + r.width / 2
    const left = Math.max(MARGIN, Math.min(cx - tw / 2, vw - tw - MARGIN))
    const top = side === 'top' ? r.top - th - GAP : r.bottom + GAP
    setPos({ top, left, side, arrow: Math.max(12, Math.min(cx - left, tw - 12)) })
  }, [placement])

  useLayoutEffect(() => {
    if (!open) { setPos(null); return }
    place()
    const on = () => place()
    window.addEventListener('resize', on)
    window.addEventListener('scroll', on, true)
    return () => { window.removeEventListener('resize', on); window.removeEventListener('scroll', on, true) }
  }, [open, place, content])

  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); setPinned(false) } }
    const down = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) { setOpen(false); setPinned(false) }
    }
    document.addEventListener('keydown', key)
    document.addEventListener('pointerdown', down)
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('pointerdown', down) }
  }, [open])
  useEffect(() => () => clearTimeout(timer.current), [])

  const show = () => { clearTimeout(timer.current); setOpen(true) }
  const hide = () => { clearTimeout(timer.current); timer.current = setTimeout(() => { if (!pinned) setOpen(false) }, 120) }

  return (
    <span
      ref={wrap} className="ui-tt-wrap"
      onMouseEnter={show} onMouseLeave={hide} onFocus={show}
      onBlur={(e) => { if (!wrap.current?.contains(e.relatedTarget as Node | null) && !pinned) setOpen(false) }}
      onClick={() => { setPinned(!pinned); setOpen(!pinned) }}
    >
      {cloneElement(children, { 'aria-describedby': open ? id : undefined })}
      {open && (
        <span
          ref={tip} id={id} role="tooltip" className={`ui-tt ${pos ? `is-${pos.side}` : ''}`}
          style={{ top: pos?.top ?? 0, left: pos?.left ?? 0, maxWidth: `min(${maxWidth}px, calc(100vw - ${MARGIN * 2}px))`, visibility: pos ? 'visible' : 'hidden', ['--arrow-x' as string]: `${pos?.arrow ?? 12}px` }}
          onClick={(e) => e.stopPropagation()}
        >
          {content}
        </span>
      )}
    </span>
  )
}
