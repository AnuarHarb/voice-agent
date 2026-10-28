import { Link, useSearchParams } from 'react-router'
import { useL } from '../content/l10n'
import { industries, useCases } from '../content/useCases'
import { CaseCard } from '../site/parts'

export default function UseCases() {
  const { l } = useL()
  const [params] = useSearchParams()
  const active = params.get('industria') ?? 'todas'
  const shown = active === 'todas' ? useCases : useCases.filter((c) => c.industry === active)
  return (
    <section className="section" aria-labelledby="casos-title">
      <header>
        <p className="mono-label">Inmercity / Agents</p>
        <h1 id="casos-title" className="display">{l({ es: 'Casos de uso', en: 'Use cases' })}</h1>
        <p className="body-lg">{l({
          es: 'Los marcados como demo en vivo se pueden llamar desde el navegador. Los marcados como concepto muestran el diseño, aún sin operar.',
          en: 'Cases marked live demo can be called from the browser. Concept cases show the design before it runs.',
        })}</p>
      </header>
      <nav className="filters" aria-label={l({ es: 'Filtrar por industria', en: 'Filter by industry' })}>
        <ul role="list">
          <li><Link to="/casos" aria-current={active === 'todas'}>{l({ es: 'Todas', en: 'All' })}</Link></li>
          {industries.map((i) => (
            <li key={i.id}><Link to={`/casos?industria=${i.id}`} aria-current={active === i.id}>{l(i.name)}</Link></li>
          ))}
        </ul>
      </nav>
      <div className="grid stagger">{shown.map((c) => <CaseCard key={c.id} item={c} />)}</div>
    </section>
  )
}
