import { useEffect, useState } from 'react'
import { settingsApi, type Settings } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

type TestState = { loading: boolean; ok?: boolean; message?: string }

function TestButton({ onTest }: { label?: string; onTest: () => Promise<{ ok: boolean; message: string }> }) {
  const [state, setState] = useState<TestState>({ loading: false })
  const run = async () => {
    setState({ loading: true })
    try {
      const r = await onTest()
      setState({ loading: false, ...r })
    } catch (e) {
      setState({ loading: false, ok: false, message: String(e) })
    }
  }
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={run} disabled={state.loading}>
        {state.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verbindung testen'}
      </Button>
      {state.ok === true && <span className="flex items-center gap-1 text-sm text-green-600"><CheckCircle className="h-4 w-4" /> {state.message}</span>}
      {state.ok === false && <span className="flex items-center gap-1 text-sm text-red-600"><AlertCircle className="h-4 w-4" /> {state.message}</span>}
    </div>
  )
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => { settingsApi.get().then(setSettings) }, [])

  const update = <K extends keyof Settings>(k: K, v: Settings[K]) =>
    setSettings(s => s ? { ...s, [k]: v } : s)

  const save = async () => {
    if (!settings) return
    setSaving(true)
    await settingsApi.update(settings)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  if (!settings) return <div className="text-muted-foreground">Lade Einstellungen…</div>

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Einstellungen</h1>
        <Button onClick={save} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
          {saved ? 'Gespeichert!' : 'Speichern'}
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle>IMAP-Verbindung</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 space-y-1">
              <Label>Host</Label>
              <Input value={settings.imap_host} onChange={e => update('imap_host', e.target.value)} placeholder="imap.example.com" />
            </div>
            <div className="space-y-1">
              <Label>Port</Label>
              <Input type="number" value={settings.imap_port} onChange={e => update('imap_port', Number(e.target.value))} />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Benutzername</Label>
            <Input value={settings.imap_user} onChange={e => update('imap_user', e.target.value)} placeholder="user@example.com" />
          </div>
          <div className="space-y-1">
            <Label>Passwort</Label>
            <Input type="password" value={settings.imap_password} onChange={e => update('imap_password', e.target.value)} placeholder="••••••••" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Posteingangsordner</Label>
              <Input value={settings.imap_folder} onChange={e => update('imap_folder', e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Papierkorb-Ordner</Label>
              <Input value={settings.trash_folder} onChange={e => update('trash_folder', e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch checked={settings.imap_tls} onCheckedChange={v => update('imap_tls', v)} />
              <Label>TLS</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={settings.use_idle} onCheckedChange={v => update('use_idle', v)} />
              <Label>IDLE-Modus</Label>
            </div>
          </div>
          {!settings.use_idle && (
            <div className="space-y-1">
              <Label>Polling-Intervall (Sekunden)</Label>
              <Input type="number" value={settings.poll_interval_seconds} onChange={e => update('poll_interval_seconds', Number(e.target.value))} className="w-32" />
            </div>
          )}
          <TestButton label="IMAP testen" onTest={() => {
            const missing: string[] = []
            if (!settings.imap_host) missing.push('Host')
            if (!settings.imap_user) missing.push('Benutzer')
            if (!settings.imap_password) missing.push('Passwort')
            if (missing.length > 0)
              return Promise.resolve({ ok: false, message: `Fehlende Felder: ${missing.join(', ')}` })
            return settingsApi.testImap({
              imap_host: settings.imap_host,
              imap_port: settings.imap_port,
              imap_user: settings.imap_user,
              imap_password: settings.imap_password,
              imap_tls: settings.imap_tls,
            })
          }} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Paperless-NGX</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label>URL</Label>
            <Input value={settings.paperless_url} onChange={e => update('paperless_url', e.target.value)} placeholder="https://paperless.example.com" />
          </div>
          <div className="space-y-1">
            <Label>API-Token</Label>
            <Input type="password" value={settings.paperless_token} onChange={e => update('paperless_token', e.target.value)} placeholder="••••••••" />
          </div>
          <TestButton label="Paperless testen" onTest={() => settingsApi.testPaperless({
            paperless_url: settings.paperless_url,
            paperless_token: settings.paperless_token,
          })} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>KI-Klassifizierung (Anthropic)</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Switch checked={settings.ai_enabled} onCheckedChange={v => update('ai_enabled', v)} />
            <Label>KI-Fallback aktivieren</Label>
          </div>
          {settings.ai_enabled && (
            <>
              <div className="space-y-1">
                <Label>API-Key</Label>
                <Input type="password" value={settings.ai_api_key} onChange={e => update('ai_api_key', e.target.value)} placeholder="sk-ant-…" />
              </div>
              <div className="space-y-1">
                <Label>Modell</Label>
                <Input value={settings.ai_model} onChange={e => update('ai_model', e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>System-Prompt</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={settings.ai_system_prompt}
                  onChange={e => update('ai_system_prompt', e.target.value)}
                />
              </div>
              <TestButton label="API-Key prüfen" onTest={() => settingsApi.testAi({
                ai_api_key: settings.ai_api_key,
                ai_model: settings.ai_model,
              })} />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Sicherheit & Wartung</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label>API-Key (optional, schützt die Web-UI)</Label>
            <Input type="password" value={settings.api_key} onChange={e => update('api_key', e.target.value)} placeholder="Leer = kein Schutz" />
          </div>
          <div className="space-y-1">
            <Label>Audit-Log Aufbewahrung (Tage)</Label>
            <Input type="number" value={settings.audit_retention_days} onChange={e => update('audit_retention_days', Number(e.target.value))} className="w-32" />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
