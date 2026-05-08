// frontend/src/pages/SuggestionsPage.tsx
import { useEffect, useState } from 'react'
import { suggestionsApi, settingsApi, type RuleSuggestion } from '@/api/client'
import { parseUTC } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { CheckCircle, Clock, XCircle, Sparkles, User } from 'lucide-react'

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  from_domain: 'Domain',
  from_address: 'Absender',
  subject_contains: 'Betreff enthält',
  has_attachment: 'Hat Anhang',
  attachment_type: 'Anhang-Typ',
  to_address: 'Empfänger',
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Offen',
  accepted: 'Angenommen',
  snoozed: 'Zurückgestellt',
  dismissed: 'Abgelehnt',
}

function AcceptModal({ suggestion, onConfirm, onCancel }: {
  suggestion: RuleSuggestion
  onConfirm: (name: string, target: string) => Promise<void>
  onCancel: () => void
}) {
  const [name, setName] = useState(suggestion.suggested_rule_name)
  const [target, setTarget] = useState(suggestion.target)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      await onConfirm(name, target)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unbekannter Fehler')
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border rounded-xl p-6 max-w-md w-full mx-4 space-y-4">
        <h2 className="text-lg font-semibold">Regel erstellen</h2>
        <p className="text-sm text-muted-foreground">Passe die Regel vor dem Speichern an:</p>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="rule-name">Name</Label>
            <Input id="rule-name" value={name} onChange={e => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>Bedingung</Label>
            <div className="bg-secondary rounded-lg px-3 py-2 text-sm text-muted-foreground">
              {SIGNAL_TYPE_LABELS[suggestion.signal_type] ?? suggestion.signal_type} = <span className="font-mono">{suggestion.signal_value}</span>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="rule-target">Zielordner ({suggestion.action})</Label>
            <Input id="rule-target" value={target} onChange={e => setTarget(e.target.value)} />
          </div>
        </div>
        {error && (
          <p className="text-sm text-destructive">Fehler: {error}</p>
        )}
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onCancel} disabled={loading}>Abbrechen</Button>
          <Button onClick={handleSubmit} disabled={loading || !name || !target}>
            {loading ? 'Wird gespeichert…' : 'Regel erstellen'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function SuggestionsPage() {
  const [tab, setTab] = useState<'open' | 'history'>('open')
  const [suggestions, setSuggestions] = useState<RuleSuggestion[]>([])
  const [history, setHistory] = useState<RuleSuggestion[]>([])
  const [confirmSuggestion, setConfirmSuggestion] = useState<RuleSuggestion | null>(null)
  const [threshold, setThreshold] = useState('3')
  const [snoozeDays, setSnoozeDays] = useState('30')
  const [saving, setSaving] = useState(false)

  const loadData = async () => {
    const [open, cfg] = await Promise.all([
      suggestionsApi.list(),
      settingsApi.get(),
    ])
    setSuggestions(open)
    setThreshold(String(cfg.suggestion_threshold))
    setSnoozeDays(String(cfg.suggestion_snooze_days))
    const [acc, snz, dis] = await Promise.all([
      suggestionsApi.list('accepted'),
      suggestionsApi.list('snoozed'),
      suggestionsApi.list('dismissed'),
    ])
    setHistory([...acc, ...snz, ...dis].sort(
      (a, b) => parseUTC(b.created_at).getTime() - parseUTC(a.created_at).getTime()
    ))
  }

  useEffect(() => { loadData() }, [])

  const handleAccept = (s: RuleSuggestion) => setConfirmSuggestion(s)

  const handleConfirmAccept = async (name: string, target: string) => {
    if (!confirmSuggestion) return
    await suggestionsApi.accept(confirmSuggestion.id, { name, target })
    setConfirmSuggestion(null)
    loadData()
  }

  const handleSnooze = async (s: RuleSuggestion, days: number) => {
    await suggestionsApi.snooze(s.id, days)
    loadData()
  }

  const handleDismiss = async (s: RuleSuggestion) => {
    await suggestionsApi.dismiss(s.id)
    loadData()
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    await settingsApi.update({
      suggestion_threshold: parseInt(threshold),
      suggestion_snooze_days: parseInt(snoozeDays),
    })
    setSaving(false)
  }

  return (
    <div className="space-y-6">
      {confirmSuggestion && (
        <AcceptModal
          suggestion={confirmSuggestion}
          onConfirm={handleConfirmAccept}
          onCancel={() => setConfirmSuggestion(null)}
          key={confirmSuggestion.id}
        />
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          Regelvorschläge
        </h1>
      </div>

      <div className="flex gap-1 border-b">
        {(['open', 'history'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t === 'open' ? `Offen (${suggestions.length})` : 'Verlauf'}
          </button>
        ))}
      </div>

      {tab === 'open' && (
        <Card>
          <CardContent className="p-0">
            {suggestions.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">
                Keine offenen Regelvorschläge
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                    <th className="text-left px-4 py-3">Signal</th>
                    <th className="text-left px-4 py-3">Wert</th>
                    <th className="text-left px-4 py-3">Aktion</th>
                    <th className="text-left px-4 py-3">Ziel</th>
                    <th className="text-left px-4 py-3">Account</th>
                    <th className="text-right px-4 py-3">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {suggestions.map(s => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-secondary/30 transition-colors">
                      <td className="px-4 py-3 font-medium">
                        {SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{s.signal_value}</td>
                      <td className="px-4 py-3">{s.action}</td>
                      <td className="px-4 py-3">{s.target}</td>
                      <td className="px-4 py-3">
                        {s.account_name
                          ? <Badge variant="outline" className="gap-1 font-normal"><User className="h-3 w-3" />{s.account_name}</Badge>
                          : <span className="text-muted-foreground">–</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Button size="sm" onClick={() => handleAccept(s)}>
                            <CheckCircle className="h-3.5 w-3.5 mr-1" /> Annehmen
                          </Button>
                          <Select onValueChange={v => handleSnooze(s, parseInt(v))}>
                            <SelectTrigger className="h-8 w-32 text-xs">
                              <Clock className="h-3.5 w-3.5 mr-1" />
                              <SelectValue placeholder="Snooze" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="7">7 Tage</SelectItem>
                              <SelectItem value="30">30 Tage</SelectItem>
                              <SelectItem value="90">90 Tage</SelectItem>
                            </SelectContent>
                          </Select>
                          <Button variant="outline" size="sm" onClick={() => handleDismiss(s)}>
                            <XCircle className="h-3.5 w-3.5 mr-1" /> Ablehnen
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'history' && (
        <Card>
          <CardContent className="p-0">
            {history.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">Kein Verlauf</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                    <th className="text-left px-4 py-3">Signal</th>
                    <th className="text-left px-4 py-3">Wert</th>
                    <th className="text-left px-4 py-3">Ziel</th>
                    <th className="text-left px-4 py-3">Account</th>
                    <th className="text-left px-4 py-3">Status</th>
                    <th className="text-left px-4 py-3">Datum</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(s => (
                    <tr key={s.id} className="border-b last:border-0">
                      <td className="px-4 py-3">{SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type}</td>
                      <td className="px-4 py-3 font-mono text-xs">{s.signal_value}</td>
                      <td className="px-4 py-3">{s.target}</td>
                      <td className="px-4 py-3">
                        {s.account_name
                          ? <Badge variant="outline" className="gap-1 font-normal"><User className="h-3 w-3" />{s.account_name}</Badge>
                          : <span className="text-muted-foreground">–</span>}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={s.status === 'accepted' ? 'default' : 'secondary'}>
                          {STATUS_LABELS[s.status] ?? s.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {parseUTC(s.created_at).toLocaleDateString('de-DE')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Einstellungen</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 max-w-sm">
            <div className="space-y-1">
              <Label htmlFor="threshold">Schwellwert (N)</Label>
              <Input
                id="threshold"
                type="number"
                min={1}
                max={20}
                value={threshold}
                onChange={e => setThreshold(e.target.value)}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">Anzahl gleicher KI-Entscheidungen</p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="snooze">Snooze-Standard (Tage)</Label>
              <Input
                id="snooze"
                type="number"
                min={1}
                value={snoozeDays}
                onChange={e => setSnoozeDays(e.target.value)}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">Standard-Snooze-Dauer</p>
            </div>
          </div>
          <Button size="sm" onClick={handleSaveSettings} disabled={saving}>
            {saving ? 'Speichern...' : 'Einstellungen speichern'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
