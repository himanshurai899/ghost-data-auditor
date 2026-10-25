/*
 * UI kit components. Every component is small, typed and token-styled (ui.css). Props:
 *
 * Card          { as?: 'div'|'section'|'article'; title?: ReactNode; actions?: ReactNode; flush?: boolean; tone?: Tone; className?; children }
 * StatCard      { label: string; value: ReactNode; sub?: ReactNode; delta?: {text: string; tone?: Tone}; icon?: IconName; tone?: Tone; loading?: boolean }
 * StatusBadge   { status: 'COMPLETE'|'INCOMPLETE'|'NOT_APPLICABLE'|'PASS'|'WARN'|'FAIL'; label?: string }   icon + text, never colour alone
 * EvidenceChip  { id: string; tier: 'A'|'B'|'C'|'D'|'X'; score?: number }   THE component for any evidence id
 * Skeleton      { w?: number|string; h?: number|string; className? }
 * EmptyState    { icon?: IconName; title: string; text?: ReactNode; action?: ReactNode }
 * PageHeader    { title: string; subtitle?: ReactNode; actions?: ReactNode }   renders the page <h1>
 * Legend        { items: {swatch: ReactNode|string(css colour var); label: string; description?: ReactNode}[]; label?: string }
 * Segmented     { options: {value: T; label: string}[]; value: T; onChange(v: T); label: string }   radio group
 * Tabs          { items: {id: string; label: string; icon?: IconName}[]; value: string; onChange(id); label: string }   tablist (arrow keys)
 * Button        { variant?: 'primary'|'secondary'|'ghost'; loading?: boolean; icon?: IconName; href?: string; ...button attrs }
 * Field         { label: string; hint?: string; error?: string; children: (a: {id; 'aria-describedby'; 'aria-invalid'}) => ReactNode }
 * Tone = 'neutral'|'primary'|'ok'|'warn'|'bad'
 * Touch targets are >= 44px; hover never shifts layout; transitions use colour/opacity/transform only.
 */
import { useId } from 'react'
import type { ButtonHTMLAttributes, KeyboardEvent, ReactNode } from 'react'
import { Icon } from './Icon'
import type { IconName } from './Icon'
import { Tooltip } from './Tooltip'
import './ui.css'

export type Tone = 'neutral' | 'primary' | 'ok' | 'warn' | 'bad'

export function Card({ as: Tag = 'div', title, actions, flush, tone = 'neutral', className = '', children }: {
  as?: 'div' | 'section' | 'article'; title?: ReactNode; actions?: ReactNode; flush?: boolean; tone?: Tone; className?: string; children?: ReactNode
}) {
  return (
    <Tag className={`ui-card tone-${tone} ${flush ? 'is-flush' : ''} ${className}`}>
      {(title || actions) && (
        <div className="ui-card-head">{title && <h2 className="ui-card-title">{title}</h2>}{actions && <div className="ui-card-actions">{actions}</div>}</div>
      )}
      {children}
    </Tag>
  )
}

export function Skeleton({ w = '100%', h = 16, className = '' }: { w?: number | string; h?: number | string; className?: string }) {
  return <span className={`ui-skel ${className}`} style={{ width: w, height: h }} aria-hidden="true" />
}

export function StatCard({ label, value, sub, delta, icon, tone = 'neutral', loading }: {
  label: string; value: ReactNode; sub?: ReactNode; delta?: { text: string; tone?: Tone }; icon?: IconName; tone?: Tone; loading?: boolean
}) {
  return (
    <div className={`ui-card ui-stat tone-${tone}`} aria-busy={loading || undefined}>
      <div className="ui-stat-top"><span className="ui-stat-label">{label}</span>{icon && <span className="ui-stat-icon"><Icon name={icon} size={18} /></span>}</div>
      {loading ? <Skeleton h={34} w="60%" /> : <div className="ui-stat-value">{value}</div>}
      {loading ? <Skeleton h={14} w="80%" /> : (sub || delta) && (
        <div className="ui-stat-sub">{delta && <span className={`ui-delta tone-${delta.tone ?? 'neutral'}`}>{delta.text}</span>}{sub}</div>
      )}
    </div>
  )
}

const STATUS: Record<string, { label: string; icon: IconName; cls: string }> = {
  COMPLETE: { label: 'Complete', icon: 'check', cls: 'ok' },
  INCOMPLETE: { label: 'Incomplete', icon: 'warn', cls: 'bad' },
  NOT_APPLICABLE: { label: 'Not applicable', icon: 'info', cls: 'neutral' },
  PASS: { label: 'Pass', icon: 'check', cls: 'ok' },
  WARN: { label: 'Warn', icon: 'warn', cls: 'warn' },
  FAIL: { label: 'Fail', icon: 'x', cls: 'bad' },
}
export function StatusBadge({ status, label }: { status: 'COMPLETE' | 'INCOMPLETE' | 'NOT_APPLICABLE' | 'PASS' | 'WARN' | 'FAIL' | (string & {}); label?: string }) {
  const s = STATUS[status] ?? { label: status, icon: 'info' as IconName, cls: 'neutral' }
  return <span className={`ui-badge tone-${s.cls}`}><Icon name={s.icon} size={14} />{label ?? s.label}</span>
}

