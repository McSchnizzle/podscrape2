'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Rss,
  Tags,
  Eye,
  Repeat,
  GitBranch,
  FlaskConical,
  Radio,
  ScrollText,
  Wrench,
  Settings,
  LogOut,
  Menu,
  X,
  Disc3,
} from 'lucide-react'
import { useAuth } from './AuthProvider'
import { ThemeToggle } from './ThemeToggle'

type NavItem = { href: string; label: string; icon: typeof LayoutDashboard }
type NavGroup = { label: string; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [{ href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Content',
    items: [
      { href: '/episodes', label: 'Episodes', icon: Rss },
      { href: '/digests', label: 'Digests', icon: Disc3 },
      { href: '/feeds', label: 'Feeds', icon: Radio },
      { href: '/topics', label: 'Topics', icon: Tags },
      { href: '/watch-themes', label: 'Watch Themes', icon: Eye },
      { href: '/recurring-topics', label: 'Recurring Topics', icon: Repeat },
      { href: '/story-arcs', label: 'Story Arcs', icon: GitBranch },
    ],
  },
  {
    label: 'Production',
    items: [
      { href: '/script-lab', label: 'Script Lab', icon: FlaskConical },
      { href: '/publishing', label: 'Publishing', icon: Radio },
      { href: '/logs', label: 'Logs', icon: ScrollText },
      { href: '/maintenance', label: 'Maintenance', icon: Wrench },
    ],
  },
  {
    label: 'System',
    items: [{ href: '/settings', label: 'Settings', icon: Settings }],
  },
]

function NavLink({ item, onClick }: { item: NavItem; onClick?: () => void }) {
  const pathname = usePathname()
  const active = pathname === item.href || pathname?.startsWith(`${item.href}/`)
  const Icon = item.icon
  return (
    <a
      href={item.href}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={`group flex items-center gap-[var(--space-3)] rounded-sm px-[var(--space-3)] py-[var(--space-2)] text-[13px] font-medium transition-colors duration-fast ease-house ${
        active
          ? 'bg-accent-soft text-accent'
          : 'text-ink-muted hover:bg-surface-2 hover:text-ink'
      }`}
    >
      <Icon
        size={16}
        strokeWidth={active ? 2.25 : 2}
        className={active ? 'text-accent' : 'text-ink-faint group-hover:text-ink-muted'}
      />
      {item.label}
    </a>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { signOut } = useAuth()
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-[var(--space-3)] px-[var(--space-5)] py-[var(--space-6)]">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-sm"
          style={{ background: 'var(--accent)', color: 'var(--on-accent)' }}
        >
          <Disc3 size={18} />
        </div>
        <div>
          <div style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Podcast Digest</div>
          <div className="micro">Admin</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-[var(--space-4)] pb-[var(--space-4)]">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-[var(--space-5)]">
            <div className="micro mb-[var(--space-2)] px-[var(--space-3)]">{group.label}</div>
            <div className="flex flex-col gap-[2px]">
              {group.items.map((item) => (
                <NavLink key={item.href} item={item} onClick={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex items-center justify-between gap-[var(--space-3)] border-t border-border px-[var(--space-4)] py-[var(--space-4)]">
        <ThemeToggle />
        <button
          onClick={signOut}
          className="btn btn-ghost btn-sm text-ink-subtle hover:text-danger"
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </div>
  )
}

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] border-r border-border bg-surface-1 md:block">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-surface-1 px-[var(--space-4)] py-[var(--space-3)] shadow-sm md:hidden">
        <div className="flex items-center gap-[var(--space-2)]">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-sm"
            style={{ background: 'var(--accent)', color: 'var(--on-accent)' }}
          >
            <Disc3 size={16} />
          </div>
          <span style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Podcast Digest</span>
        </div>
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          className="btn btn-ghost btn-sm"
        >
          <Menu size={18} />
        </button>
      </div>

      {/* Mobile off-canvas menu */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0"
            style={{ background: 'var(--scrim)' }}
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-surface-1 shadow-lg">
            <div className="flex justify-end p-[var(--space-3)]">
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="btn btn-ghost btn-sm"
              >
                <X size={18} />
              </button>
            </div>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}
    </>
  )
}
