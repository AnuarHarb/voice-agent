import { useCallback, useEffect, useEffectEvent, useState } from 'react'
import { api, type Overview, type Tenant } from './api'
import { Cases } from './components/Cases'
import { Conversations } from './components/Conversations'
import { Customers } from './components/Customers'
import { LiveCall } from './components/LiveCall'
import { Plans } from './components/Plans'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { summaryFacts, useI18n, type Lang } from './i18n'
import { useLiveCall } from './live'

const REFRESH_MS = 10_000
const AGENT_NAME: Record<string, string> = { avanza: 'Sofía', nexo: 'Horacio' }
const LANGUAGES: { id: Lang; name: string }[] = [{ id: 'es', name: 'Español' }, { id: 'en', name: 'English' }]

const tenantFromUrl = () => new URLSearchParams(location.search).get('fintech') ?? 'avanza'

function Summary({ data }: { data: Overview }) {
  const { t, f } = useI18n()
  return <p className="lede">{t.summary(summaryFacts(data, f.money))}</p>
}

function Policy({ data }: { data: Overview }) {
  const { t, f } = useI18n()
  if (!data.policy) return null
  return (
    <section className="block policy" aria-labelledby="politica">
      <h2 id="politica">{t.policyTitle}</h2>
      <p>{t.policy(data.policy, f.money)}</p>
    </section>
  )
}

function LanguageSwitch() {
  const { lang, setLang, t } = useI18n()
  return (
    <div className="lang-switch" role="group" aria-label={t.languageGroup}>
      {LANGUAGES.map((l) => (
        <button key={l.id} type="button" lang={l.id} aria-pressed={l.id === lang} onClick={() => setLang(l.id)}>
          {l.name}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const { t, f } = useI18n()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenant, setTenant] = useState(tenantFromUrl)
  const [includeTests, setIncludeTests] = useState(false)
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.tenants().then(setTenants, (e: Error) => setError(e.message))
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
    if (current) document.title = t.docTitle(current.name)
  }, [current, t])

  const switchTenant = (id: string) => {
    if (id === tenant) return
    call.reset()
    setTenant(id)
  }

  const onPop = useEffectEvent(() => switchTenant(tenantFromUrl()))
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
    <div className="app" data-tenant={tenant}>
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
          <LanguageSwitch />
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
            {current?.agent_id && <LiveCall call={call} tenant={tenant} agentName={agentName} />}
            <Customers
              tenant={tenant}
              customers={shown.customers}
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
      </main>

      <footer className="colophon">
        <p>{t.footer}</p>
      </footer>
    </div>
  )
}
