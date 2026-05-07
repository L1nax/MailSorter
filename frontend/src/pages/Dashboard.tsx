import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { statusApi, logsApi, accountsApi, suggestionsApi, type Status, type AuditLog } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Play, Square, RefreshCw, Mail, CheckCircle, AlertCircle, Circle, Bot, Sparkles, ListFilter } from 'lucide-react'

const REFRESH_INTERVAL_MS = 30_000

function ConnectionDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <Circle className={`h-2.5 w-2.5 fill-current ${ok ? 'text-green-500' : 'text-red-400'}`} />
      <span className={ok ? 'text-foreground' : 'text-muted-foreground'}>{label}</span>
    </div>
  )
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [multiAccount, setMultiAccount] = useState(false)
  const [suggestionCount, setSuggestionCount] = useState(0)
  const navigate = useNavigate()
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = async () => {
    const [s, l, sc] = await Promise.all([
      statusApi.get(),
      logsApi.list({ page: 1, page_size: 10 }),
      suggestionsApi.count(),
    ])
    setStatus(s)
    setLogs(l.items)
    setSuggestionCount(sc.count)
  }

  useEffect(() => {
    accountsApi.list().then(a => setMultiAccount(a.length > 1))
  }, [])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, REFRESH_INTERVAL_MS)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const handleStart = async () => { setLoading(true); await statusApi.start(); await refresh(); setLoading(false) }
  const handleStop = async () => { setLoading(true); await statusApi.stop(); await refresh(); setLoading(false) }
  const handleNow = async () => { setLoading(true); await statusApi.processNow(); await refresh(); setLoading(false) }

  const totalWeek = status?.mails_week ?? 0
  const aiWeek = status?.ai_count_week ?? 0
  const aiPct = totalWeek > 0 ? Math.round((aiWeek / totalWeek) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        {suggestionCount > 0 && (
          <button
            onClick={() => navigate('/suggestions')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 border border-primary/20 text-sm text-primary hover:bg-primary/20 transition-colors"
          >
            <Sparkles className="h-4 w-4" />
            {suggestionCount} {suggestionCount === 1 ? 'Regelvorschlag' : 'Regelvorschläge'} verfügbar
          </button>
        )}
        <div className="flex gap-2">
          {status?.worker_running ? (
            <Button variant="outline" size="sm" onClick={handleStop} disabled={loading}>
              <Square className="h-4 w-4 mr-1" /> Worker stoppen
            </Button>
          ) : (
            <Button size="sm" onClick={handleStart} disabled={loading}>
              <Play className="h-4 w-4 mr-1" /> Worker starten
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleNow} disabled={loading}>
            <RefreshCw className="h-4 w-4 mr-1" /> Jetzt verarbeiten
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Worker</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            <Badge variant={status?.worker_running ? 'success' : 'secondary'}>
              {status?.worker_running ? 'Aktiv' : 'Gestoppt'}
            </Badge>
            {status?.worker_running && (
              <p className="text-xs text-muted-foreground">{status.idle_mode ? 'IDLE-Modus' : 'Polling'}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Mails heute</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-2xl font-bold">
              <Mail className="h-5 w-5 text-primary" />
              {status?.mails_today ?? '–'}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Mails diese Woche</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{status?.mails_week ?? '–'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">KI-Anteil (Woche)</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-2xl font-bold">
              <Bot className="h-5 w-5 text-primary" />
              {totalWeek > 0 ? `${aiPct} %` : '–'}
            </div>
            {totalWeek > 0 && <p className="text-xs text-muted-foreground">{aiWeek} von {totalWeek}</p>}
          </CardContent>
        </Card>
      </div>

      {/* Connection status + top rules */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Verbindungen</CardTitle></CardHeader>
          <CardContent className="flex gap-6">
            <ConnectionDot ok={!!status?.imap_configured} label="IMAP konfiguriert" />
            <ConnectionDot ok={!!status?.paperless_configured} label="Paperless konfiguriert" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Top-Regeln (Woche)</CardTitle></CardHeader>
          <CardContent>
            {!status?.top_rules?.length ? (
              <p className="text-sm text-muted-foreground">Noch keine Daten</p>
            ) : (
              <ul className="space-y-1">
                {status.top_rules.map(r => (
                  <li key={r.name} className="flex justify-between text-sm">
                    <span className="truncate max-w-[180px]">{r.name}</span>
                    <span className="text-muted-foreground">{r.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Last actions */}
      <Card>
        <CardHeader><CardTitle>Letzte Aktionen</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Zeit</th>
                {multiAccount && <th className="px-4 py-2 text-left font-medium">Account</th>}
                <th className="px-4 py-2 text-left font-medium">Von</th>
                <th className="px-4 py-2 text-left font-medium">Betreff</th>
                <th className="px-4 py-2 text-left font-medium">Regel</th>
                <th className="px-4 py-2 text-left font-medium">Aktion</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={multiAccount ? 7 : 6} className="px-4 py-8 text-center text-muted-foreground">Keine Einträge</td></tr>
              ) : logs.map(l => (
                <tr key={l.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{new Date(l.timestamp).toLocaleTimeString('de')}</td>
                  {multiAccount && <td className="px-4 py-2 max-w-[120px] truncate text-muted-foreground">{l.account_name ?? '–'}</td>}
                  <td className="px-4 py-2 max-w-[160px] truncate">{l.from_address}</td>
                  <td className="px-4 py-2 max-w-[200px] truncate">{l.subject}</td>
                  <td className="px-4 py-2">
                    {l.rule_name === 'AI'
                      ? <Badge className="bg-purple-100 text-purple-700 border-purple-200 gap-1"><Sparkles className="h-3 w-3" />KI</Badge>
                      : l.rule_name
                        ? <Badge variant="outline" className="gap-1"><ListFilter className="h-3 w-3" />{l.rule_name}</Badge>
                        : <span className="text-muted-foreground text-xs">–</span>}
                  </td>
                  <td className="px-4 py-2">{l.action}{l.target ? ` → ${l.target}` : ''}</td>
                  <td className="px-4 py-2">
                    {l.status === 'success'
                      ? <CheckCircle className="h-4 w-4 text-green-500" />
                      : l.status === 'error'
                        ? <span title={l.error_msg ?? ''}><AlertCircle className="h-4 w-4 text-red-500" /></span>
                        : <RefreshCw className="h-4 w-4 text-muted-foreground animate-spin" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
