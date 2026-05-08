import { useEffect, useState, useMemo } from 'react'
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { rulesApi, accountsApi, settingsApi, type Rule, type RuleCreate, type Condition, type ActionType, type ConditionType, type MailAccount } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2, GripVertical, Edit2, X, ChevronDown, ChevronUp, FlaskConical, MailOpen, Mail, Search, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'

type SortField = 'name' | 'action' | 'target' | 'priority'
type SortDir = 'asc' | 'desc'

const CONDITION_TYPES: { value: ConditionType; label: string }[] = [
  { value: 'from_domain', label: 'Absender-Domain' },
  { value: 'from_address', label: 'Absender-Adresse' },
  { value: 'subject_contains', label: 'Betreff enthält' },
  { value: 'subject_regex', label: 'Betreff (Regex)' },
  { value: 'has_attachment', label: 'Hat Anhang' },
  { value: 'attachment_type', label: 'Anhang-Typ' },
  { value: 'body_contains', label: 'Body enthält' },
  { value: 'to_address', label: 'Empfänger-Adresse' },
]

const ACTION_TYPES: { value: ActionType; label: string }[] = [
  { value: 'move', label: 'Verschieben' },
  { value: 'label', label: 'Label setzen' },
  { value: 'paperless', label: 'Paperless + Verschieben' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'keep', label: 'Im Posteingang lassen' },
  { value: 'trash', label: 'In Papierkorb' },
]

const BLANK_RULE: RuleCreate = {
  name: '',
  priority: 100,
  enabled: true,
  conditions: [{ type: 'from_domain', value: '' }],
  action: 'move',
  action_params: { folder: '' },
  account_id: null,
}

function SortableRuleRow({ rule, onEdit, onDelete, onToggle }: { rule: Rule; onEdit: () => void; onDelete: () => void; onToggle: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: rule.id })
  const style = { transform: CSS.Transform.toString(transform), transition }

  return (
    <tr ref={setNodeRef} style={style} className="border-b last:border-0 hover:bg-muted/30">
      <td className="px-2 py-3">
        <button {...attributes} {...listeners} className="cursor-grab text-muted-foreground hover:text-foreground">
          <GripVertical className="h-4 w-4" />
        </button>
      </td>
      <td className="px-3 py-3 font-medium">{rule.name}</td>
      <td className="px-3 py-3 text-sm text-muted-foreground">{rule.conditions.length} Bedingung{rule.conditions.length !== 1 ? 'en' : ''}</td>
      <td className="px-3 py-3"><Badge variant="secondary">{ACTION_TYPES.find(a => a.value === rule.action)?.label ?? rule.action}</Badge></td>
      <td className="px-3 py-3 text-sm text-muted-foreground truncate max-w-[120px]">{rule.action_params?.folder ?? rule.action_params?.url ?? ''}</td>
      <td className="px-3 py-3">
        {rule.action_params?.mark_as_read !== false
          ? <span title="Als gelesen markieren"><MailOpen className="h-4 w-4 text-muted-foreground" /></span>
          : <span title="Ungelesen lassen"><Mail className="h-4 w-4 text-muted-foreground" /></span>}
      </td>
      <td className="px-3 py-3"><Switch checked={rule.enabled} onCheckedChange={onToggle} /></td>
      <td className="px-3 py-3">
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={onEdit}><Edit2 className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={onDelete}><Trash2 className="h-4 w-4 text-destructive" /></Button>
        </div>
      </td>
    </tr>
  )
}

