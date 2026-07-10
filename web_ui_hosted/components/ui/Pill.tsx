import type { ReactNode } from 'react'

export type PillTone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent' | 'live'

const TONE_CLASS: Record<PillTone, string> = {
  neutral: 'pill',
  success: 'pill pill-success',
  warning: 'pill pill-warning',
  danger: 'pill pill-danger',
  accent: 'pill pill-accent',
  live: 'pill pill-live',
}

export function Pill({ tone = 'neutral', children }: { tone?: PillTone; children: ReactNode }) {
  return <span className={TONE_CLASS[tone]}>{children}</span>
}
