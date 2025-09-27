import type { Metadata } from 'next'
import { Navigation } from '@/components/Navigation'
import { AuthProvider } from '@/components/AuthProvider'
import { AuthGuard } from '@/components/AuthGuard'
import Footer from '@/components/Footer'
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
        <AuthProvider>
          <AuthGuard>
            {/* Navigation - only shown for authenticated users */}
            <Navigation />

            {/* Main content */}
            <main className="flex-1">
              <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                {children}
              </div>
            </main>

            {/* Footer - only shown for authenticated users */}
            <Footer />
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  )
}