function RuleEditor({ initial, onSave, onClose, paperlessOk, accounts, saveError }: { initial: RuleCreate; onSave: (r: RuleCreate) => void; onClose: () => void; paperlessOk: boolean; accounts: MailAccount[]; saveError?: string | null }) {
  const [form, setForm] = useState<RuleCreate>(initial)
  const [testInput, setTestInput] = useState({ from_address: '', subject: '', body: '' })
  const [testResult, setTestResult] = useState<string | null>(null)
  const [showTest, setShowTest] = useState(false)

  const setField = <K extends keyof RuleCreate>(k: K, v: RuleCreate[K]) => setForm(f => ({ ...f, [k]: v }))

  const addCondition = () => setField('conditions', [...form.conditions, { type: 'from_domain', value: '' }])
  const removeCondition = (i: number) => setField('conditions', form.conditions.filter((_, j) => j !== i))
  const updateCondition = (i: number, c: Condition) => setField('conditions', form.conditions.map((x, j) => j === i ? c : x))

  const runTest = async () => {
    const r = await rulesApi.test({ ...testInput, conditions: form.conditions }) as { matched: boolean; rule_name?: string; action?: string; action_params?: Record<string, string> }
    setTestResult(r.matched ? `Treffer: Bedingungen passen ✓` : 'Kein Treffer')
  }

  const availableActions = ACTION_TYPES.filter(a => a.value !== 'paperless' || paperlessOk)

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Regel bearbeiten</h2>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Name</Label>
              <Input value={form.name} onChange={e => setField('name', e.target.value)} placeholder="Regelname" />
            </div>
            <div className="space-y-1">
              <Label>Priorität</Label>
              <Input type="number" value={form.priority} onChange={e => setField('priority', Number(e.target.value))} />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Bedingungen (AND)</Label>
              <Button variant="outline" size="sm" onClick={addCondition}><Plus className="h-3 w-3 mr-1" /> Bedingung</Button>
            </div>
            {form.conditions.map((cond, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Select value={cond.type} onValueChange={v => updateCondition(i, { ...cond, type: v as ConditionType })}>
                  <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CONDITION_TYPES.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Input value={cond.value} onChange={e => updateCondition(i, { ...cond, value: e.target.value })} placeholder="Wert" className="flex-1" />
                <Button variant="ghost" size="icon" onClick={() => removeCondition(i)}><X className="h-4 w-4" /></Button>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Aktion</Label>
              <Select value={form.action} onValueChange={v => setField('action', v as ActionType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {availableActions.map(a => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {(form.action === 'move' || form.action === 'paperless') && (
              <div className="space-y-1">
                <Label>Zielordner</Label>
                <Input value={String(form.action_params.folder ?? '')} onChange={e => setField('action_params', { ...form.action_params, folder: e.target.value })} placeholder="INBOX.Ordner" />
              </div>
            )}
            {form.action === 'webhook' && (
              <div className="space-y-1">
                <Label>URL</Label>
                <Input value={String(form.action_params.url ?? '')} onChange={e => setField('action_params', { ...form.action_params, url: e.target.value })} placeholder="https://..." />
              </div>
            )}
            {form.action === 'label' && (
              <div className="space-y-1">
                <Label>Label</Label>
                <Input value={String(form.action_params.label ?? '')} onChange={e => setField('action_params', { ...form.action_params, label: e.target.value })} placeholder="Label-Name" />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Switch
              checked={form.action_params.mark_as_read !== false}
              onCheckedChange={v => setField('action_params', { ...form.action_params, mark_as_read: v })}
            />
            <Label>Als gelesen markieren</Label>
          </div>

          <div className="space-y-1">
            <Label>Account (optional)</Label>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              value={form.account_id ?? ''}
              onChange={e => setField('account_id', e.target.value || null)}
            >
              <option value="">Alle Accounts (global)</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          <div className="border rounded-md p-3 space-y-2">
            <button className="flex items-center gap-2 text-sm font-medium" onClick={() => setShowTest(!showTest)}>
              <FlaskConical className="h-4 w-4" /> Test-Modus
              {showTest ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </button>
            {showTest && (
              <div className="space-y-2 pt-1">
                <Input placeholder="Von: user@example.com" value={testInput.from_address} onChange={e => setTestInput(t => ({ ...t, from_address: e.target.value }))} />
                <Input placeholder="Betreff" value={testInput.subject} onChange={e => setTestInput(t => ({ ...t, subject: e.target.value }))} />
                <Input placeholder="Body (Auszug)" value={testInput.body} onChange={e => setTestInput(t => ({ ...t, body: e.target.value }))} />
                <Button variant="outline" size="sm" onClick={runTest}>Testen</Button>
                {testResult && <p className="text-sm text-muted-foreground">{testResult}</p>}
              </div>
            )}
          </div>
        </div>
        {saveError && (
          <div className="mx-4 mb-2 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
            {saveError}
          </div>
        )}
        <div className="flex justify-end gap-2 p-4 border-t">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={() => onSave(form)} disabled={!form.name}>Speichern</Button>
        </div>
      </div>
    </div>
  )
}

function SortHeader({ label, field, sort, onSort }: { label: string; field: SortField; sort: { field: SortField; dir: SortDir } | null; onSort: (f: SortField) => void }) {
  const active = sort?.field === field
  return (
    <button className="flex items-center gap-1 hover:text-foreground transition-colors" onClick={() => onSort(field)}>
      {label}
      {active ? (sort.dir === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />) : <ArrowUpDown className="h-3 w-3 opacity-40" />}
    </button>
  )
}

export default function Rules() {
  const [rules, setRules] = useState<Rule[]>([])
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [editing, setEditing] = useState<{ rule?: Rule; open: boolean }>({ open: false })
  const [saveError, setSaveError] = useState<string | null>(null)
  const [paperlessOk, setPaperlessOk] = useState(false)
  const [search, setSearch] = useState('')
  const [filterAction, setFilterAction] = useState<ActionType | 'all'>('all')
  const [filterEnabled, setFilterEnabled] = useState<'all' | 'active' | 'inactive'>('all')
  const [filterAccount, setFilterAccount] = useState<string>('all')
  const [sort, setSort] = useState<{ field: SortField; dir: SortDir } | null>(null)

  useEffect(() => {
    settingsApi.get().then(s => setPaperlessOk(!!(s.paperless_url && s.paperless_token)))
    accountsApi.list().then(setAccounts)
  }, [])

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const load = async () => setRules(await rulesApi.list())
  useEffect(() => { load() }, [])

  const isFiltered = search !== '' || filterAction !== 'all' || filterEnabled !== 'all' || filterAccount !== 'all' || sort !== null

  const displayRules = useMemo(() => {
    let result = [...rules]
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(r =>
        r.name.toLowerCase().includes(q) ||
        r.conditions.some(c => c.value?.toLowerCase().includes(q)) ||
        (r.action_params?.folder as string | undefined)?.toLowerCase().includes(q)
      )
    }
    if (filterAction !== 'all') result = result.filter(r => r.action === filterAction)
    if (filterEnabled === 'active') result = result.filter(r => r.enabled)
    if (filterEnabled === 'inactive') result = result.filter(r => !r.enabled)
    if (filterAccount !== 'all') result = result.filter(r => filterAccount === 'global' ? r.account_id === null : r.account_id === filterAccount)
    if (sort) {
      result.sort((a, b) => {
        let va = '', vb = ''
        if (sort.field === 'name') { va = a.name; vb = b.name }
        else if (sort.field === 'action') { va = a.action; vb = b.action }
        else if (sort.field === 'target') { va = (a.action_params?.folder as string) ?? ''; vb = (b.action_params?.folder as string) ?? '' }
        else if (sort.field === 'priority') { va = String(a.priority).padStart(6, '0'); vb = String(b.priority).padStart(6, '0') }
        return sort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      })
    }
    return result
  }, [rules, search, filterAction, filterEnabled, filterAccount, sort])

  const handleSort = (field: SortField) => {
    setSort(prev => prev?.field === field ? (prev.dir === 'asc' ? { field, dir: 'desc' } : null) : { field, dir: 'asc' })
  }

  const clearFilters = () => {
    setSearch('')
    setFilterAction('all')
    setFilterEnabled('all')
    setFilterAccount('all')
    setSort(null)
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = rules.findIndex(r => r.id === active.id)
    const newIndex = rules.findIndex(r => r.id === over.id)
    const reordered = arrayMove(rules, oldIndex, newIndex)
    setRules(reordered)
    await rulesApi.reorder(reordered.map(r => r.id))
  }

  const handleSave = async (form: RuleCreate) => {
    try {
      if (editing.rule) {
        await rulesApi.update(editing.rule.id, form)
      } else {
        await rulesApi.create(form)
      }
      setSaveError(null)
      setEditing({ open: false })
      await load()
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Unbekannter Fehler')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Regel löschen?')) return
    await rulesApi.delete(id)
    await load()
  }

  const handleToggle = async (rule: Rule) => {
    await rulesApi.update(rule.id, { enabled: !rule.enabled })
    await load()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Regeln</h1>
        <Button onClick={() => { setEditing({ open: true }); setSaveError(null) }}><Plus className="h-4 w-4 mr-1" /> Neue Regel</Button>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Suchen…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-8 h-9"
          />
        </div>
        <Select value={filterAction} onValueChange={v => setFilterAction(v as ActionType | 'all')}>
          <SelectTrigger className="h-9 w-40"><SelectValue placeholder="Aktion" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Aktionen</SelectItem>
            {ACTION_TYPES.map(a => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filterEnabled} onValueChange={v => setFilterEnabled(v as 'all' | 'active' | 'inactive')}>
          <SelectTrigger className="h-9 w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            <SelectItem value="active">Aktiv</SelectItem>
            <SelectItem value="inactive">Inaktiv</SelectItem>
          </SelectContent>
        </Select>
        {accounts.length > 0 && (
          <Select value={filterAccount} onValueChange={setFilterAccount}>
            <SelectTrigger className="h-9 w-40"><SelectValue placeholder="Account" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Alle Accounts</SelectItem>
              <SelectItem value="global">Global</SelectItem>
              {accounts.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
            </SelectContent>
          </Select>
        )}
        {isFiltered && (
          <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9 text-muted-foreground">
            <X className="h-3.5 w-3.5 mr-1" /> Filter zurücksetzen
          </Button>
        )}
        <span className="text-xs text-muted-foreground ml-auto">{displayRules.length} von {rules.length}</span>
      </div>

      <Card>
        <CardContent className="p-0">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={displayRules.map(r => r.id)} strategy={verticalListSortingStrategy}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50 text-muted-foreground text-xs">
                    <th className="w-8 px-2" title={isFiltered ? 'Drag & Drop bei aktiven Filtern deaktiviert' : ''}></th>
                    <th className="px-3 py-2 text-left font-medium">
                      <SortHeader label="Name" field="name" sort={sort} onSort={handleSort} />
                    </th>
                    <th className="px-3 py-2 text-left font-medium">Bedingungen</th>
                    <th className="px-3 py-2 text-left font-medium">
                      <SortHeader label="Aktion" field="action" sort={sort} onSort={handleSort} />
                    </th>
                    <th className="px-3 py-2 text-left font-medium">
                      <SortHeader label="Ziel" field="target" sort={sort} onSort={handleSort} />
                    </th>
                    <th className="px-3 py-2 text-left font-medium">Gelesen</th>
                    <th className="px-3 py-2 text-left font-medium">Aktiv</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {displayRules.length === 0 ? (
                    <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                      {rules.length === 0 ? 'Keine Regeln. Erstelle deine erste Regel.' : 'Keine Regeln entsprechen den Filterkriterien.'}
                    </td></tr>
                  ) : displayRules.map(r => (
                    <SortableRuleRow
                      key={r.id}
                      rule={r}
                      onEdit={() => { setEditing({ rule: r, open: true }); setSaveError(null) }}
                      onDelete={() => handleDelete(r.id)}
                      onToggle={() => handleToggle(r)}
                    />
                  ))}
                </tbody>
              </table>
            </SortableContext>
          </DndContext>
        </CardContent>
      </Card>

      {editing.open && (
        <RuleEditor
          initial={editing.rule ? {
            name: editing.rule.name,
            priority: editing.rule.priority,
            enabled: editing.rule.enabled,
            conditions: editing.rule.conditions,
            action: editing.rule.action,
            action_params: editing.rule.action_params,
            account_id: editing.rule.account_id,
          } : BLANK_RULE}
          onSave={handleSave}
          onClose={() => { setEditing({ open: false }); setSaveError(null) }}
          paperlessOk={paperlessOk}
          accounts={accounts}
          saveError={saveError}
        />
      )}
    </div>
  )
}
