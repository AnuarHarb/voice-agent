import { Link } from 'react-router'
import { anatomy } from '../content/explain'
import { useL } from '../content/l10n'
import { useCaseById } from '../content/useCases'
import { Script } from '../site/parts'

export default function HowItWorks() {
  const { l } = useL()
  const example = useCaseById('libre-inversion-mora')!
  return (
    <>
      <section className="section" aria-labelledby="como-title">
        <header>
          <p className="mono-label">Inmercity / Agents</p>
          <h1 id="como-title" className="display">{l({ es: 'Cómo funciona un agente de voz', en: 'How a voice agent works' })}</h1>
          <p className="body-lg">{l({
            es: 'Un agente útil no es solo un modelo que habla. Son seis piezas, y las más importantes no son inteligencia artificial.',
            en: 'A useful agent is not just a model that talks. It is six parts, and the most important ones are not AI.',
          })}</p>
        </header>
        <ol className="grid stagger" role="list">
          {anatomy.map((p, i) => (
            <li key={p.id} className="card" style={p.ai ? { borderColor: 'var(--electric-iris)' } : undefined}>
              <span className="mono-label">{String(i + 1).padStart(2, '0')} / {p.ai ? 'AI' : 'SYSTEM'}</span>
              <h2 style={{ fontSize: 'var(--text-h3)', fontFamily: 'var(--font-sans)' }}>{l(p.name)}</h2>
              <p>{l(p.what)}</p>
              <p className="mono-label">{l({ es: 'En este proyecto', en: 'In this project' })}</p>
              <p style={{ color: 'var(--ink)' }}>{l(p.example)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="section" aria-labelledby="regla">
        <header>
          <h2 id="regla">{l({ es: 'El modelo conversa; el código decide', en: 'The model talks; code decides' })}</h2>
          <p className="muted">{l({
            es: 'El agente nunca calcula un monto ni decide una opción. Pide a la API y repite lo que la API devuelve. Si el modelo se equivoca, la política sigue intacta.',
            en: 'The agent never computes an amount or picks an option. It asks the API and repeats what the API returns. If the model errs, the policy stays intact.',
          })}</p>
        </header>
      </section>

      <section className="section" aria-labelledby="llamada">
        <header>
          <h2 id="llamada">{l({ es: 'Una llamada, paso a paso', en: 'One call, step by step' })}</h2>
          <p className="muted">{l({ es: 'En electric-iris, lo que hace la inteligencia; en azul, lo que dice el cliente.', en: 'In iris, what the intelligence does; in blue, what the customer says.' })}</p>
        </header>
        <figure className="diagram">
          <Script lines={example.script} />
          <figcaption>{l(example.title)}</figcaption>
        </figure>
        <p><Link className="btn" to="/integracion">{l({ es: 'Cómo se integra', en: 'How it integrates' })}</Link></p>
      </section>
    </>
  )
}
