import type { Metadata } from 'next'
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
          <nav className="bg-white shadow-sm border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex items-center space-x-8">
                  <div className="flex-shrink-0">
                    <h1 className="text-xl font-bold text-gray-900">
                      Podcast Digest Admin
                    </h1>
                  </div>
                  <div className="hidden md:flex items-center space-x-4">
                    <a href="/dashboard" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                      Dashboard
                    </a>
                    <a href="/feeds" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                      Feeds
                    </a>
                    <a href="/settings" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                      Settings
                    </a>
                  </div>
                </div>
                <div className="flex items-center">
                  <span className="text-sm text-gray-500">
                    Hosted Admin Interface
                  </span>
                </div>
              </div>
            </div>
          </nav>

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