export const TIERS = {
  A: { label: 'Direct', text: 'Citable file captured at or before audit_at that shows the resource in the cited state.' },
  B: { label: 'Inferred', text: 'Absence proven by omission from a citable table-level snapshot of the system.' },
  C: { label: 'Claim', text: 'A workflow or activity claim only. Never sufficient alone and never cited in output.' },
  D: { label: 'Late', text: 'Captured after audit_at. Used for discovery only, never for state or citation.' },
  X: { label: 'None', text: 'A future step (remediation or post-remediation verification): no evidence by design.' },
} as const
export type Tier = keyof typeof TIERS

export function EvidenceChip({ id, tier, score }: { id: string; tier: Tier; score?: number }) {
  const t = TIERS[tier]
  return (
    <Tooltip content={<><strong>Tier {tier}: {t.label}</strong><br />{t.text}{score !== undefined && <><br />Score {score} / 100 (tier base minus recency penalty).</>}</>}>
      <button type="button" className={`ui-ev ev-${tier.toLowerCase()}`}>
        <span className="ui-ev-tier" aria-hidden="true">{tier}</span>
        <span className="ui-ev-id">{id || 'planned'}</span>
        <span className="sr">tier {tier} {t.label}{score !== undefined ? `, score ${score}` : ''}</span>
        {score !== undefined && <span className="ui-ev-score" aria-hidden="true">{score}</span>}
      </button>
    </Tooltip>
  )
}

export function EmptyState({ icon = 'info', title, text, action }: { icon?: IconName; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="ui-empty">
      <span className="ui-empty-icon"><Icon name={icon} size={28} /></span>
      <h3>{title}</h3>
      {text && <p className="muted">{text}</p>}
      {action}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="ui-pagehead">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      {actions && <div className="row">{actions}</div>}
    </header>
  )
}

export function Legend({ items, label }: { items: { swatch: ReactNode; label: string; description?: ReactNode }[]; label?: string }) {
  return (
    <ul className="ui-legend" aria-label={label}>
      {items.map((i, n) => (
        <li key={n}>
          <span className="ui-swatch" aria-hidden="true">{i.swatch}</span>
          <span>{i.label && <strong>{i.label}</strong>}{i.description && <span className="muted"> {i.description}</span>}</span>
        </li>
      ))}
    </ul>
  )
}

function arrows(e: KeyboardEvent, i: number, n: number, pick: (j: number) => void) {
  const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
  if (!d) return
  e.preventDefault(); pick((i + d + n) % n)
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string
}) {
  return (
    <div className="ui-seg" role="radiogroup" aria-label={label}>
      {options.map((o, i) => (
        <button
          key={o.value} type="button" role="radio" aria-checked={o.value === value} tabIndex={o.value === value ? 0 : -1}
          className={o.value === value ? 'is-on' : ''} onClick={() => onChange(o.value)}
          onKeyDown={(e) => arrows(e, i, options.length, (j) => { onChange(options[j].value); (e.currentTarget.parentElement?.children[j] as HTMLElement | undefined)?.focus() })}
        >{o.label}</button>
      ))}
    </div>
  )
}

export function Tabs({ items, value, onChange, label }: {
  items: { id: string; label: string; icon?: IconName }[]; value: string; onChange: (id: string) => void; label: string
}) {
  return (
    <div className="ui-tabs" role="tablist" aria-label={label}>
      {items.map((t, i) => (
        <button
          key={t.id} type="button" role="tab" aria-selected={t.id === value} tabIndex={t.id === value ? 0 : -1}
          className={t.id === value ? 'is-on' : ''} onClick={() => onChange(t.id)}
          onKeyDown={(e) => arrows(e, i, items.length, (j) => { onChange(items[j].id); (e.currentTarget.parentElement?.children[j] as HTMLElement | undefined)?.focus() })}
        >{t.icon && <Icon name={t.icon} size={16} />}{t.label}</button>
      ))}
    </div>
  )
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost'; loading?: boolean; icon?: IconName; href?: string }
export function Button({ variant = 'secondary', loading, icon, href, children, className = '', disabled, ...rest }: BtnProps) {
  const cls = `ui-btn is-${variant} ${className}`
  const inner = <>{loading ? <span className="ui-spin" aria-hidden="true" /> : icon && <Icon name={icon} size={18} />}{children}</>
  if (href) return <a className={cls} href={href}>{inner}</a>
  return <button type="button" className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>{inner}</button>
}

export function Field({ label, hint, error, children }: {
  label: string; hint?: string; error?: string
  children: (a: { id: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }) => ReactNode
}) {
  const id = useId()
  const desc = [hint && `${id}-h`, error && `${id}-e`].filter(Boolean).join(' ') || undefined
  return (
    <div className="ui-field">
      <label htmlFor={id}>{label}</label>
      {children({ id, 'aria-describedby': desc, 'aria-invalid': error ? true : undefined })}
      {hint && <p id={`${id}-h`} className="ui-field-hint">{hint}</p>}
      {error && <p id={`${id}-e`} className="ui-field-err" role="alert">{error}</p>}
    </div>
  )
}
