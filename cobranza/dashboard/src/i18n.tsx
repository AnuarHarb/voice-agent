import { createContext, use, type ReactNode } from 'react'
import type { Overview } from './api'

export type Lang = 'es' | 'en'

const TZ = 'America/Bogota'
const LOCALE: Record<Lang, string> = { es: 'es-CO', en: 'en-US' }
const DIGITS: Record<Lang, string[]> = {
  es: ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve'],
  en: ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'],
}

// Plain dates come as YYYY-MM-DD; parsing them at noon UTC keeps the day stable in any timezone.
const plainDate = (iso: string) => new Date(`${iso}T12:00:00Z`)

function formatters(lang: Lang) {
  const locale = LOCALE[lang]
  return {
    money: (amount: number) => (lang === 'es' ? '$' : 'COP ') + Math.round(amount).toLocaleString(locale),
    longDate: (iso: string) =>
      plainDate(iso).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }),
    shortDate: (iso: string) =>
      plainDate(iso).toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }),
    dateTime: (iso: string) =>
      new Date(iso).toLocaleString(locale, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: TZ }),
    clock: (iso: string) =>
      new Date(iso).toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit', second: '2-digit', timeZone: TZ }),
    duration: (secs: number | null) =>
      secs == null ? '' : `${Math.floor(secs / 60)} min ${String(secs % 60).padStart(2, '0')} s`,
    spokenDigits: (digits: string) => [...digits].map((d) => DIGITS[lang][Number(d)]).join(' '),
    percent: (share: number) => `${Math.round(share * 100)} %`,
    signed: (score: number) => (score > 0 ? `+${score.toFixed(1)}` : score.toFixed(1)),
  }
}

export type Format = ReturnType<typeof formatters>

type SummaryFacts = { n: number; overdue: string; plans: number; recovered: string; paid: number; scored: number; calm: number }

