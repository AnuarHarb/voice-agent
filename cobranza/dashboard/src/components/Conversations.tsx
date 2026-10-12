import { useEffect, useState } from 'react'
import { api, type AuditEvent, type Conversation } from '../api'
import { OUTCOME, SENTIMENT, TOOL, clock, dateTime, duration, historyUrl, money, percent, shortDate, signed } from '../format'

const RESULT: Record<string, string> = {
  verified: 'verificada',
  not_verified: 'no coincide',
  locked: 'bloqueada por intentos',
  ok: 'ok',
  sent: 'enviado',
  created: 'creado',
  registered: 'registrado',
  stored: 'guardado',
  idempotent_replay: 'repetido, se devolvió el mismo',
  channel_failed: 'falló el canal',
  simulated_payment: 'pagado',
}

function Events({ tenant, conversationId }: { tenant: string; conversationId: string }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let live = true
    api.events(tenant, conversationId).then(
      (rows) => live && setEvents(rows),
      (e: Error) => live && setError(e.message),
    )
    return () => { live = false }
  }, [tenant, conversationId])

  if (error) return <p className="error">No se pudo cargar la bitácora: {error}</p>
  if (events === null) return <p className="muted">Cargando la bitácora…</p>
  if (events.length === 0) return <p className="muted">El agente no llamó ninguna herramienta en esta conversación.</p>

  return (
    <ol className="events">
      {events.map((e, i) => {
        const detail = Object.entries(e.detail ?? {})
        return (
          <li key={i} className={e.result.startsWith('rejected') || e.result.includes('fail') || e.result === 'not_verified' ? 'is-warning' : ''}>
            <time dateTime={e.created_at}>{clock(e.created_at)}</time>
            <p>
              <strong>{TOOL[e.tool] ?? e.tool}</strong>: {RESULT[e.result] ?? e.result}
            </p>
            {detail.length > 0 && (
              <dl>
                {detail.map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        )
      })}
    </ol>
  )
}

function Row({ tenant, c }: { tenant: string; c: Conversation }) {
  const [open, setOpen] = useState(false)
  return (
    <li>
      <details onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>
          <time dateTime={c.started_at}>{dateTime(c.started_at)}</time>
          <span className="who">{c.full_name ?? 'Sin identificar'}</span>
          <span className={`outcome outcome-${c.outcome ?? 'pendiente'}`}>
            {c.outcome ? OUTCOME[c.outcome] ?? c.outcome : 'Sin resumen aún'}
          </span>
          <span className="muted">{duration(c.duration_secs)}</span>
        </summary>
        <div className="conversation-body">
          <dl className="facts">
            {c.language && (<div><dt>Idioma</dt><dd>{c.language === 'en' ? 'Inglés' : 'Español'}</dd></div>)}
            {c.late_reason && (<div><dt>Motivo de la mora</dt><dd>{c.late_reason}</dd></div>)}
            {c.promise_amount != null && (<div><dt>Promesa</dt><dd>{money(c.promise_amount)}{c.promise_date ? `, desde el ${shortDate(c.promise_date)}` : ''}</dd></div>)}
            {c.hardship != null && (<div><dt>Dificultad económica</dt><dd>{c.hardship ? 'Sí' : 'No'}</dd></div>)}
            {c.sentiment_label && (
              <div>
                <dt>Ánimo al final</dt>
                <dd>
                  <span className={`mood mood-${c.sentiment_label}`}>{SENTIMENT[c.sentiment_label]}</span>
                  {c.frustration_score != null && `, frustración ${percent(c.frustration_score)}`}
                  {c.min_sentiment_score != null && c.sentiment_score != null && c.min_sentiment_score < c.sentiment_score &&
                    `; su punto más bajo fue ${signed(c.min_sentiment_score)} y cerró en ${signed(c.sentiment_score)}`}
                </dd>
              </div>
            )}
            <div><dt>Herramientas llamadas</dt><dd>{c.tool_calls}</dd></div>
          </dl>
          <h3>Lo que hizo el agente, paso a paso</h3>
          {open && <Events tenant={tenant} conversationId={c.conversation_id} />}
          <p>
            <a href={historyUrl(c.conversation_id)} target="_blank" rel="noreferrer">
              Escuchar la llamada en ElevenLabs
            </a>
          </p>
        </div>
      </details>
    </li>
  )
}

export function Conversations({ tenant, conversations }: { tenant: string; conversations: Conversation[] }) {
  return (
    <section className="block" aria-labelledby="conversaciones">
      <header className="block-head">
        <h2 id="conversaciones">Conversaciones</h2>
        <p>Abre una para ver, en orden, cada herramienta que usó el agente y qué le respondió el sistema.</p>
      </header>
      {conversations.length === 0 ? (
        <p className="empty">Aún no hay llamadas. La primera aparecerá aquí sola, sin recargar.</p>
      ) : (
        <ul className="conversations" role="list">
          {conversations.map((c) => <Row key={c.conversation_id} tenant={tenant} c={c} />)}
        </ul>
      )}
    </section>
  )
}
