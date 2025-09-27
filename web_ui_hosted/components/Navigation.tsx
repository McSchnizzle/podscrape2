'use client'

import { useState } from 'react'
import { useAuth } from './AuthProvider'

export function Navigation() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { user, signOut } = useAuth()

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <div className="flex-shrink-0">
              <h1 className="text-lg sm:text-xl font-bold text-gray-900">
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
              <a href="/topics" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Topics
              </a>
              <a href="/script-lab" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Script Lab
              </a>
              <a href="/episodes" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Episodes
              </a>
              <a href="/publishing" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Publishing
              </a>
              <a href="/maintenance" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Maintenance
              </a>
              <a href="/settings" className="text-gray-900 hover:text-primary-600 px-3 py-2 rounded-md text-sm font-medium">
                Settings
              </a>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {user && (
              <div className="flex items-center space-x-3">
                <span className="hidden sm:block text-sm text-gray-500">
                  {user.email}
                </span>
                <button
                  onClick={signOut}
                  className="text-sm text-gray-500 hover:text-red-600 px-3 py-1 rounded border border-gray-300 hover:border-red-300"
                >
                  Sign Out
                </button>
              </div>
            )}
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden ml-3 inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500"
            >
              <span className="sr-only">Open main menu</span>
              {/* Hamburger icon */}
              <svg
                className={`${mobileMenuOpen ? 'hidden' : 'block'} h-6 w-6`}
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              {/* Close icon */}
              <svg
                className={`${mobileMenuOpen ? 'block' : 'hidden'} h-6 w-6`}
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        <div className={`${mobileMenuOpen ? 'block' : 'hidden'} md:hidden`}>
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 border-t border-gray-200">
            <a
              href="/dashboard"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Dashboard
            </a>
            <a
              href="/feeds"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Feeds
            </a>
            <a
              href="/topics"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Topics
            </a>
            <a
              href="/script-lab"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Script Lab
            </a>
            <a
              href="/episodes"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Episodes
            </a>
            <a
              href="/publishing"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Publishing
            </a>
            <a
              href="/maintenance"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Maintenance
            </a>
            <a
              href="/settings"
              className="text-gray-900 hover:text-primary-600 block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setMobileMenuOpen(false)}
            >
              Settings
            </a>
          </div>
        </div>
      </div>
    </nav>
  )
}