const es = {
  appTitle: 'Mesa de cobranza',
  docTitle: (fintech: string) => `Mesa de cobranza de ${fintech}`,
  fintechNav: 'Fintech',
  languageGroup: 'Idioma',
  summaryLabel: 'Resumen',
  agentFallback: 'el agente',
  loading: (fintech?: string) => `Cargando ${fintech ?? 'la fintech'}…`,
  includeTests: 'Incluir pruebas automáticas',
  offline: (error: string) => `Sin conexión con el backend (${error}). Reintentando cada 10 segundos.`,
  updatedAt: (time: ReactNode) => <>Actualizado a las {time}, se refresca solo</>,
  summary: (s: SummaryFacts) => (
    <>
      {s.n} {s.n === 1 ? 'cliente debe' : 'clientes deben'} <strong>{s.overdue}</strong> en mora.{' '}
      {s.plans === 0 ? 'Todavía no hay planes acordados por voz.' : (
        <>
          Por voz se han comprometido <strong>{s.recovered}</strong> en {s.plans === 1 ? '1 plan' : `${s.plans} planes`}
          {s.paid > 0 ? `, ${s.paid} ya ${s.paid === 1 ? 'pagado' : 'pagados'}` : ''}.
        </>
      )}
      {s.scored > 0 && ' ' + (s.scored === 1
        ? `La llamada analizada terminó con el cliente ${s.calm ? 'tranquilo' : 'molesto'}.`
        : `${s.calm === s.scored ? 'Todas las' : `${s.calm} de ${s.scored}`} llamadas analizadas terminaron sin el cliente molesto.`)}
    </>
  ),
  policyTitle: 'Política de crédito (por producto)',
  policy: (p: Record<string, unknown>) => {
    const opts = (p.options ?? {}) as Record<string, unknown>
    if (opts.mode === 'card_preventive') return <>Tarjeta al día: pago mínimo, total y rediferido según política.</>
    if (opts.mode === 'promise') return <>Microcrédito: pago hoy o promesa dentro de {String(opts.promise_max_days ?? 7)} días.</>
    return (
      <>
        Modo {String(opts.mode ?? 'overdue')}: hasta {String(opts.max_installments ?? '—')} cuotas, mínimo{' '}
        {String(opts.min_installment_cop ?? '—')} COP. Sin descuentos.
      </>
    )
  },
  productTabsLabel: 'Producto',
  productAll: 'Todos',
  conversionTitle: 'Conversión comercial',
  conversionOffered: 'Ofertas activas',
  conversionDisbursed: 'Desembolsos confirmados',
  conversionRejected: 'Rechazadas',
  conversionAmount: 'Monto desembolsado',
  casesNav: 'Casos de uso',
  consoleNav: 'Consola',
  casesCatalogTitle: 'Catálogo de casos',
  casesCatalogLead: 'Cinco conversaciones sobre la misma arquitectura: cliente, integración y agente.',
  casesConsoleCaption: 'Vista de consola después de la llamada',
  casesScreenshotPending: 'Captura pendiente',
  casesAudioPending: 'Grabación pendiente (60–90 s)',
  casesTryLive: 'Pruébalo tú',
  casesAgentPending: 'Publica el agente del caso para habilitar el enlace.',
  casesTenantNote: (name: string) => `Demos de ${name}; nombres y datos ficticios.`,
  footer: (
    <>
      Simulación del back office de la fintech. Cada consulta usa el rol de solo lectura <code>cobranza_console</code>,
      y la seguridad por fila de Supabase limita los datos a la fintech elegida. Lo único que escribe es
      «Agregar cliente al azar», a través de una función que solo puede crear clientes ficticios en esa fintech.
    </>
  ),

  liveTitle: 'Llamada en vivo',
  liveIntro: (agent: string) =>
    `Habla con ${agent} desde aquí con tu micrófono. El plan o el caso aparece en las tablas apenas cuelgues. Cada llamada consume créditos de ElevenLabs.`,
  connecting: (agent: string) => `Conectando con ${agent}…`,
  ready: 'Lista para llamar',
  thinking: (agent: string) => `${agent} está consultando…`,
  talking: (agent: string) => `${agent} está hablando`,
  listening: (agent: string) => `${agent} te escucha`,
  callingAs: 'Llamas como',
  nationalId: 'Cédula',
  birthDate: 'Nacimiento',
  hangUp: 'Colgar',
  mute: 'Silenciar',
  unmute: 'Activar micrófono',
  callAgent: (agent: string) => `Llamar a ${agent}`,
  transcriptLabel: (agent: string) => `Transcripción con ${agent}`,
  transcriptLive: (agent: string) => `Saluda a ${agent}; lo que digan los dos aparece aquí.`,
  transcriptIdle: 'La transcripción aparece aquí durante la llamada. Para llamar como un cliente, usa el botón de su tarjeta.',
  scrollLatest: 'Ir al último mensaje',
  micDenied: 'Sin acceso al micrófono. Permítelo en el navegador para llamar.',

  customersTitle: 'Clientes',
  customersIntro: (agent: string) =>
    `Datos ficticios para probar. Para verificarte con ${agent}, di los últimos cuatro dígitos de la cédula y la fecha de nacimiento.`,
  addCustomer: 'Agregar cliente al azar',
  adding: 'Creando…',
  addFailed: (error: string) => `No se pudo crear el cliente (${error}).`,
  say: (digits: string, date: string) => `Di: «${digits}» y «${date}».`,
  callAs: (firstName: string) => `Llamar como ${firstName}`,
  optedOut: 'No contactar',
  overdue: 'En mora',
  daysPastDue: 'Días de mora',
  totalBalance: 'Saldo total',
  accountLine: (product: string, last4: string) => `${product}, cuenta terminada en ${last4}`,
  calls: (n: number) => (n === 1 ? '1 llamada' : `${n} llamadas`),

  plansTitle: 'Planes registrados',
  plansIntro: 'Cada plan sale de una opción que calculó la política de crédito; el agente no puede inventar montos.',
  plansEmpty: 'Todavía no hay planes. Llama al agente y acepta una opción para ver aparecer el primero.',
  colPlan: 'Plan',
  colCustomer: 'Cliente',
  colInstallments: 'Cuotas',
  colInstallment: 'Valor cuota',
  colTotal: 'Total',
  colFirstDate: 'Primera fecha',
  colStatus: 'Estado',
  colLink: 'Link de pago',
  colRegistered: 'Registrado',
  hardshipTag: 'Dificultad',
  linkVia: (status: string, channel: string | null) => (channel ? `${status} por ${channel}` : status),
  noLink: 'Sin link',
  view: 'Ver',
  openAndPay: 'Abrir y pagar',

  conversationsTitle: 'Conversaciones',
  conversationsIntro: 'Abre una para ver, en orden, cada herramienta que usó el agente y qué le respondió el sistema.',
  conversationsEmpty: 'Aún no hay llamadas. La primera aparecerá aquí sola, sin recargar.',
  unidentified: 'Sin identificar',
  noSummary: 'Sin resumen aún',
  language: 'Idioma',
  languageName: (code: string): string => (code === 'en' ? 'Inglés' : 'Español'),
  lateReason: 'Motivo de la mora',
  promise: 'Promesa',
  promiseFrom: (date: string) => `, desde el ${date}`,
  hardship: 'Dificultad económica',
  yes: 'Sí',
  no: 'No',
  moodAtEnd: 'Ánimo al final',
  frustration: (share: string) => `, frustración ${share}`,
  lowest: (min: string, end: string) => `; su punto más bajo fue ${min} y cerró en ${end}`,
  toolCalls: 'Herramientas llamadas',
  stepsTitle: 'Lo que hizo el agente, paso a paso',
  listen: 'Escuchar la llamada en ElevenLabs',
  eventsError: (error: string) => `No se pudo cargar la bitácora: ${error}`,
  eventsLoading: 'Cargando la bitácora…',
  eventsEmpty: 'El agente no llamó ninguna herramienta en esta conversación.',

  casesTitle: 'Casos para el equipo',
  casesIntro: 'Disputas, pedidos de llamada con un asesor y solicitudes de no volver a contactar.',
  casesEmpty: 'Sin casos abiertos.',
  colKind: 'Tipo',
  colRef: 'Referencia',
  colDetail: 'Detalle',
  colDate: 'Fecha',
  unverified: 'Sin verificar',

  sentiment: { positive: 'Tranquilo', neutral: 'Neutral', negative: 'Molesto' } as Record<string, string>,
  outcome: {
    promesa: 'Plan registrado',
    disputa: 'Disputa abierta',
    escalado: 'Pasa a asesor',
    opt_out: 'No contactar',
    sin_acuerdo: 'Sin acuerdo',
  } as Record<string, string>,
  tool: {
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
  } as Record<string, string>,
  result: {
    verified: 'verificada',
    not_verified: 'no coincide',
    locked: 'bloqueada por intentos',
    ok: 'ok',
    sent: 'enviado',
    created: 'creado',
    registered: 'registrado',
    stored: 'guardado',
    idempotent_replay: 'repetido, se devolvió el mismo',
    channel_failed: 'falló el canal',
    simulated_payment: 'pagado',
  } as Record<string, string>,
  planStatus: { pending_payment: 'Pendiente de pago', paid: 'Pagado', cancelled: 'Cancelado' } as Record<string, string>,
  linkStatus: { pending: 'Por enviar', sent: 'Enviado', failed: 'Falló el envío', paid: 'Pagado' } as Record<string, string>,
  accountStatus: { active: 'En mora', in_dispute: 'En disputa', current: 'Al día' } as Record<string, string>,
  caseKind: { disputa: 'Disputa', 'llamada de asesor': 'Llamada de asesor', 'no contactar': 'No contactar' } as Record<string, string>,
  caseStatus: { pending: 'Pendiente', open: 'Abierta', activo: 'Activo' } as Record<string, string>,
}

