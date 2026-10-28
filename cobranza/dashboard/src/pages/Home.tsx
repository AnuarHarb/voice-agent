import { Link } from 'react-router'
import { useL } from '../content/l10n'
import { casesOf, industries, useCases } from '../content/useCases'
import { CaseCard } from '../site/parts'

export default function Home() {
  const { l } = useL()
  const featured = useCases.filter((c) => c.demo).slice(0, 3)
  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <p className="mono-label">Inmercity / Agents</p>
        <h1 id="hero-title" className="display-xl">{l({ es: 'Agentes que hacen el trabajo.', en: 'Agents that do the work.' })}</h1>
        <p className="body-lg">{l({
          es: 'Agentes de voz que verifican identidad, consultan sistemas reales, aplican las reglas del negocio y dejan trazabilidad completa. Conversaciones que terminan en un resultado, no en un ticket.',
          en: 'Voice agents that verify identity, query real systems, apply business rules and leave a complete audit trail. Conversations that end in an outcome, not a ticket.',
        })}</p>
        <div className="actions">
          <Link className="btn" to="/casos">{l({ es: 'Ver casos de uso', en: 'See use cases' })}</Link>
          <Link className="btn btn-quiet" to="/como-funciona">{l({ es: 'Cómo funciona un agente', en: 'How an agent works' })}</Link>
        </div>
      </section>

      <section className="section" aria-labelledby="industrias">
        <header>
          <h2 id="industrias">{l({ es: 'Una arquitectura, varias industrias', en: 'One architecture, several industries' })}</h2>
          <p className="muted">{l({
            es: 'El mismo patrón sirve en cobranza, salud, retail, telecomunicaciones y ventas.',
            en: 'The same pattern works in collections, healthcare, retail, telecom and sales.',
          })}</p>
        </header>
        <div className="grid stagger">
          {industries.map((i) => (
            <article className="card" key={i.id}>
              <h3><Link className="card-link" to={`/casos?industria=${i.id}`}>{l(i.name)}</Link></h3>
              <p>{l(i.summary)}</p>
              <p className="mono-label">{casesOf(i.id).length} {casesOf(i.id).length === 1 ? l({ es: 'caso', en: 'case' }) : l({ es: 'casos', en: 'cases' })}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="demos">
        <header>
          <h2 id="demos">{l({ es: 'Demos que puedes llamar hoy', en: 'Demos you can call today' })}</h2>
          <p className="muted">{l({
            es: 'Cinco agentes financieros en operación de demo, conectados a una API real con datos ficticios.',
            en: 'Five financial agents running as demos, connected to a real API with fictional data.',
          })}</p>
        </header>
        <div className="grid stagger">{featured.map((c) => <CaseCard key={c.id} item={c} />)}</div>
      </section>

      <section className="section" aria-labelledby="principios">
        <header><h2 id="principios">{l({ es: 'Cómo los construimos', en: 'How we build them' })}</h2></header>
        <div className="grid">
          {[
            { t: { es: 'El modelo conversa; el código decide', en: 'The model talks; code decides' }, d: { es: 'Identidad, montos y cumplimiento viven en la API, no en el prompt.', en: 'Identity, amounts and compliance live in the API, not in the prompt.' } },
            { t: { es: 'Humanos al mando', en: 'Humans stay in control' }, d: { es: 'Escalamiento, opt-out y bitácora de cada llamada.', en: 'Escalation, opt-out and a log for every call.' } },
            { t: { es: 'Hecho para producción', en: 'Built for production' }, d: { es: 'Aislamiento por cliente con RLS, pruebas automatizadas y agentes como código.', en: 'Per-client isolation with RLS, automated tests and agents as code.' } },
          ].map((x) => (
            <article className="card" key={x.t.es}><h3>{l(x.t)}</h3><p>{l(x.d)}</p></article>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="cierre">
        <header>
          <h2 id="cierre">{l({ es: 'From idea to intelligent system.', en: 'From idea to intelligent system.' })}</h2>
          <p className="muted">{l({
            es: 'Descubrimiento, prototipo, piloto y producción. Cuéntanos qué conversación quieres automatizar.',
            en: 'Discovery, prototype, pilot and production. Tell us which conversation you want to automate.',
          })}</p>
        </header>
        <div className="hero"><div className="actions" style={{ paddingTop: 0 }}>
          <Link className="btn" to="/integracion">{l({ es: 'Ver cómo se integra', en: 'See how it integrates' })}</Link>
        </div></div>
      </section>
    </>
  )
}
