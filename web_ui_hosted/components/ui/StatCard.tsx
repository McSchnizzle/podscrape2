import type { ReactNode } from 'react'

export function StatCard({
  label,
  value,
  sublabel,
  tone = 'neutral',
  icon,
}: {
  label: string
  value: ReactNode
  sublabel?: ReactNode
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
  icon?: ReactNode
}) {
  const accentColor =
    tone === 'success'
      ? 'var(--success)'
      : tone === 'warning'
        ? 'var(--warning)'
        : tone === 'danger'
          ? 'var(--danger)'
          : 'var(--accent)'

  return (
    <div className="card card-hover relative overflow-hidden">
      <div
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{ background: accentColor }}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-[var(--space-3)]">
        <span className="micro">{label}</span>
        {icon && (
          <span className="text-ink-faint" aria-hidden>
            {icon}
          </span>
        )}
      </div>
      <div className="mt-[var(--space-2)]" style={{ font: 'var(--t-h1)', color: 'var(--text)' }}>
        {value}
      </div>
      {sublabel && (
        <div className="mt-[var(--space-2)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
          {sublabel}
        </div>
      )}
    </div>
  )
}
