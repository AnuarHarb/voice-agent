import { Link } from 'react-router'
import { useL } from '../content/l10n'
import { QuickDemo } from '../site/QuickDemo'

export default function Home() {
  const { l } = useL()
  const explore = [
    { to: '/casos', t: { es: 'Casos de uso', en: 'Use cases' }, d: { es: 'Finanzas, salud, retail, telecomunicaciones e inmobiliaria.', en: 'Finance, healthcare, retail, telecom and real estate.' } },
    { to: '/como-funciona', t: { es: 'Cómo funciona', en: 'How it works' }, d: { es: 'Qué hace el modelo y qué decide el código.', en: 'What the model does and what code decides.' } },
    { to: '/integracion', t: { es: 'Integración', en: 'Integration' }, d: { es: 'Cómo se conecta con tus sistemas.', en: 'How it connects to your systems.' } },
  ]
  return (
    <>
      <section className="hero compact" aria-labelledby="hero-title">
        <p className="mono-label">Inmercity / Agents</p>
        <h1 id="hero-title" className="display-xl">{l({ es: 'Agentes de voz que hacen el trabajo.', en: 'Voice agents that do the work.' })}</h1>
        <p className="body-lg">{l({
          es: 'Verifican identidad, consultan sistemas y cierran la gestión en la misma llamada. Pruébalo ahora.',
          en: 'They verify identity, query systems and finish the task in the same call. Try it now.',
        })}</p>
      </section>

      <section className="section" id="probar" aria-label={l({ es: 'Probar un agente', en: 'Try an agent' })}>
        <QuickDemo />
      </section>

      <section className="section" aria-labelledby="explorar">
        <header><h2 id="explorar">{l({ es: 'Explora más', en: 'Explore more' })}</h2></header>
        <div className="grid">
          {explore.map((x) => (
            <article className="card" key={x.to}>
              <h3><Link className="card-link" to={x.to}>{l(x.t)}</Link></h3>
              <p>{l(x.d)}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
