import { useCallback, useEffect, useRef, useState } from 'react'
import { settingsApi, backupApi, type Settings } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react'

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
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [customModel, setCustomModel] = useState(false)
  const fetchIdRef = useRef(0)
  const [backupSections, setBackupSections] = useState<string[]>(['rules', 'accounts', 'settings', 'suggestions'])
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<Record<string, number> | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [importMode, setImportMode] = useState<'merge' | 'replace'>('merge')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const DEFAULT_MODELS: Record<string, string> = {
    claude: 'claude-sonnet-4-6', openai: 'gpt-4o-mini', gemini: 'gemini-2.0-flash', ollama: 'llama3.2',
  }

  const fetchModels = useCallback(async (provider: string, apiKey: string, baseUrl: string) => {
    const id = ++fetchIdRef.current
    setLoadingModels(true)
    try {
      const result = await settingsApi.listAiModels({ provider, api_key: apiKey, base_url: baseUrl })
      if (id !== fetchIdRef.current) return
      setAvailableModels(result.models)
    } catch {
      if (id !== fetchIdRef.current) return
      setAvailableModels([])
    } finally {
      if (id === fetchIdRef.current) setLoadingModels(false)
    }
  }, [])

  useEffect(() => { settingsApi.get().then(s => { setSettings(s); fetchModels(s.ai_provider, s.ai_api_key, s.ai_base_url) }) }, [])

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

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      await backupApi.export(backupSections)
    } catch (e) {
      setExportError(String(e))
    } finally {
      setExporting(false)
    }
  }

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    setImportError(null)
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      const counts = await backupApi.import(data, importMode)
      setImportResult(counts)
    } catch (err) {
      setImportError(String(err))
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const toggleSection = (s: string) =>
    setBackupSections(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    )

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
        <CardHeader><CardTitle>KI-Klassifizierung</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <Switch checked={settings.ai_enabled} onCheckedChange={v => update('ai_enabled', v)} />
            <Label>KI-Fallback aktivieren</Label>
          </div>
          {settings.ai_enabled && (
            <>
              <div className="space-y-1">
                <Label>Provider</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                  value={settings.ai_provider}
                  onChange={e => {
                    const p = e.target.value
                    update('ai_provider', p)
                    update('ai_model', DEFAULT_MODELS[p] ?? '')
                    setCustomModel(false)
                    fetchModels(p, settings.ai_api_key, settings.ai_base_url)
                  }}
                >
                  <option value="claude">Claude (Anthropic)</option>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini (Google)</option>
                  <option value="ollama">Ollama (lokal)</option>
                </select>
              </div>
              {settings.ai_provider !== 'ollama' && (
                <div className="space-y-1">
                  <Label>API-Key</Label>
                  <Input type="password" value={settings.ai_api_key}
                    onChange={e => update('ai_api_key', e.target.value)} placeholder="••••••••" />
                </div>
              )}
              {(settings.ai_provider === 'openai' || settings.ai_provider === 'ollama') && (
                <div className="space-y-1">
                  <Label>Base URL</Label>
                  <Input value={settings.ai_base_url}
                    onChange={e => update('ai_base_url', e.target.value)}
                    placeholder={settings.ai_provider === 'ollama' ? 'http://localhost:11434/v1' : 'https://api.openai.com/v1'} />
                </div>
              )}
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Label>Modell</Label>
                  {loadingModels
                    ? <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                    : <button type="button" title="Modellliste neu laden"
                        onClick={() => fetchModels(settings.ai_provider, settings.ai_api_key, settings.ai_base_url)}
                        className="text-muted-foreground hover:text-foreground transition-colors">
                        <RefreshCw className="h-3 w-3" />
                      </button>
                  }
                </div>
                {availableModels.length > 0 && !customModel ? (
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                    value={availableModels.includes(settings.ai_model) ? settings.ai_model : '__custom__'}
                    onChange={e => {
                      if (e.target.value === '__custom__') { setCustomModel(true) }
                      else { update('ai_model', e.target.value) }
                    }}
                  >
                    {!availableModels.includes(settings.ai_model) && settings.ai_model && (
                      <option value={settings.ai_model}>{settings.ai_model}</option>
                    )}
                    {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                    <option value="__custom__">— Benutzerdefiniert eingeben …</option>
                  </select>
                ) : (
                  <div className="flex gap-2">
                    <Input
                      value={settings.ai_model}
                      onChange={e => update('ai_model', e.target.value)}
                      placeholder={DEFAULT_MODELS[settings.ai_provider] ?? ''}
                    />
                    {availableModels.length > 0 && (
                      <button type="button" onClick={() => setCustomModel(false)}
                        className="text-xs text-muted-foreground hover:text-foreground whitespace-nowrap">
                        ← Liste
                      </button>
                    )}
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <Label>System-Prompt</Label>
                <textarea
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={settings.ai_system_prompt}
                  onChange={e => update('ai_system_prompt', e.target.value)}
                />
              </div>
              <TestButton onTest={() => {
                const missing: string[] = []
                if (settings.ai_provider !== 'ollama' && !settings.ai_api_key) missing.push('API-Key')
                if (missing.length > 0)
                  return Promise.resolve({ ok: false, message: `Fehlende Felder: ${missing.join(', ')}` })
                return settingsApi.testAi({
                  ai_provider: settings.ai_provider,
                  ai_api_key: settings.ai_api_key,
                  ai_model: settings.ai_model,
                  ai_base_url: settings.ai_base_url,
                })
              }} />
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

      <Card>
        <CardHeader>
          <CardTitle>KI-Regelvorschläge</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 max-w-sm">
            <div className="space-y-1">
              <Label htmlFor="suggestion_threshold">Schwellwert (N)</Label>
              <Input
                id="suggestion_threshold"
                type="number"
                min={1}
                max={20}
                value={settings.suggestion_threshold ?? 3}
                onChange={e => update('suggestion_threshold', parseInt(e.target.value))}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">
                Anzahl gleicher KI-Entscheidungen bis ein Vorschlag erscheint
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="suggestion_snooze_days">Snooze-Dauer (Tage)</Label>
              <Input
                id="suggestion_snooze_days"
                type="number"
                min={1}
                value={settings.suggestion_snooze_days ?? 30}
                onChange={e => update('suggestion_snooze_days', parseInt(e.target.value))}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">Standard-Snooze-Dauer für Vorschläge</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Backup & Restore</CardTitle></CardHeader>
        <CardContent className="space-y-5">
          {/* Export */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Export</p>
            <div className="flex flex-wrap gap-3">
              {[
                { key: 'rules', label: 'Regeln' },
                { key: 'accounts', label: 'Mail-Accounts' },
                { key: 'settings', label: 'Einstellungen' },
                { key: 'suggestions', label: 'KI-Vorschläge & Signale' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={backupSections.includes(key)}
                    onChange={() => toggleSection(key)}
                    className="rounded"
                  />
                  {label}
                </label>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={exporting || backupSections.length === 0}
            >
              {exporting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
              Backup herunterladen
            </Button>
            {exportError && (
              <p className="text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-4 w-4" />
                {exportError}
              </p>
            )}
          </div>

          <div className="h-px bg-border" />

          {/* Import */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Import</p>
            <div className="flex gap-4">
              {(['merge', 'replace'] as const).map(m => (
                <label key={m} className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                  <input
                    type="radio"
                    name="importMode"
                    value={m}
                    checked={importMode === m}
                    onChange={() => setImportMode(m)}
                  />
                  {m === 'merge' ? 'Merge (bestehende behalten)' : 'Überschreiben'}
                </label>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={importing}
              >
                {importing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
                Backup-Datei auswählen…
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={handleImportFile}
              />
            </div>
            {importResult && (
              <p className="text-sm text-green-600 flex items-center gap-1">
                <CheckCircle className="h-4 w-4" />
                Importiert: {Object.entries(importResult).filter(([, v]) => v > 0).map(([k, v]) => `${k}: ${v}`).join(', ') || 'Keine neuen Einträge'}
              </p>
            )}
            {importError && (
              <p className="text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-4 w-4" />
                {importError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
