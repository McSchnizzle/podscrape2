import type { Metadata } from 'next'
import { Navigation } from '@/components/Navigation'
import { AuthProvider } from '@/components/AuthProvider'
import { AuthGuard } from '@/components/AuthGuard'
import { ToastProvider } from '@/components/Toast'
import Footer from '@/components/Footer'
import './tokens.css'
import './globals.css'

export const metadata: Metadata = {
  title: 'Podcast Digest Admin',
  description: 'Admin interface for RSS podcast digest system',
}

// Runs before hydration so the persisted theme (or OS preference) applies
// on first paint -- otherwise the page flashes light before JS swaps it.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('podcast-admin-theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {}
})();
`

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-bg text-ink antialiased">
        <AuthProvider>
          <AuthGuard>
            {/* Navigation - only shown for authenticated users */}
            <Navigation />

            {/* Main content */}
            <main className="flex-1">
              <div className="mx-auto max-w-7xl px-[var(--space-5)] py-[var(--space-6)] sm:px-[var(--space-6)] lg:px-[var(--space-7)]">
                {children}
              </div>
            </main>

            {/* Footer - only shown for authenticated users */}
            <Footer />
          </AuthGuard>
        </AuthProvider>
        <ToastProvider />
      </body>
    </html>
  )
}