import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { anatomy, integrationFlow, phases } from '../content/explain'
import { useL } from '../content/l10n'
import { industries, useCases, type L10n } from '../content/useCases'
import { LanguageSwitch } from '../components/LanguageSwitch'
import Demo from './Demo'

type Slide = { id: string; dark: boolean; notes: L10n; body: ReactNode }

function useSlides(): Slide[] {
  const { l, list } = useL()
  const featured = ['tarjeta-preventiva', 'libre-inversion-mora', 'oferta-cupo']
    .map((id) => useCases.find((c) => c.id === id)!)
  return [
    {
      id: 'portada', dark: true,
      notes: { es: 'Abrir con la frase. Una sola idea: agentes que ejecutan trabajo.', en: 'Open with the line. One idea: agents that execute work.' },
      body: (
        <>
          <img src="/brand/logo-horizontal-negativo.svg" alt="Inmercity Labs" height="40" style={{ justifySelf: 'start' }} />
          <h1>{l({ es: 'Agentes que hacen el trabajo.', en: 'Agents that do the work.' })}</h1>
          <p className="mono-label">Inmercity / Agents</p>
        </>
      ),
    },
    {
      id: 'problema', dark: false,
      notes: { es: 'Preguntar cuántas llamadas repetitivas atiende hoy su equipo.', en: 'Ask how many repetitive calls their team handles today.' },
      body: (
        <>
          <h2>{l({ es: 'Tu operación repite las mismas conversaciones.', en: 'Your operation repeats the same conversations.' })}</h2>
          <p>{l({ es: 'Cobranza, citas, pedidos, soporte. Reglas claras, volumen alto, poco margen para el error.', en: 'Collections, appointments, orders, support. Clear rules, high volume, little room for error.' })}</p>
        </>
      ),
    },
    {
      id: 'anatomia', dark: false,
      notes: { es: 'Insistir: cuatro de las seis piezas no son IA. Ahí está la confiabilidad.', en: 'Stress it: four of the six parts are not AI. That is where reliability comes from.' },
      body: (
        <>
          <h2>{l({ es: 'Seis piezas. Cuatro no son IA.', en: 'Six parts. Four are not AI.' })}</h2>
          <div className="deck-cols" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
            {anatomy.map((p) => (
              <article key={p.id} style={p.ai ? { borderColor: 'var(--electric-iris)' } : undefined}>
                <h3>{l(p.name)}</h3><p>{l(p.what)}</p>
              </article>
            ))}
          </div>
        </>
      ),
    },
    {
      id: 'industrias', dark: true,
      notes: { es: 'Mostrar que el patrón se repite. Finanzas es lo que ya funciona hoy.', en: 'Show that the pattern repeats. Finance is what works today.' },
      body: (
        <>
          <h2>{l({ es: 'Una arquitectura, cinco industrias.', en: 'One architecture, five industries.' })}</h2>
          <div className="deck-cols">
            {industries.map((i) => <article key={i.id}><h3>{l(i.name)}</h3><p>{l(i.summary)}</p></article>)}
          </div>
        </>
      ),
    },
    ...featured.map((c): Slide => ({
      id: c.id, dark: false,
      notes: { es: `Caso: ${c.title.es}. Contar el problema y qué métrica mueve.`, en: `Case: ${c.title.en}. Tell the problem and the metric it moves.` },
      body: (
        <>
          <p className="mono-label">{l({ es: 'CASO', en: 'CASE' })} / {l(industries.find((i) => i.id === c.industry)!.name)}</p>
          <h2>{l(c.title)}</h2>
          <p>{l(c.problem)}</p>
          <ol>{list(c.flow).map((s) => <li key={s}>{s}</li>)}</ol>
          <p className="mono-label">{l({ es: 'Métrica', en: 'Metric' })} / {l(c.metric)}</p>
        </>
      ),
    })),
    {
      id: 'demo', dark: false,
      notes: { es: 'Llamar en vivo con un cliente de prueba. Señalar el panel de herramientas.', en: 'Call live with a test customer. Point at the tool panel.' },
      body: (
        <>
          <h2>{l({ es: 'Ahora, en vivo.', en: 'Now, live.' })}</h2>
          <Demo caseId="libre-inversion-mora" compact />
        </>
      ),
    },
    {
      id: 'integracion', dark: true,
      notes: { es: 'El agente nunca toca sus sistemas: pasa por una API que ustedes controlan.', en: 'The agent never touches your systems: it goes through an API you control.' },
      body: (
        <>
          <h2>{l({ es: 'Se integra sin tocar tu core.', en: 'It integrates without touching your core.' })}</h2>
          <ol className="deck-cols">
            {integrationFlow.map((n) => (
              <li key={n.name.es} style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)', ...(n.ai ? { borderColor: 'var(--electric-iris)' } : {}) }}>
                <strong style={{ color: 'var(--ink)' }}>{l(n.name)}</strong><br />{l(n.detail)}
              </li>
            ))}
          </ol>
        </>
      ),
    },
    {
      id: 'fases', dark: false,
      notes: { es: 'Proponer empezar por una sola conversación.', en: 'Propose starting with a single conversation.' },
      body: (
        <>
          <h2>{l({ es: 'De la idea a producción.', en: 'From idea to production.' })}</h2>
          <ol className="deck-cols">
            {phases.map((p, i) => (
              <li key={p.name.es} style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-6)' }}>
                <span className="mono-label">{String(i + 1).padStart(2, '0')}</span><br />
                <strong style={{ color: 'var(--ink)' }}>{l(p.name)}</strong><br />{l(p.detail)}
              </li>
            ))}
          </ol>
        </>
      ),
    },
    {
      id: 'cierre', dark: true,
      notes: { es: 'Cerrar con la pregunta: ¿qué conversación automatizamos primero?', en: 'Close with the question: which conversation do we automate first?' },
      body: (
        <>
          <img src="/brand/logo-horizontal-negativo.svg" alt="Inmercity Labs" height="40" style={{ justifySelf: 'start' }} />
          <h2>{l({ es: '¿Qué conversación automatizamos primero?', en: 'Which conversation do we automate first?' })}</h2>
          <p className="mono-label">Inmercity Labs. Building Intelligence.</p>
        </>
      ),
    },
  ]
}

