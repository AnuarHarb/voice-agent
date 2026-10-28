import { Link, useParams } from 'react-router'
import { useL } from '../content/l10n'
import { industryById, useCaseById } from '../content/useCases'
import { CaseTag, Script } from '../site/parts'

export default function CaseDetail() {
  const { l, list } = useL()
  const { id = '' } = useParams()
  const item = useCaseById(id)
  if (!item) {
    return (
      <section className="section">
        <h1>{l({ es: 'Caso no encontrado', en: 'Case not found' })}</h1>
        <Link to="/casos">{l({ es: 'Volver a los casos', en: 'Back to use cases' })}</Link>
      </section>
    )
  }
  return (
    <article className="section" aria-labelledby="caso-title">
      <header>
        <p className="mono-label">
          <Link to="/casos">{l({ es: 'Casos', en: 'Cases' })}</Link> / {l(industryById(item.industry)!.name)}
        </p>
        <h1 id="caso-title" className="display">{l(item.title)}</h1>
        <p className="body-lg">{l(item.problem)}</p>
        <p><CaseTag item={item} /></p>
        {item.demo && (
          <p><Link className="btn" to={`/demo/${item.id}`}>{l({ es: 'Probar el demo', en: 'Try the demo' })}</Link></p>
        )}
      </header>
      <div className="detail">
        <section aria-labelledby="flujo">
          <h2 id="flujo">{l({ es: 'Qué hace el agente', en: 'What the agent does' })}</h2>
          <ol className="steps" role="list">{list(item.flow).map((s) => <li key={s}>{s}</li>)}</ol>
        </section>
        <section aria-labelledby="guardrails">
          <h2 id="guardrails">{l({ es: 'Reglas que no se rompen', en: 'Rules that hold' })}</h2>
          <ul className="checks" role="list">{list(item.guardrails).map((s) => <li key={s}>{s}</li>)}</ul>
          <p className="mono-label">{l({ es: 'Métrica que mueve', en: 'Metric it moves' })}</p>
          <p>{l(item.metric)}</p>
        </section>
        <section aria-labelledby="tools">
          <h2 id="tools">{l({ es: 'Herramientas', en: 'Tools' })}</h2>
          <p className="muted">{item.demo
            ? l({ es: 'Funciones reales de la API que el agente puede llamar.', en: 'Real API functions the agent can call.' })
            : l({ es: 'Funciones previstas para este caso.', en: 'Planned functions for this case.' })}</p>
          <div className="tools">{item.tools.map((t) => <code key={t}>{t}</code>)}</div>
        </section>
        <section aria-labelledby="ejemplo">
          <h2 id="ejemplo">{l({ es: 'Fragmento de conversación', en: 'Conversation excerpt' })}</h2>
          <Script lines={item.script} />
        </section>
      </div>
    </article>
  )
}
