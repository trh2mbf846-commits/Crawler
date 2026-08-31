import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Übersicht', end: true },
  { to: '/profiles', label: 'Suchprofile', end: false },
  { to: '/portals', label: 'Quellstatus', end: false },
  { to: '/escalations', label: 'Posteingang', end: false },
]

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-surface-muted">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex shrink-0 items-center gap-2 focus-ring rounded">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-sm font-bold text-white">
              AC
            </span>
            <span className="hidden text-base font-semibold text-ink sm:inline">Ausschreibungs-Crawler</span>
          </NavLink>
          <nav className="flex flex-1 flex-wrap gap-1 overflow-x-auto">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `focus-ring whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive ? 'bg-brand-light text-brand' : 'text-ink-muted hover:bg-surface-sunken hover:text-ink'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
    </div>
  )
}
