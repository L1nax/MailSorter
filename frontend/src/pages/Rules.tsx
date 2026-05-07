import { useEffect, useState } from 'react'
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { rulesApi, type Rule, type RuleCreate, type Condition, type ActionType, type ConditionType } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2, GripVertical, Edit2, X, ChevronDown, ChevronUp, FlaskConical } from 'lucide-react'

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

function RuleEditor({ initial, onSave, onClose }: { initial: RuleCreate; onSave: (r: RuleCreate) => void; onClose: () => void }) {
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
                  {ACTION_TYPES.map(a => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {(form.action === 'move' || form.action === 'paperless') && (
              <div className="space-y-1">
                <Label>Zielordner</Label>
                <Input value={form.action_params.folder ?? ''} onChange={e => setField('action_params', { ...form.action_params, folder: e.target.value })} placeholder="INBOX.Ordner" />
              </div>
            )}
            {form.action === 'webhook' && (
              <div className="space-y-1">
                <Label>URL</Label>
                <Input value={form.action_params.url ?? ''} onChange={e => setField('action_params', { ...form.action_params, url: e.target.value })} placeholder="https://..." />
              </div>
            )}
            {form.action === 'label' && (
              <div className="space-y-1">
                <Label>Label</Label>
                <Input value={form.action_params.label ?? ''} onChange={e => setField('action_params', { ...form.action_params, label: e.target.value })} placeholder="Label-Name" />
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
        <div className="flex justify-end gap-2 p-4 border-t">
          <Button variant="outline" onClick={onClose}>Abbrechen</Button>
          <Button onClick={() => onSave(form)} disabled={!form.name}>Speichern</Button>
        </div>
      </div>
    </div>
  )
}

export default function Rules() {
  const [rules, setRules] = useState<Rule[]>([])
  const [editing, setEditing] = useState<{ rule?: Rule; open: boolean }>({ open: false })

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const load = async () => setRules(await rulesApi.list())
  useEffect(() => { load() }, [])

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
    if (editing.rule) {
      await rulesApi.update(editing.rule.id, form)
    } else {
      await rulesApi.create(form)
    }
    setEditing({ open: false })
    await load()
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
        <Button onClick={() => setEditing({ open: true })}><Plus className="h-4 w-4 mr-1" /> Neue Regel</Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={rules.map(r => r.id)} strategy={verticalListSortingStrategy}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="w-8 px-2"></th>
                    <th className="px-3 py-2 text-left font-medium">Name</th>
                    <th className="px-3 py-2 text-left font-medium">Bedingungen</th>
                    <th className="px-3 py-2 text-left font-medium">Aktion</th>
                    <th className="px-3 py-2 text-left font-medium">Ziel</th>
                    <th className="px-3 py-2 text-left font-medium">Aktiv</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {rules.length === 0 ? (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Keine Regeln. Erstelle deine erste Regel.</td></tr>
                  ) : rules.map(r => (
                    <SortableRuleRow
                      key={r.id}
                      rule={r}
                      onEdit={() => setEditing({ rule: r, open: true })}
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
          } : BLANK_RULE}
          onSave={handleSave}
          onClose={() => setEditing({ open: false })}
        />
      )}
    </div>
  )
}
