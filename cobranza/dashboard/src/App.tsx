import { useCallback, useEffect, useState } from 'react'
import { api, type Overview, type Tenant } from './api'
import { Cases } from './components/Cases'
import { Conversations } from './components/Conversations'
import { Customers } from './components/Customers'
import { LiveCall } from './components/LiveCall'
import { Plans } from './components/Plans'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { clock, money } from './format'
import { useLiveCall } from './live'

const REFRESH_MS = 10_000
const AGENT_NAME: Record<string, string> = { avanza: 'Sofía', nexo: 'Horacio' }

const tenantFromUrl = () => new URLSearchParams(location.search).get('fintech') ?? 'avanza'

function Summary({ data }: { data: Overview }) {
  const overdue = data.customers.reduce((sum, c) => sum + c.overdue_amount, 0)
  const recovered = data.plans.filter((p) => p.status !== 'cancelled').reduce((sum, p) => sum + p.total_amount, 0)
  const paid = data.plans.filter((p) => p.status === 'paid').length
  const n = data.customers.length
  const scored = data.conversations.filter((c) => c.sentiment_label)
  const calm = scored.filter((c) => c.sentiment_label !== 'negative').length
  return (
    <p className="lede">
      {n} {n === 1 ? 'cliente debe' : 'clientes deben'} <strong>{money(overdue)}</strong> en mora.{' '}
      {data.plans.length === 0 ? (
        'Todavía no hay planes acordados por voz.'
      ) : (
        <>
          Por voz se han comprometido <strong>{money(recovered)}</strong> en{' '}
          {data.plans.length === 1 ? '1 plan' : `${data.plans.length} planes`}
          {paid > 0 ? `, ${paid} ya ${paid === 1 ? 'pagado' : 'pagados'}` : ''}.
        </>
      )}
      {scored.length > 0 && (
        <>
          {' '}
          {scored.length === 1
            ? `La llamada analizada terminó con el cliente ${calm ? 'tranquilo' : 'molesto'}.`
            : `${calm === scored.length ? 'Todas las' : `${calm} de ${scored.length}`} llamadas analizadas terminaron sin el cliente molesto.`}
        </>
      )}
    </p>
  )
}

function Policy({ data }: { data: Overview }) {
  const p = data.policy
  if (!p) return null
  return (
    <section className="block policy" aria-labelledby="politica">
      <h2 id="politica">Política de crédito</h2>
      <p>
        Hasta {p.max_installments} {p.max_installments === 1 ? 'cuota' : 'cuotas'} de mínimo {money(p.min_installment_cop)},
        con el primer pago en los próximos {p.first_payment_max_days} días.{' '}
        {p.hardship_enabled
          ? `A quien cuenta una dificultad económica se le puede ofrecer ${p.hardship_installments} cuotas, empezando en ${p.hardship_grace_days} días.`
          : 'No hay opción especial por dificultad económica: esos casos pasan a un asesor.'}
        {' '}Nunca hay descuentos.
      </p>
    </section>
  )
}

export default function App() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenant, setTenant] = useState(tenantFromUrl)
  const [includeTests, setIncludeTests] = useState(false)
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.tenants().then(setTenants, (e: Error) => setError(e.message))
    const onPop = () => setTenant(tenantFromUrl())
    addEventListener('popstate', onPop)
    return () => removeEventListener('popstate', onPop)
  }, [])

  const load = useCallback(
    (signal?: AbortSignal) =>
      api.overview(tenant, includeTests, signal).then(
        (next) => { setData(next); setError('') },
        (e: Error) => { if (e.name !== 'AbortError') setError(e.message) },
      ),
    [tenant, includeTests],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    const timer = setInterval(() => document.visibilityState === 'visible' && load(), REFRESH_MS)
    return () => { controller.abort(); clearInterval(timer) }
  }, [load])

  const current = tenants.find((t) => t.id === tenant)
  const agentName = AGENT_NAME[tenant] ?? 'el agente'
  const shown = data?.tenant.id === tenant ? data : null

  const call = useLiveCall(current?.agent_id ?? undefined, () => {
    load()
    setTimeout(() => load(), 4000)
  })
  const inCall = call.status === 'connected' || call.status === 'connecting'
  const showLive = () => document.getElementById('en-vivo')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const callAs = (customer: Parameters<typeof call.start>[0]) => {
    showLive()
    call.start(customer)
  }

  useEffect(() => {
    if (current) document.title = `Mesa de cobranza de ${current.name}`
  }, [current])

  const choose = (id: string) => (event: React.MouseEvent) => {
    event.preventDefault()
    if (inCall) call.end()
    history.pushState(null, '', `?fintech=${id}`)
    setTenant(id)
  }

  return (
    <div className="app" data-tenant={tenant}>
      <header className="masthead">
        <div className="brand">
          <p>{current?.name ?? ' '}</p>
          <h1>Mesa de cobranza</h1>
        </div>
        <nav aria-label="Fintech">
          <ul role="list">
            {tenants.map((t) => (
              <li key={t.id}>
                <a href={`?fintech=${t.id}`} onClick={choose(t.id)} aria-current={t.id === tenant ? 'page' : undefined}>
                  {t.name}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main>
        <section className="intro" aria-label="Resumen">
          {shown ? (
            <Summary data={shown} />
          ) : (
            <p className="lede"><ShimmeringText text={`Cargando ${current?.name ?? 'la fintech'}…`} /></p>
          )}
          <div className="controls">
            <label>
              <input type="checkbox" checked={includeTests} onChange={(e) => setIncludeTests(e.target.checked)} />
              Incluir pruebas automáticas
            </label>
            <p className="muted" aria-live="polite">
              {error
                ? <span className="error">Sin conexión con el backend ({error}). Reintentando cada 10 segundos.</span>
                : shown && <>Actualizado a las <time dateTime={shown.generated_at}>{clock(shown.generated_at)}</time>, se refresca solo</>}
            </p>
          </div>
        </section>

        {shown && (
          <>
            {current?.agent_id && <LiveCall call={call} tenant={tenant} agentName={agentName} />}
            <Customers customers={shown.customers} agentName={agentName} onCall={inCall ? undefined : callAs} />
            <Plans plans={shown.plans} />
            <Conversations tenant={tenant} conversations={shown.conversations} />
            <Cases cases={shown.cases} />
            <Policy data={shown} />
          </>
        )}
      </main>

      <footer className="colophon">
        <p>
          Simulación del back office de la fintech. Solo lectura: cada consulta usa el rol <code>cobranza_console</code>,
          y la seguridad por fila de Supabase limita los datos a la fintech elegida.
        </p>
      </footer>
    </div>
  )
}