type Messages = typeof es

const en: Messages = {
  appTitle: 'Collections desk',
  docTitle: (fintech) => `${fintech} collections desk`,
  fintechNav: 'Fintech',
  languageGroup: 'Language',
  summaryLabel: 'Summary',
  agentFallback: 'the agent',
  loading: (fintech) => `Loading ${fintech ?? 'the fintech'}…`,
  includeTests: 'Include automated tests',
  offline: (error) => `No connection to the backend (${error}). Retrying every 10 seconds.`,
  updatedAt: (time) => <>Updated at {time}, refreshes on its own</>,
  summary: (s) => (
    <>
      {s.n} {s.n === 1 ? 'customer owes' : 'customers owe'} <strong>{s.overdue}</strong> overdue.{' '}
      {s.plans === 0 ? 'No plans have been agreed by voice yet.' : (
        <>
          <strong>{s.recovered}</strong> committed by voice in {s.plans === 1 ? '1 plan' : `${s.plans} plans`}
          {s.paid > 0 ? `, ${s.paid} already paid` : ''}.
        </>
      )}
      {s.scored > 0 && ' ' + (s.scored === 1
        ? `The analyzed call ended with the customer ${s.calm ? 'calm' : 'upset'}.`
        : `${s.calm === s.scored ? 'All' : `${s.calm} of ${s.scored}`} analyzed calls ended without the customer upset.`)}
    </>
  ),
  policyTitle: 'Credit policy (per product)',
  policy: (p: Record<string, unknown>) => {
    const opts = (p.options ?? {}) as Record<string, unknown>
    if (opts.mode === 'card_preventive') return <>Current card: minimum, full balance, refinance per policy.</>
    if (opts.mode === 'promise') return <>Microloan: pay today or promise within {String(opts.promise_max_days ?? 7)} days.</>
    return (
      <>
        Mode {String(opts.mode ?? 'overdue')}: up to {String(opts.max_installments ?? '—')} installments, minimum{' '}
        {String(opts.min_installment_cop ?? '—')} COP. No discounts.
      </>
    )
  },
  productTabsLabel: 'Product',
  productAll: 'All',
  conversionTitle: 'Commercial conversion',
  conversionOffered: 'Active offers',
  conversionDisbursed: 'Confirmed disbursements',
  conversionRejected: 'Rejected',
  conversionAmount: 'Disbursed amount',
  casesNav: 'Use cases',
  consoleNav: 'Console',
  casesCatalogTitle: 'Case catalog',
  casesCatalogLead: 'Five conversations on the same architecture: client, integration, and agent.',
  casesConsoleCaption: 'Console view after the call',
  casesScreenshotPending: 'Screenshot pending',
  casesAudioPending: 'Recording pending (60–90 s)',
  casesTryLive: 'Try it yourself',
  casesAgentPending: 'Publish the case agent to enable the link.',
  casesTenantNote: (name: string) => `${name} demos; fictional names and data.`,
  footer: (
    <>
      A simulation of the fintech's back office. Every query uses the read-only role <code>cobranza_console</code>,
      and Supabase row-level security limits the data to the selected fintech. The only write is
      "Add random customer", through a function that can only create fictitious customers in that fintech.
    </>
  ),

  liveTitle: 'Live call',
  liveIntro: (agent) =>
    `Talk to ${agent} from here with your microphone. The plan or case shows up in the tables as soon as you hang up. Every call spends ElevenLabs credits.`,
  connecting: (agent) => `Connecting to ${agent}…`,
  ready: 'Ready to call',
  thinking: (agent) => `${agent} is checking…`,
  talking: (agent) => `${agent} is speaking`,
  listening: (agent) => `${agent} is listening`,
  callingAs: 'Calling as',
  nationalId: 'National ID',
  birthDate: 'Born',
  hangUp: 'Hang up',
  mute: 'Mute',
  unmute: 'Unmute',
  callAgent: (agent) => `Call ${agent}`,
  transcriptLabel: (agent) => `Transcript with ${agent}`,
  transcriptLive: (agent) => `Say hello to ${agent}; what you both say shows up here.`,
  transcriptIdle: "The transcript shows up here during the call. To call as a customer, use the button on their card.",
  scrollLatest: 'Go to the latest message',
  micDenied: 'No microphone access. Allow it in the browser to call.',

  customersTitle: 'Customers',
  customersIntro: (agent) =>
    `Fictitious data for testing. To verify yourself with ${agent}, say the last four digits of the national ID and the birth date. ${agent} speaks Spanish and switches to English if you do.`,
  addCustomer: 'Add random customer',
  adding: 'Creating…',
  addFailed: (error) => `Could not create the customer (${error}).`,
  say: (digits, date) => `Say: "${digits}" and "${date}".`,
  callAs: (firstName) => `Call as ${firstName}`,
  optedOut: 'Do not contact',
  overdue: 'Overdue',
  daysPastDue: 'Days past due',
  totalBalance: 'Total balance',
  accountLine: (product, last4) => `${product}, account ending in ${last4}`,
  calls: (n) => (n === 1 ? '1 call' : `${n} calls`),

  plansTitle: 'Registered plans',
  plansIntro: 'Every plan comes from an option computed by the credit policy; the agent cannot invent amounts.',
  plansEmpty: 'No plans yet. Call the agent and accept an option to see the first one appear.',
  colPlan: 'Plan',
  colCustomer: 'Customer',
  colInstallments: 'Installments',
  colInstallment: 'Installment',
  colTotal: 'Total',
  colFirstDate: 'First due date',
  colStatus: 'Status',
  colLink: 'Payment link',
  colRegistered: 'Registered',
  hardshipTag: 'Hardship',
  linkVia: (status, channel) => (channel ? `${status} via ${channel}` : status),
  noLink: 'No link',
  view: 'View',
  openAndPay: 'Open and pay',

  conversationsTitle: 'Conversations',
  conversationsIntro: 'Open one to see, in order, every tool the agent used and what the system answered.',
  conversationsEmpty: 'No calls yet. The first one will show up here on its own, without reloading.',
  unidentified: 'Unidentified',
  noSummary: 'No summary yet',
  language: 'Language',
  languageName: (code) => (code === 'en' ? 'English' : 'Spanish'),
  lateReason: 'Reason for being late',
  promise: 'Promise to pay',
  promiseFrom: (date) => `, starting ${date}`,
  hardship: 'Financial hardship',
  yes: 'Yes',
  no: 'No',
  moodAtEnd: 'Mood at the end',
  frustration: (share) => `, frustration ${share}`,
  lowest: (min, end) => `; its lowest point was ${min} and it ended at ${end}`,
  toolCalls: 'Tool calls',
  stepsTitle: 'What the agent did, step by step',
  listen: 'Listen to the call in ElevenLabs',
  eventsError: (error) => `Could not load the audit log: ${error}`,
  eventsLoading: 'Loading the audit log…',
  eventsEmpty: 'The agent did not call any tool in this conversation.',

  casesTitle: 'Cases for the team',
  casesIntro: 'Disputes, requests for a call from an advisor, and requests not to be contacted again.',
  casesEmpty: 'No open cases.',
  colKind: 'Type',
  colRef: 'Reference',
  colDetail: 'Detail',
  colDate: 'Date',
  unverified: 'Unverified',

  sentiment: { positive: 'Calm', neutral: 'Neutral', negative: 'Upset' },
  outcome: {
    promesa: 'Plan registered',
    disputa: 'Dispute opened',
    escalado: 'Sent to an advisor',
    opt_out: 'Do not contact',
    sin_acuerdo: 'No agreement',
  },
  tool: {
    verify_identity: 'Identity verification',
    get_account_summary: 'Account status lookup',
    get_payment_options: 'Payment options lookup',
    create_payment_plan: 'Plan registration',
    send_payment_link: 'Payment link sent',
    register_dispute: 'Dispute registered',
    register_opt_out: 'Do-not-contact registered',
    request_callback: 'Advisor callback requested',
    post_call_webhook: 'End-of-call summary',
    payment_page: 'Payment on the page',
  },
  result: {
    verified: 'verified',
    not_verified: 'does not match',
    locked: 'locked after too many attempts',
    ok: 'ok',
    sent: 'sent',
    created: 'created',
    registered: 'registered',
    stored: 'stored',
    idempotent_replay: 'repeated, the same one was returned',
    channel_failed: 'channel failed',
    simulated_payment: 'paid',
  },
  planStatus: { pending_payment: 'Awaiting payment', paid: 'Paid', cancelled: 'Cancelled' },
  linkStatus: { pending: 'Not sent yet', sent: 'Sent', failed: 'Sending failed', paid: 'Paid' },
  accountStatus: { active: 'Overdue', in_dispute: 'In dispute', current: 'Up to date' },
  caseKind: { disputa: 'Dispute', 'llamada de asesor': 'Advisor callback', 'no contactar': 'Do not contact' },
  caseStatus: { pending: 'Pending', open: 'Open', activo: 'Active' },
}

