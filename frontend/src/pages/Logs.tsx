import { useEffect, useState } from 'react'
import { logsApi, type AuditLog, type LogsResponse } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Download, CheckCircle, AlertCircle, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'

export default function Logs() {
  const [data, setData] = useState<LogsResponse | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const load = async () => {
    const params: Record<string, string | number> = { page, page_size: 50 }
    if (search) params.search = search
    if (status && status !== 'all') params.status = status
    if (dateFrom) params.date_from = dateFrom + 'T00:00:00'
    if (dateTo) params.date_to = dateTo + 'T23:59:59'
    setData(await logsApi.list(params))
  }

  useEffect(() => { load() }, [page, status])

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); setPage(1); load() }

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Audit-Log</h1>
        <a href={logsApi.exportUrl()} download>
          <Button variant="outline" size="sm"><Download className="h-4 w-4 mr-1" /> CSV Export</Button>
        </a>
      </div>

      <form onSubmit={handleSearch} className="space-y-2">
        <div className="flex gap-2">
          <Input
            placeholder="Suche (Absender, Betreff, Message-ID)"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1"
          />
          <Select value={status} onValueChange={v => { setStatus(v); setPage(1) }}>
            <SelectTrigger className="w-40"><SelectValue placeholder="Alle Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Alle Status</SelectItem>
              <SelectItem value="success">Erfolg</SelectItem>
              <SelectItem value="error">Fehler</SelectItem>
              <SelectItem value="processing">In Bearbeitung</SelectItem>
            </SelectContent>
          </Select>
          <Button type="submit" variant="outline">Filtern</Button>
        </div>
        <div className="flex gap-2 items-center text-sm">
          <span className="text-muted-foreground whitespace-nowrap">Zeitraum:</span>
          <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-40" />
          <span className="text-muted-foreground">–</span>
          <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-40" />
          {(dateFrom || dateTo) && (
            <Button type="button" variant="ghost" size="sm" onClick={() => { setDateFrom(''); setDateTo('') }}>
              Zurücksetzen
            </Button>
          )}
        </div>
      </form>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Zeitstempel</th>
                <th className="px-4 py-2 text-left font-medium">Von</th>
                <th className="px-4 py-2 text-left font-medium">Betreff</th>
                <th className="px-4 py-2 text-left font-medium">Regel</th>
                <th className="px-4 py-2 text-left font-medium">Aktion → Ziel</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {!data || data.items.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">Keine Einträge</td></tr>
              ) : data.items.map((l: AuditLog) => (
                <tr key={l.id} className="border-b last:border-0 hover:bg-muted/30" title={l.error_msg ?? undefined}>
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground text-xs">
                    {new Date(l.timestamp).toLocaleString('de')}
                  </td>
                  <td className="px-4 py-2 max-w-[140px] truncate">{l.from_address}</td>
                  <td className="px-4 py-2 max-w-[200px] truncate">{l.subject}</td>
                  <td className="px-4 py-2">
                    {l.rule_name ? <Badge variant="outline">{l.rule_name}</Badge> : <span className="text-muted-foreground">–</span>}
                  </td>
                  <td className="px-4 py-2 text-xs">{l.action}{l.target ? ` → ${l.target}` : ''}</td>
                  <td className="px-4 py-2">
                    {l.status === 'success'
                      ? <CheckCircle className="h-4 w-4 text-green-500" />
                      : l.status === 'error'
                        ? <AlertCircle className="h-4 w-4 text-red-500" />
                        : <RefreshCw className="h-4 w-4 text-muted-foreground animate-spin" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {data && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{data.total} Einträge gesamt</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => setPage(p => p - 1)} disabled={page <= 1}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span>Seite {page} / {totalPages}</span>
            <Button variant="outline" size="icon" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
