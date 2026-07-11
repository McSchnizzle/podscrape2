import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-[var(--space-7)] flex flex-col gap-[var(--space-4)] sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-[length:inherit]" style={{ font: 'var(--t-h1)', color: 'var(--text)' }}>
          {title}
        </h1>
        {description && (
          <p className="mt-[var(--space-2)] max-w-2xl text-ink-subtle" style={{ font: 'var(--t-body)' }}>
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-[var(--space-3)]">{actions}</div>}
    </div>
  )
}
