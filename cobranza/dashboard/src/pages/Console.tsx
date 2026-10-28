import { useCallback, useEffect, useEffectEvent, useState } from 'react'
import { api, type Overview, type Tenant } from '../api'
import { Cases } from '../components/Cases'
import { Conversion } from '../components/Conversion'
import { Conversations } from '../components/Conversations'
import { Customers } from '../components/Customers'
import { LiveCall } from '../components/LiveCall'
import { Plans } from '../components/Plans'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { summaryFacts, useI18n } from '../i18n'
import { useLiveCall } from '../live'

const REFRESH_MS = 10_000
const AGENT_NAME: Record<string, string> = { avanza: 'Sofía', nexo: 'Horacio' }

const tenantFromUrl = () => new URLSearchParams(location.search).get('fintech') ?? 'avanza'
const productFromUrl = () => new URLSearchParams(location.search).get('product') ?? 'all'

function Summary({ data }: { data: Overview }) {
  const { t, f } = useI18n()
  return <p className="lede">{t.summary(summaryFacts(data, f.money))}</p>
}

function Policy({ data }: { data: Overview }) {
  const { t } = useI18n()
  if (!data.policy) return null
  return (
    <section className="block policy" aria-labelledby="politica">
      <h2 id="politica">{t.policyTitle}</h2>
      <p>{t.policy(data.policy)}</p>
    </section>
  )
}

export default function Console() {
  const { t, f } = useI18n()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenant, setTenant] = useState(tenantFromUrl)
  const [product, setProduct] = useState(productFromUrl)
  const [includeTests, setIncludeTests] = useState(false)
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    // The demos tenant has no collections data: its agents are exercised from /demo.
    api.tenants().then((list) => setTenants(list.filter((t) => t.id !== 'demos')), (e: Error) => setError(e.message))
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
  const agentName = AGENT_NAME[tenant] ?? t.agentFallback
  const shown = data?.tenant.id === tenant ? data : null
  const agents = current?.agents ?? []
  const liveAgentId = agents.find((a) => a.label === product)?.agent_id
    ?? agents.find((a) => a.label === 'libre_inversion_mora')?.agent_id
    ?? current?.agent_id
  const filterByProduct = <T extends { product_code?: string }>(rows: T[]) =>
    product === 'all' ? rows : rows.filter((r) => r.product_code === product)

  const call = useLiveCall(liveAgentId ?? undefined, () => {
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
    if (current) document.title = t.docTitle(current.name)
  }, [current, t])

  const switchTenant = (id: string) => {
    if (id === tenant) return
    call.reset()
    setTenant(id)
  }

  const onPop = useEffectEvent(() => {
    switchTenant(tenantFromUrl())
    setProduct(productFromUrl())
  })
  useEffect(() => {
    const listener = () => onPop()
    addEventListener('popstate', listener)
    return () => removeEventListener('popstate', listener)
  }, [])

  const choose = (id: string) => (event: React.MouseEvent) => {
    event.preventDefault()
    if (id === tenant) return
    history.pushState(null, '', `?fintech=${id}`)
    switchTenant(id)
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <p>{current?.name ?? ' '}</p>
          <h1>{t.appTitle}</h1>
        </div>
        <div className="masthead-tools">
          <nav aria-label={t.fintechNav}>
            <ul role="list">
              {tenants.map((item) => (
                <li key={item.id}>
                  <a href={`?fintech=${item.id}`} onClick={choose(item.id)} aria-current={item.id === tenant ? 'page' : undefined}>
                    {item.name}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main>
        <section className="intro" aria-label={t.summaryLabel}>
          {shown ? (
            <Summary data={shown} />
          ) : (
            <p className="lede"><ShimmeringText text={t.loading(current?.name)} /></p>
          )}
          <div className="controls">
            <label>
              <input type="checkbox" checked={includeTests} onChange={(e) => setIncludeTests(e.target.checked)} />
              {t.includeTests}
            </label>
            <p className="muted" aria-live="polite">
              {error
                ? <span className="error">{t.offline(error)}</span>
                : shown && t.updatedAt(<time dateTime={shown.generated_at}>{f.clock(shown.generated_at)}</time>)}
            </p>
          </div>
        </section>

        {shown && (
          <>
            {shown.products.length > 0 && (
              <nav className="product-tabs" aria-label={t.productTabsLabel}>
                <ul role="list">
                  <li>
                    <button type="button" aria-pressed={product === 'all'} onClick={() => setProduct('all')}>
                      {t.productAll}
                    </button>
                  </li>
                  {shown.products.map((p) => (
                    <li key={p.product_code}>
                      <button type="button" aria-pressed={product === p.product_code}
                        onClick={() => setProduct(p.product_code)}>
                        {p.display_name}
                      </button>
                    </li>
                  ))}
                  <li>
                    <button type="button" aria-pressed={product === 'conversion'}
                      onClick={() => setProduct('conversion')}>
                      {t.conversionTitle}
                    </button>
                  </li>
                </ul>
              </nav>
            )}
            {product === 'conversion' && shown.conversion && <Conversion stats={shown.conversion} />}
            {product !== 'conversion' && liveAgentId && (
              <LiveCall call={call} tenant={tenant} agentName={agentName} />
            )}
            {product !== 'conversion' && (
              <>
                <Customers
                  tenant={tenant}
                  customers={filterByProduct(shown.customers)}
                  agentName={agentName}
                  onCall={inCall ? undefined : callAs}
                  onAdded={load}
                />
                <Plans plans={shown.plans} />
                <Conversations tenant={tenant} conversations={shown.conversations} />
                <Cases cases={shown.cases} />
                <Policy data={shown} />
              </>
            )}
          </>
        )}
      </main>

      <footer className="colophon">
        <p>{t.footer}</p>
      </footer>
    </div>
  )
}
