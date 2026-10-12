const TZ = 'America/Bogota'

export const money = (amount: number) => '$' + Math.round(amount).toLocaleString('es-CO')

// Plain dates come as YYYY-MM-DD; parsing them at noon UTC keeps the day stable in any timezone.
const plainDate = (iso: string) => new Date(`${iso}T12:00:00Z`)

export const longDate = (iso: string) =>
  plainDate(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })

export const shortDate = (iso: string) =>
  plainDate(iso).toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })

export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('es-CO', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: TZ })

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit', second: '2-digit', timeZone: TZ })

export const duration = (secs: number | null) =>
  secs == null ? '' : `${Math.floor(secs / 60)} min ${String(secs % 60).padStart(2, '0')} s`

const DIGITS = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']

export const spokenDigits = (digits: string) => [...digits].map((d) => DIGITS[Number(d)]).join(' ')

export const percent = (share: number) => `${Math.round(share * 100)} %`

export const signed = (score: number) => (score > 0 ? `+${score.toFixed(1)}` : score.toFixed(1))

export const SENTIMENT: Record<string, string> = { positive: 'Tranquilo', neutral: 'Neutral', negative: 'Molesto' }

export const OUTCOME: Record<string, string> = {
  promesa: 'Plan registrado',
  disputa: 'Disputa abierta',
  escalado: 'Pasa a asesor',
  opt_out: 'No contactar',
  sin_acuerdo: 'Sin acuerdo',
}

export const TOOL: Record<string, string> = {
  verify_identity: 'Verificación de identidad',
  get_account_summary: 'Consulta del estado de cuenta',
  get_payment_options: 'Consulta de opciones de pago',
  create_payment_plan: 'Registro del plan',
  send_payment_link: 'Envío del link de pago',
  register_dispute: 'Registro de disputa',
  register_opt_out: 'Registro de no contactar',
  request_callback: 'Solicitud de llamada de asesor',
  post_call_webhook: 'Resumen de fin de llamada',
  payment_page: 'Pago en la página',
}

export const PLAN_STATUS: Record<string, string> = {
  pending_payment: 'Pendiente de pago',
  paid: 'Pagado',
  cancelled: 'Cancelado',
}

export const LINK_STATUS: Record<string, string> = {
  pending: 'Por enviar',
  sent: 'Enviado',
  failed: 'Falló el envío',
  paid: 'Pagado',
}

export const ACCOUNT_STATUS: Record<string, string> = {
  active: 'En mora',
  in_dispute: 'En disputa',
  current: 'Al día',
}

export const historyUrl = (conversationId: string) =>
  `https://elevenlabs.io/app/agents/history/${conversationId}`

export const talkUrl = (agentId: string) => `https://elevenlabs.io/app/talk-to?agent_id=${agentId}`
