import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, ListFilter, Settings, ScrollText, Mail } from 'lucide-react'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/rules', label: 'Regeln', icon: ListFilter },
  { to: '/logs', label: 'Audit-Log', icon: ScrollText },
  { to: '/settings', label: 'Einstellungen', icon: Settings },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="w-56 border-r flex flex-col py-4 gap-1 px-2 shrink-0">
        <div className="flex items-center gap-2 px-3 mb-4">
          <Mail className="h-5 w-5 text-primary" />
          <span className="font-semibold text-lg">MailSort</span>
        </div>
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn('flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent', isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground')
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
