import { integrationFlow, phases, toolContract } from '../content/explain'
import { useL } from '../content/l10n'

export default function Integration() {
  const { l } = useL()
  return (
    <>
      <section className="section" aria-labelledby="int-title">
        <header>
          <p className="mono-label">Inmercity / Agents</p>
          <h1 id="int-title" className="display">{l({ es: 'Cómo se integra con tu operación', en: 'How it integrates with your operation' })}</h1>
          <p className="body-lg">{l({
            es: 'El agente no toca tus sistemas directamente. Habla con una API de herramientas que tú controlas y que valida cada acción.',
            en: 'The agent never touches your systems directly. It talks to a tools API you control, which validates every action.',
          })}</p>
        </header>
        <figure className="diagram">
          <ol className="stagger" role="list">
            {integrationFlow.map((n) => (
              <li key={n.name.es} className={n.ai ? 'ai' : undefined}>
                <strong>{l(n.name)}</strong>
                <span>{l(n.detail)}</span>
              </li>
            ))}
          </ol>
          <figcaption>{l({ es: 'Flujo de una acción: del canal al sistema del cliente.', en: 'Flow of one action: from channel to client system.' })}</figcaption>
        </figure>
      </section>

      <section className="section" aria-labelledby="contrato">
        <header>
          <h2 id="contrato">{l({ es: 'Cada herramienta es un contrato', en: 'Every tool is a contract' })}</h2>
          <p className="muted">{l({
            es: 'Un endpoint, un esquema de entrada y una clave por cliente. Esta es una de las doce herramientas reales del proyecto.',
            en: 'One endpoint, one input schema and one key per client. This is one of the twelve real tools in the project.',
          })}</p>
        </header>
        <pre className="code" tabIndex={0}><code>{toolContract}</code></pre>
      </section>

      <section className="section" aria-labelledby="seguridad">
        <header><h2 id="seguridad">{l({ es: 'Multi-cliente, seguridad y auditoría', en: 'Multi-client, security and audit' })}</h2></header>
        <div className="grid">
          {[
            { t: { es: 'Aislamiento por cliente', en: 'Per-client isolation' }, d: { es: 'Dos fintechs de demo, Banco Avanza y Nexo, comparten infraestructura sin ver los datos del otro. Lo aplica la base de datos.', en: 'Two demo fintechs, Banco Avanza and Nexo, share infrastructure without seeing each other. The database enforces it.' } },
            { t: { es: 'Claves y sesiones', en: 'Keys and sessions' }, d: { es: 'El backend guarda solo hashes de las claves. Las sesiones expiran en 30 minutos.', en: 'The backend stores only key hashes. Sessions expire after 30 minutes.' } },
            { t: { es: 'Bitácora', en: 'Audit log' }, d: { es: 'Cada herramienta llamada queda registrada con su resultado, lista para revisión.', en: 'Every tool call is recorded with its result, ready for review.' } },
          ].map((x) => <article className="card" key={x.t.es}><h3>{l(x.t)}</h3><p>{l(x.d)}</p></article>)}
        </div>
      </section>

      <section className="section" aria-labelledby="fases">
        <header><h2 id="fases">{l({ es: 'De la idea a producción', en: 'From idea to production' })}</h2></header>
        <ol className="grid" role="list">
          {phases.map((p, i) => (
            <li className="card" key={p.name.es}>
              <span className="mono-label">{String(i + 1).padStart(2, '0')}</span>
              <h3>{l(p.name)}</h3>
              <p>{l(p.detail)}</p>
            </li>
          ))}
        </ol>
      </section>
    </>
  )
}
