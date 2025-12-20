'use client'

import { Toaster, toast } from 'sonner'

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: 'white',
          border: '1px solid #e5e7eb',
          borderRadius: '0.5rem',
        },
        classNames: {
          success: 'border-l-4 border-l-green-500',
          error: 'border-l-4 border-l-red-500',
          warning: 'border-l-4 border-l-amber-500',
          info: 'border-l-4 border-l-blue-500',
        }
      }}
      richColors
      closeButton
    />
  )
}

// Re-export toast for easy imports
export { toast }
