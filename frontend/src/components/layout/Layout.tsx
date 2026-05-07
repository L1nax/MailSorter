import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, ListFilter, Settings, ScrollText, Mail, Sun, Moon, Zap, Server, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'
import { suggestionsApi } from '@/api/client'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/accounts', label: 'Accounts', icon: Server, end: false },
  { to: '/rules', label: 'Regeln', icon: ListFilter, end: false },
  { to: '/suggestions', label: 'Vorschläge', icon: Sparkles, end: false },
  { to: '/logs', label: 'Audit-Log', icon: ScrollText, end: false },
  { to: '/settings', label: 'Einstellungen', icon: Settings, end: false },
]

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/accounts': 'Mail-Accounts',
  '/rules': 'Regeln',
  '/suggestions': 'Regelvorschläge',
  '/logs': 'Audit-Log',
  '/settings': 'Einstellungen',
}

export default function Layout() {
  const { theme, toggle } = useTheme()
  const location = useLocation()
  const pageTitle = PAGE_TITLES[location.pathname] ?? 'MailSort'
  const [suggestionCount, setSuggestionCount] = useState(0)

  useEffect(() => {
    suggestionsApi.count().then(r => setSuggestionCount(r.count)).catch(() => {})
    const interval = setInterval(() => {
      suggestionsApi.count().then(r => setSuggestionCount(r.count)).catch(() => {})
    }, 60_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* ── Sidebar ── */}
      <aside
        className="w-[228px] shrink-0 flex flex-col"
        style={{
          backgroundColor: 'hsl(var(--sidebar-bg))',
          borderRight: '1px solid hsl(var(--sidebar-border))',
          transition: 'background-color 0.25s ease, border-color 0.25s ease',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 pt-7 pb-6">
          <div className="logo-icon flex items-center justify-center w-9 h-9 rounded-xl shrink-0">
            <Mail className="h-[18px] w-[18px] text-white" strokeWidth={2.2} />
          </div>
          <div className="min-w-0">
            <div
              className="font-bold text-[16px] tracking-tight leading-none text-foreground"
              style={{ letterSpacing: '-0.025em' }}
            >
              MailSort
            </div>
            <div className="text-[9px] font-mono text-muted-foreground tracking-[0.18em] uppercase mt-1 opacity-70">
              v1.0
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="mx-4 h-px bg-border opacity-60 mb-2" />

        {/* Nav section label */}
        <p className="px-5 py-2 text-[10px] font-semibold text-muted-foreground tracking-[0.12em] uppercase opacity-60">
          Menü
        </p>

        {/* Navigation */}
        <nav className="flex-1 px-3 space-y-0.5">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-[9px] text-[13.5px] font-medium transition-all duration-150 select-none',
                  isActive
                    ? 'bg-primary text-primary-foreground nav-active-ring'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn(
                      'h-4 w-4 shrink-0 transition-transform duration-150',
                      isActive ? 'opacity-100' : 'opacity-70 group-hover:opacity-100 group-hover:scale-110'
                    )}
                    strokeWidth={isActive ? 2.4 : 2}
                  />
                  <span className="truncate">{label}</span>
                  {to === '/suggestions' && suggestionCount > 0 && !isActive && (
                    <span className="ml-auto bg-primary text-primary-foreground text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center shrink-0">
                      {suggestionCount > 9 ? '9+' : suggestionCount}
                    </span>
                  )}
                  {isActive && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-foreground opacity-60 shrink-0" />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="px-3 pb-5">
          <div className="mx-1 h-px bg-border opacity-50 mb-3" />

          {/* Theme toggle */}
          <button
            onClick={toggle}
            className={cn(
              'w-full flex items-center gap-3 rounded-lg px-3 py-[9px]',
              'text-[13.5px] font-medium text-muted-foreground',
              'hover:bg-secondary hover:text-foreground',
              'transition-all duration-150 select-none group'
            )}
            aria-label={theme === 'dark' ? 'Zu Hellmodus wechseln' : 'Zu Dunkelmodus wechseln'}
          >
            <span className="flex items-center justify-center w-4 h-4 shrink-0 opacity-70 group-hover:opacity-100 group-hover:scale-110 transition-transform duration-150">
              {theme === 'dark' ? (
                <Sun className="h-4 w-4" strokeWidth={2} />
              ) : (
                <Moon className="h-4 w-4" strokeWidth={2} />
              )}
            </span>
            <span className="truncate">
              {theme === 'dark' ? 'Hellmodus' : 'Dunkelmodus'}
            </span>
            {/* Toggle pill */}
            <div className="ml-auto shrink-0">
              <div
                className={cn(
                  'toggle-track',
                  theme === 'dark' ? 'bg-primary' : 'bg-border'
                )}
              >
                <div
                  className={cn(
                    'toggle-thumb',
                    theme === 'dark' ? 'left-[18px]' : 'left-0.5'
                  )}
                />
              </div>
            </div>
          </button>

          {/* Version / brand footer */}
          <div className="mt-3 flex items-center gap-1.5 px-3">
            <Zap className="h-3 w-3 text-primary opacity-70" />
            <span className="text-[10px] font-mono text-muted-foreground opacity-50 tracking-wide">
              self-hosted
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header
          className="topbar-glass shrink-0 flex items-center justify-between px-6 py-3 z-10"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">{pageTitle}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 status-pulse"
              title="System aktiv"
            />
            <span className="text-[11px] font-mono text-muted-foreground opacity-70 tracking-wide">
              online
            </span>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