export default function Deck() {
  const { l } = useL()
  const slides = useSlides()
  const { slide } = useParams()
  const navigate = useNavigate()
  const index = Math.min(Math.max((Number(slide) || 1) - 1, 0), slides.length - 1)
  const [notes, setNotes] = useState(false)
  const current = slides[index]

  const go = useCallback(
    (to: number) => navigate(`/presentacion/${Math.min(Math.max(to, 0), slides.length - 1) + 1}`),
    [navigate, slides.length],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'BUTTON' || tag === 'A') return
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); go(index + 1) }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(index - 1)
      else if (e.key.toLowerCase() === 'n') setNotes((v) => !v)
      else if (e.key.toLowerCase() === 'f') {
        if (document.fullscreenElement) void document.exitFullscreen()
        else void document.documentElement.requestFullscreen()
      }
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [go, index])

  useEffect(() => {
    document.title = `${index + 1}/${slides.length} · Inmercity / Agents`
  }, [index, slides.length])

  return (
    <div className="deck" data-tone={current.dark ? 'dark' : 'light'}>
      <header className="deck-top">
        <Link to="/" className="mono-label" style={{ textDecoration: 'none' }}>Inmercity / Agents</Link>
        <LanguageSwitch />
      </header>
      <main className="deck-slide" aria-live="polite" key={current.id}>{current.body}</main>
      <div>
        {notes && (
          <aside className="deck-notes" aria-label={l({ es: 'Notas del presentador', en: 'Speaker notes' })}>
            <p className="mono-label">{l({ es: 'NOTAS', en: 'NOTES' })}</p>
            <p>{l(current.notes)}</p>
          </aside>
        )}
        <footer className="deck-bottom">
          <span className="mono-label">{String(index + 1).padStart(2, '0')} / {String(slides.length).padStart(2, '0')}</span>
          <nav aria-label={l({ es: 'Diapositivas', en: 'Slides' })} style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button type="button" onClick={() => go(index - 1)} disabled={index === 0}>{l({ es: 'Anterior', en: 'Previous' })}</button>
            <button type="button" onClick={() => go(index + 1)} disabled={index === slides.length - 1}>{l({ es: 'Siguiente', en: 'Next' })}</button>
            <button type="button" aria-pressed={notes} onClick={() => setNotes((v) => !v)}>{l({ es: 'Notas (N)', en: 'Notes (N)' })}</button>
            <button type="button" onClick={() => void document.documentElement.requestFullscreen()}>{l({ es: 'Pantalla completa (F)', en: 'Fullscreen (F)' })}</button>
          </nav>
        </footer>
      </div>
    </div>
  )
}
