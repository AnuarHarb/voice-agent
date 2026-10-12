const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export type Tenant = { id: string; name: string; channel: string; agent_id: string | null }

export type Customer = {
  account_id: string
  full_name: string
  national_id: string
  birth_date: string
  phone_e164: string | null
  account_last4: string
  product: string
  overdue_amount: number
  total_balance: number
  days_past_due: number
  status: 'active' | 'in_dispute' | 'current'
  opted_out: boolean
  calls: number
}

export type Plan = {
  plan_ref: string
  full_name: string
  account_last4: string
  installments: number
  installment_amount: number
  total_amount: number
  first_due_date: string
  hardship: boolean
  status: 'pending_payment' | 'paid' | 'cancelled'
  link_status: 'pending' | 'sent' | 'failed' | 'paid' | null
  link_channel: string | null
  link_sent_at: string | null
  conversation_id: string | null
  created_at: string
}

export type Conversation = {
  conversation_id: string
  started_at: string
  tool_calls: number
  outcome: string | null
  language: string | null
  duration_secs: number | null
  call_successful: string | null
  promise_amount: number | null
  promise_date: string | null
  late_reason: string | null
  hardship: boolean | null
  full_name: string | null
}

export type Case = {
  kind: string
  ref: string
  full_name: string | null
  summary: string
  status: string
  conversation_id: string | null
  created_at: string
}

export type Policy = {
  max_installments: number
  min_installment_cop: number
  first_payment_max_days: number
  hardship_enabled: boolean
  hardship_installments: number
  hardship_grace_days: number
}

export type Overview = {
  tenant: { id: string; name: string; channel: string }
  policy: Policy | null
  customers: Customer[]
  plans: Plan[]
  conversations: Conversation[]
  cases: Case[]
  generated_at: string
}

export type AuditEvent = { created_at: string; tool: string; result: string; detail: Record<string, unknown> }

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal })
  if (!response.ok) throw new Error(`${response.status} en ${path}`)
  return response.json() as Promise<T>
}

export const api = {
  tenants: (signal?: AbortSignal) => get<Tenant[]>('/console/tenants', signal),
  overview: (tenant: string, includeTests: boolean, signal?: AbortSignal) =>
    get<Overview>(`/console/${tenant}/overview?include_tests=${includeTests}`, signal),
  events: (tenant: string, conversationId: string) =>
    get<AuditEvent[]>(`/console/${tenant}/conversations/${encodeURIComponent(conversationId)}/events`),
}
