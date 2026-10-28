import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type Customer, type Tenant } from '../api'
import { LiveCall } from '../components/LiveCall'
import { useL } from '../content/l10n'
import { useCaseById } from '../content/useCases'
import { useI18n } from '../i18n'
import { useLiveCall } from '../live'

export default function Demo({ caseId, compact = false }: { caseId?: string; compact?: boolean }) {
  const { l } = useL()
  const { f } = useI18n()
  const params = useParams()
  const id = caseId ?? params.id ?? ''
  const item = useCaseById(id)
  const demo = item?.demo
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!demo) return
    api.tenants().then(setTenants, (e: Error) => setError(e.message))
    api.overview(demo.tenant, false).then(
      (o) => setCustomers(o.customers.filter((c) => c.product_code === demo.productCode)),
      (e: Error) => setError(e.message),
    )
  }, [demo])

  const agentId = tenants.find((t) => t.id === demo?.tenant)?.agents?.find((a) => a.label === demo?.agentLabel)?.agent_id
  const call = useLiveCall(agentId, () => undefined)
  const inCall = call.status === 'connected' || call.status === 'connecting'
  const tools = call.lines.filter((x) => x.kind === 'tool')
  const forCommercial = demo?.agentLabel === 'oferta_cupo'
  const callers = customers.filter((c) => (forCommercial ? c.days_past_due === 0 : demo?.agentLabel === 'tarjeta_preventiva' ? c.days_past_due === 0 : true))

  if (!item || !demo) {
    return (
      <section className="section">
        <h1>{l({ es: 'Este caso aún no tiene demo', en: 'This case has no demo yet' })}</h1>
        <Link to="/casos">{l({ es: 'Volver a los casos', en: 'Back to use cases' })}</Link>
      </section>
    )
  }

  return (
    <section className="section" aria-labelledby="demo-title">
      <header hidden={compact}>
        <p className="mono-label"><Link to={`/casos/${item.id}`}>{l(item.title)}</Link> / DEMO</p>
        <h1 id="demo-title" className="display">{l({ es: 'Llama al agente', en: 'Call the agent' })}</h1>
        <p className="body-lg">{l({
          es: 'Elige un cliente de prueba, presiona llamar y responde con los datos que ves. Se usa tu micrófono.',
          en: 'Pick a test customer, press call and answer with the data you see. Your microphone is used.',
        })}</p>
        {error && <p role="alert" style={{ color: 'var(--warn)' }}>{error}</p>}
      </header>

      <div className="demo-grid">
        <div className="frame">
          <span className="mono-label">DEMO / {demo.agentLabel.toUpperCase()} / {inCall ? 'ACTIVE' : 'READY'}</span>
          <LiveCall call={call} tenant={demo.tenant} agentName={demo.agentName} />
        </div>
        <aside className="frame" aria-labelledby="xray-title">
          <span className="mono-label" id="xray-title">X-RAY / TOOL CALLS</span>
          {tools.length === 0 ? (
            <p className="xray muted">{l({
              es: 'Aquí aparece cada herramienta que el agente llama durante la llamada.',
              en: 'Every tool the agent calls during the call shows up here.',
            })}</p>
          ) : (
            <ol className="xray" role="list">
              {tools.map((x) => x.kind === 'tool' && (
                <li key={x.id} className={x.ok === null ? 'pending' : x.ok ? '' : 'failed'}>
                  <span className="mono-label" style={{ color: 'var(--electric-iris)' }}>TOOL / {x.tool}</span>
                  <span>{x.ok === null ? l({ es: 'En curso', en: 'Running' }) : x.ok ? l({ es: 'Respondió', en: 'Returned' }) : l({ es: 'Error', en: 'Error' })}</span>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>

      <section aria-labelledby="clientes">
        <h2 id="clientes">{l({ es: 'Clientes de prueba', en: 'Test customers' })}</h2>
        <ul className="callers" role="list">
          {callers.map((c) => (
            <li key={c.account_id}>
              <span>
                <strong>{c.full_name}</strong>
                <span className="muted"> · {l({ es: 'cédula', en: 'ID' })} {c.national_id} · {f.longDate(c.birth_date)}</span>
              </span>
              <button type="button" className="btn" disabled={inCall || !agentId} onClick={() => call.start(c)}>
                {l({ es: 'Llamar como este cliente', en: 'Call as this customer' })}
              </button>
            </li>
          ))}
        </ul>
        {callers.length === 0 && <p className="muted">{l({ es: 'Cargando clientes de prueba.', en: 'Loading test customers.' })}</p>}
      </section>
    </section>
  )
}