const MESSAGES: Record<Lang, Messages> = { es, en }
const FORMATS: Record<Lang, Format> = { es: formatters('es'), en: formatters('en') }
const STORAGE_KEY = 'console-lang'

export function initialLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'es' || stored === 'en') return stored
  return navigator.language.toLowerCase().startsWith('es') ? 'es' : 'en'
}

export const storeLang = (lang: Lang) => localStorage.setItem(STORAGE_KEY, lang)

type I18n = { lang: Lang; setLang: (lang: Lang) => void; t: Messages; f: Format }

export const i18nFor = (lang: Lang, setLang: (lang: Lang) => void): I18n =>
  ({ lang, setLang, t: MESSAGES[lang], f: FORMATS[lang] })

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const value = use(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}

export const summaryFacts = (data: Overview, money: Format['money']): SummaryFacts => {
  const scored = data.conversations.filter((c) => c.sentiment_label)
  return {
    n: data.customers.length,
    overdue: money(data.customers.reduce((sum, c) => sum + c.overdue_amount, 0)),
    plans: data.plans.length,
    recovered: money(data.plans.filter((p) => p.status !== 'cancelled').reduce((sum, p) => sum + p.total_amount, 0)),
    paid: data.plans.filter((p) => p.status === 'paid').length,
    scored: scored.length,
    calm: scored.filter((c) => c.sentiment_label !== 'negative').length,
  }
}
