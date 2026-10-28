import { useEffect, useMemo, useState } from 'react'
import { api, type Customer, type DemoCustomer, type Tenant } from '../api'
import { LiveCall } from '../components/LiveCall'
import { useL } from '../content/l10n'
import { industryById, useCases, type L10n, type UseCase } from '../content/useCases'
import { useI18n } from '../i18n'
import { useLiveCall } from '../live'

type Caller = { key: string; name: string; id: string; birth: string; hint?: L10n; customer: Customer | null }

const demoCases = useCases.filter((c) => c.demo)

/** Agent id registered for a demo. The first Avanza agent still runs under the label "production". */
function agentFor(tenants: Tenant[], demo: NonNullable<UseCase['demo']>): string | undefined {
  const agents = tenants.find((t) => t.id === demo.tenant)?.agents ?? []
  return (
    agents.find((a) => a.label === demo.agentLabel) ??
    (demo.agentLabel === 'libre_inversion_mora' ? agents.find((a) => a.label === 'production') : undefined)
  )?.agent_id
}

/** One agent, one button: pick an agent, see what to say, press call. `lockedId` pins a single agent. */
export function QuickDemo({ lockedId }: { lockedId?: string }) {
  const { l } = useL()
  const { f } = useI18n()
  const [selectedId, setSelectedId] = useState(lockedId ?? demoCases[0].id)
  const [callerKey, setCallerKey] = useState('')
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [finance, setFinance] = useState<Customer[]>([])
  const [vertical, setVertical] = useState<DemoCustomer[]>([])
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const item: UseCase | undefined = demoCases.find((c) => c.id === (lockedId ?? selectedId))
  const demo = item?.demo

  useEffect(() => {
    api.tenants().then(setTenants, (e: Error) => setError(e.message))
    api.overview('avanza', false).then((o) => setFinance(o.customers), () => undefined)
    api.demoCustomers('demos').then(setVertical, () => undefined)
  }, [])

  // Start on the first agent that is actually reachable.
  useEffect(() => {
    if (lockedId || tenants.length === 0) return
    const current = demoCases.find((c) => c.id === selectedId)
    if (current && agentFor(tenants, current.demo!)) return
    const first = demoCases.find((c) => agentFor(tenants, c.demo!))
    if (first) setSelectedId(first.id)
  }, [tenants, lockedId, selectedId])

  const callers: Caller[] = useMemo(() => {
    if (!demo) return []
    if (demo.productCode) {
      return finance
        .filter((c) => c.product_code === demo.productCode)
        .filter((c) => (['oferta_cupo', 'tarjeta_preventiva'].includes(demo.agentLabel) ? c.days_past_due === 0 : true))
        .map((c) => ({ key: c.account_id, name: c.full_name, id: c.national_id, birth: c.birth_date, customer: c }))
    }
    return (demo.callers ?? []).flatMap((hint) => {
      const c = vertical.find((v) => v.id === hint.id)
      return c ? [{ key: c.id, name: c.full_name, id: c.national_id, birth: c.birth_date, hint: hint.hint, customer: null }] : []
    })
  }, [demo, finance, vertical])

  const caller = callers.find((c) => c.key === callerKey) ?? callers[0]
  const agentId = demo ? agentFor(tenants, demo) : undefined
  const call = useLiveCall(agentId, () => undefined)
  const inCall = call.status === 'connected' || call.status === 'connecting'
  const tools = call.lines.filter((x) => x.kind === 'tool')

  const copy = async () => {
    if (!caller) return
    const text = `${caller.id.slice(-4)} / ${caller.birth}`
    await navigator.clipboard?.writeText(text).catch(() => undefined)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!item || !demo) return null

  return (
    <div className="quick">
      {!lockedId && (
        <fieldset className="chips" disabled={inCall}>
          <legend className="mono-label">{l({ es: '1. Elige un agente', en: '1. Pick an agent' })}</legend>
          {demoCases.map((c) => {
            const live = Boolean(agentFor(tenants, c.demo!))
            return (
              <label key={c.id} className={`chip${c.id === item.id ? ' on' : ''}${live ? '' : ' off'}`}>
                <input type="radio" name="agent" value={c.id} checked={c.id === item.id} disabled={!live}
                  onChange={() => { setSelectedId(c.id); setCallerKey('') }} />
                <strong>{c.demo!.agentName}</strong>
                <span>{l(industryById(c.industry)!.name)}{live ? '' : ` · ${l({ es: 'Próximamente', en: 'Coming soon' })}`}</span>
              </label>
            )
          })}
        </fieldset>
      )}

      <div className="demo-grid">
        <section className="frame" aria-label={l({ es: 'Llamada', en: 'Call' })}>
          <span className="mono-label">DEMO / {demo.agentLabel.toUpperCase()} / {inCall ? 'ACTIVE' : 'READY'}</span>
          <LiveCall call={call} tenant={demo.tenant} agentName={demo.agentName} embedded />
          {error && <p role="alert" style={{ color: 'var(--warn)', padding: 'var(--space-4)' }}>{error}</p>}
        </section>

        <aside className="frame" aria-labelledby="say-title">
          <span className="mono-label" id="say-title">{l({ es: '2. Qué decir', en: '2. What to say' })}</span>
          <div className="say">
            <p><strong>{l(item.title)}</strong></p>
            {demo.guide && <p>{l(demo.guide)}</p>}
            {caller && (
              <>
                {callers.length > 1 && (
                  <label className="field">
                    <span className="muted">{l({ es: 'Cliente de prueba', en: 'Test customer' })}</span>
                    <select value={caller.key} onChange={(e) => setCallerKey(e.target.value)} disabled={inCall}>
                      {callers.map((c) => <option key={c.key} value={c.key}>{c.name}</option>)}
                    </select>
                  </label>
                )}
                <dl className="data">
                  <div><dt>{l({ es: 'Últimos 4 de la cédula', en: 'Last 4 of the ID' })}</dt><dd>{caller.id.slice(-4)}</dd></div>
                  <div><dt>{l({ es: 'Nacimiento', en: 'Birth date' })}</dt><dd>{f.longDate(caller.birth)}</dd></div>
                </dl>
                {caller.hint && <p className="muted">{l(caller.hint)}</p>}
                <button type="button" className="btn btn-quiet" onClick={copy}>
                  {copied ? l({ es: 'Copiado', en: 'Copied' }) : l({ es: 'Copiar datos', en: 'Copy details' })}
                </button>
              </>
            )}
            <button type="button" className="btn call" disabled={inCall || !agentId} onClick={() => call.start(caller?.customer ?? null)}>
              {l({ es: '3. Llamar a', en: '3. Call' })} {demo.agentName}
            </button>
          </div>
          <span className="mono-label" id="xray-title">X-RAY / TOOL CALLS</span>
          {tools.length === 0 ? (
            <p className="xray muted">{l({
              es: 'Aquí aparece cada herramienta que el agente llama.',
              en: 'Every tool the agent calls shows up here.',
            })}</p>
          ) : (
            <ol className="xray" role="list" aria-labelledby="xray-title">
              {tools.map((x) => x.kind === 'tool' && (
                <li key={x.id} className={x.ok === null ? 'pending' : x.ok ? '' : 'failed'}>
                  <span className="mono-label" style={{ color: 'var(--electric-iris)' }}>TOOL / {x.tool}</span>
                  <span>{x.ok === null ? l({ es: 'En curso', en: 'Running' }) : x.ok ? l({ es: 'Respondió', en: 'Returned' }) : 'Error'}</span>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </div>
  )
}
