import { useEffect, useState } from 'react'
import { statusApi, logsApi, type Status, type AuditLog } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Play, Square, RefreshCw, Mail, CheckCircle, AlertCircle } from 'lucide-react'

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null)
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    const [s, l] = await Promise.all([statusApi.get(), logsApi.list({ page: 1, page_size: 10 })])
    setStatus(s)
    setLogs(l.items)
  }

  useEffect(() => { refresh() }, [])

  const handleStart = async () => { setLoading(true); await statusApi.start(); await refresh(); setLoading(false) }
  const handleStop = async () => { setLoading(true); await statusApi.stop(); await refresh(); setLoading(false) }
  const handleNow = async () => { setLoading(true); await statusApi.processNow(); await refresh(); setLoading(false) }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Worker-Status</CardTitle></CardHeader>
          <CardContent>
            <Badge variant={status?.worker_running ? 'success' : 'secondary'}>
              {status?.worker_running ? 'Aktiv' : 'Gestoppt'}
            </Badge>
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
      </div>

      <Card>
        <CardHeader><CardTitle>Letzte Aktionen</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Zeit</th>
                <th className="px-4 py-2 text-left font-medium">Von</th>
                <th className="px-4 py-2 text-left font-medium">Betreff</th>
                <th className="px-4 py-2 text-left font-medium">Aktion</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">Keine Einträge</td></tr>
              ) : logs.map(l => (
                <tr key={l.id} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{new Date(l.timestamp).toLocaleTimeString('de')}</td>
                  <td className="px-4 py-2 max-w-[160px] truncate">{l.from_address}</td>
                  <td className="px-4 py-2 max-w-[200px] truncate">{l.subject}</td>
                  <td className="px-4 py-2">{l.action}{l.target ? ` → ${l.target}` : ''}</td>
                  <td className="px-4 py-2">
                    {l.status === 'success'
                      ? <CheckCircle className="h-4 w-4 text-green-500" />
                      : <span title={l.error_msg ?? undefined}><AlertCircle className="h-4 w-4 text-red-500" /></span>}
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
