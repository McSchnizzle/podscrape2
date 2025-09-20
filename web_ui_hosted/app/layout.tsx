import type { Metadata } from 'next'
import { Navigation } from '@/components/Navigation'
import './globals.css'

export const metadata: Metadata = {
  title: 'Podcast Digest Admin',
  description: 'Admin interface for RSS podcast digest system',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <div className="min-h-screen flex flex-col">
          {/* Navigation */}
          <Navigation />

          {/* Main content */}
          <main className="flex-1">
            <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
              {children}
            </div>
          </main>

          {/* Footer */}
          <footer className="bg-white border-t border-gray-200">
            <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
              <p className="text-sm text-gray-500 text-center">
                Powered by Next.js + Supabase + GitHub Actions
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  )
}