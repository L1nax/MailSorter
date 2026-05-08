import { useEffect, useState } from 'react'
import { accountsApi, type MailAccount, type MailAccountCreate } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Edit2, Trash2, CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react'

const BLANK: MailAccountCreate = {
  name: '',
  imap_host: '',
  imap_port: 993,
  imap_user: '',
  imap_password: '',
  imap_tls: true,
  imap_folder: 'INBOX',
  trash_folder: 'Trash',
  poll_interval_seconds: 60,
  use_idle: false,
  enabled: true,
}

type TestState = { loading: boolean; ok?: boolean; message?: string }

function AccountForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: MailAccountCreate
  onSave: (data: MailAccountCreate) => Promise<void>
  onCancel: () => void
}) {
  const [form, setForm] = useState<MailAccountCreate>(initial)
  const [saving, setSaving] = useState(false)
  const [test, setTest] = useState<TestState>({ loading: false })

  const set = <K extends keyof MailAccountCreate>(k: K, v: MailAccountCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(form)
    } finally {
      setSaving(false)
    }
  }

  const runTest = async () => {
    setTest({ loading: true })
    try {
      const r = await accountsApi.testImap({
        imap_host: form.imap_host,
        imap_port: form.imap_port,
        imap_user: form.imap_user,
        imap_password: form.imap_password,
        imap_tls: form.imap_tls,
      })
      setTest({ loading: false, ...r })
    } catch (e) {
      setTest({ loading: false, ok: false, message: String(e) })
    }
  }

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1 col-span-2">
          <Label>Account-Name</Label>
          <Input value={form.name} onChange={e => set('name', e.target.value)} placeholder="z.B. Privat, Arbeit" />
        </div>
        <div className="space-y-1 col-span-2 md:col-span-1">
          <Label>IMAP-Host</Label>
          <Input value={form.imap_host} onChange={e => set('imap_host', e.target.value)} placeholder="imap.example.com" />
        </div>
        <div className="space-y-1">
          <Label>Port</Label>
          <Input type="number" value={form.imap_port} onChange={e => set('imap_port', Number(e.target.value))} />
        </div>
        <div className="space-y-1 col-span-2">
          <Label>Benutzername</Label>
          <Input value={form.imap_user} onChange={e => set('imap_user', e.target.value)} placeholder="user@example.com" />
        </div>
        <div className="space-y-1 col-span-2">
          <Label>Passwort</Label>
          <Input type="password" value={form.imap_password} onChange={e => set('imap_password', e.target.value)} placeholder="••••••••" />
        </div>
        <div className="space-y-1">
          <Label>Posteingangsordner</Label>
          <Input value={form.imap_folder} onChange={e => set('imap_folder', e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Papierkorb-Ordner</Label>
          <Input value={form.trash_folder} onChange={e => set('trash_folder', e.target.value)} />
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Switch checked={form.imap_tls} onCheckedChange={v => set('imap_tls', v)} />
          <Label>TLS</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={form.use_idle} onCheckedChange={v => set('use_idle', v)} />
          <Label>IDLE-Modus</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={form.enabled} onCheckedChange={v => set('enabled', v)} />
          <Label>Aktiv</Label>
        </div>
      </div>
      {!form.use_idle && (
        <div className="space-y-1">
          <Label>Polling-Intervall (Sekunden)</Label>
          <Input type="number" value={form.poll_interval_seconds} onChange={e => set('poll_interval_seconds', Number(e.target.value))} className="w-32" />
        </div>
      )}
      <div className="flex items-center gap-3 pt-1">
        <Button variant="outline" size="sm" onClick={runTest} disabled={test.loading}>
          {test.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
          Verbindung testen
        </Button>
        {test.ok === true && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <CheckCircle className="h-4 w-4" /> {test.message}
          </span>
        )}
        {test.ok === false && (
          <span className="flex items-center gap-1 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" /> {test.message}
          </span>
        )}
      </div>
      <div className="flex justify-end gap-2 pt-2 border-t">
        <Button variant="outline" onClick={onCancel}>Abbrechen</Button>
        <Button onClick={handleSave} disabled={saving || !form.name}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
          Speichern
        </Button>
      </div>
    </div>
  )
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [editing, setEditing] = useState<{ id?: string; open: boolean }>({ open: false })
  const [resetting, setResetting] = useState<string | null>(null)

  const load = async () => setAccounts(await accountsApi.list())
  useEffect(() => { load() }, [])

  const handleSave = async (data: MailAccountCreate) => {
    if (editing.id) {
      await accountsApi.update(editing.id, data)
    } else {
      await accountsApi.create(data)
    }
    await load()
    setEditing({ open: false })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Account löschen? Verknüpfte Regeln werden global.')) return
    await accountsApi.delete(id)
    await load()
  }

  const handleToggle = async (account: MailAccount) => {
    setAccounts(prev => prev.map(a => a.id === account.id ? { ...a, enabled: !a.enabled } : a))
    await accountsApi.update(account.id, { enabled: !account.enabled })
    await load()
  }

  const handleResetFlags = async (id: string) => {
    if (!confirm('$MailSortProcessed-Flag für alle Mails im Posteingang entfernen? Mails werden beim nächsten Abruf erneut verarbeitet.')) return
    setResetting(id)
    try {
      await accountsApi.resetFlags(id)
    } finally {
      setResetting(null)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Mail-Accounts</h1>
        <Button onClick={() => setEditing({ open: true })}>
          <Plus className="h-4 w-4 mr-1" /> Account hinzufügen
        </Button>
      </div>

      {editing.open && !editing.id && (
        <AccountForm
          initial={BLANK}
          onSave={handleSave}
          onCancel={() => setEditing({ open: false })}
        />
      )}

      {accounts.length === 0 && !editing.open && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Noch kein Account konfiguriert. Klicke auf „Account hinzufügen".
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {accounts.map(account => (
          <Card key={account.id}>
            {editing.open && editing.id === account.id ? (
              <CardContent className="pt-4">
                <AccountForm
                  initial={{
                    name: account.name,
                    imap_host: account.imap_host,
                    imap_port: account.imap_port,
                    imap_user: account.imap_user,
                    imap_password: account.imap_password,
                    imap_tls: account.imap_tls,
                    imap_folder: account.imap_folder,
                    trash_folder: account.trash_folder,
                    poll_interval_seconds: account.poll_interval_seconds,
                    use_idle: account.use_idle,
                    enabled: account.enabled,
                  }}
                  onSave={handleSave}
                  onCancel={() => setEditing({ open: false })}
                />
              </CardContent>
            ) : (
              <>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{account.name}</CardTitle>
                    <div className="flex items-center gap-2">
                      <Switch checked={account.enabled} onCheckedChange={() => handleToggle(account)} />
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Mails neu verarbeiten (Flag zurücksetzen)"
                        onClick={() => handleResetFlags(account.id)}
                        disabled={resetting === account.id}
                      >
                        {resetting === account.id
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <RefreshCw className="h-4 w-4" />}
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setEditing({ id: account.id, open: true })}>
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(account.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground space-y-0.5">
                    <div>{account.imap_user} @ {account.imap_host}:{account.imap_port}</div>
                    <div>Ordner: {account.imap_folder} · Papierkorb: {account.trash_folder}</div>
                    <div>{account.use_idle ? 'IDLE-Modus' : `Polling alle ${account.poll_interval_seconds}s`} · TLS: {account.imap_tls ? 'ja' : 'nein'}</div>
                  </div>
                </CardContent>
              </>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
