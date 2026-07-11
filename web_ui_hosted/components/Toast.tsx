'use client'

import { Toaster, toast } from 'sonner'

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: 'var(--surface-1)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          boxShadow: 'var(--shadow-md)',
          font: 'var(--t-small)',
        },
        classNames: {
          success: '[border-left:3px_solid_var(--success)]',
          error: '[border-left:3px_solid_var(--danger)]',
          warning: '[border-left:3px_solid_var(--warning)]',
          info: '[border-left:3px_solid_var(--accent)]',
        }
      }}
      closeButton
    />
  )
}

// Re-export toast for easy imports
export { toast }
