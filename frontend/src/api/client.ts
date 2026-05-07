const BASE = '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const apiKey = localStorage.getItem('mailsort_api_key') ?? ''
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Rules
export type ConditionType = 'from_domain' | 'from_address' | 'subject_contains' | 'subject_regex' | 'has_attachment' | 'attachment_type' | 'body_contains' | 'to_address'
export type ActionType = 'move' | 'label' | 'paperless' | 'webhook' | 'keep' | 'trash'

export interface Condition {
  type: ConditionType
  value: string
}

export interface Rule {
  id: string
  name: string
  priority: number
  enabled: boolean
  conditions: Condition[]
  action: ActionType
  action_params: Record<string, string | boolean>
  created_at: string
}

export interface RuleCreate {
  name: string
  priority: number
  enabled: boolean
  conditions: Condition[]
  action: ActionType
  action_params: Record<string, string | boolean>
}

export const rulesApi = {
  list: () => request<Rule[]>('/rules'),
  create: (data: RuleCreate) => request<Rule>('/rules', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<RuleCreate>) => request<Rule>(`/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/rules/${id}`, { method: 'DELETE' }),
  reorder: (ids: string[]) => request<void>('/rules/reorder', { method: 'POST', body: JSON.stringify({ ids }) }),
  test: (data: object) => request<object>('/rules/test', { method: 'POST', body: JSON.stringify(data) }),
}

// Audit Logs
export interface AuditLog {
  id: string
  timestamp: string
  message_id: string
  from_address: string
  subject: string
  rule_id: string | null
  rule_name: string | null
  action: string
  target: string | null
  status: 'success' | 'error'
  error_msg: string | null
}

export interface LogsResponse {
  total: number
  page: number
  page_size: number
  items: AuditLog[]
}

export const logsApi = {
  list: (params: Record<string, string | number>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined).map(([k, v]) => [k, String(v)])).toString()
    return request<LogsResponse>(`/logs${qs ? '?' + qs : ''}`)
  },
  exportUrl: () => `${BASE}/logs/export`,
  purge: (days: number) => request<void>(`/logs?older_than_days=${days}`, { method: 'DELETE' }),
}

// Settings
export interface Settings {
  imap_host: string
  imap_port: number
  imap_user: string
  imap_password: string
  imap_tls: boolean
  imap_folder: string
  poll_interval_seconds: number
  use_idle: boolean
  trash_folder: string
  paperless_url: string
  paperless_token: string
  ai_enabled: boolean
  ai_api_key: string
  ai_model: string
  ai_system_prompt: string
  ai_provider: string
  ai_base_url: string
  audit_retention_days: number
  api_key: string
}

export interface ImapTestParams {
  imap_host: string
  imap_port: number
  imap_user: string
  imap_password: string
  imap_tls: boolean
}

export const settingsApi = {
  get: () => request<Settings>('/settings'),
  update: (data: Partial<Settings>) => request<Settings>('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  testImap: (params: ImapTestParams) => request<{ ok: boolean; message: string }>('/settings/test-imap', { method: 'POST', body: JSON.stringify(params) }),
  testPaperless: (params: { paperless_url: string; paperless_token: string }) => request<{ ok: boolean; message: string }>('/settings/test-paperless', { method: 'POST', body: JSON.stringify(params) }),
  testAi: (params: { ai_provider: string; ai_api_key: string; ai_model: string; ai_base_url: string }) => request<{ ok: boolean; message: string }>('/settings/test-ai', { method: 'POST', body: JSON.stringify(params) }),
}

// Status
export interface TopRule {
  name: string
  count: number
}

export interface Status {
  worker_running: boolean
  idle_mode: boolean
  imap_configured: boolean
  paperless_configured: boolean
  mails_today: number
  mails_week: number
  ai_count_week: number
  top_rules: TopRule[]
  timestamp: string
}

export const statusApi = {
  get: () => request<Status>('/status'),
  start: () => request<void>('/worker/start', { method: 'POST' }),
  stop: () => request<void>('/worker/stop', { method: 'POST' }),
  processNow: () => request<void>('/worker/process-now', { method: 'POST' }),
}
