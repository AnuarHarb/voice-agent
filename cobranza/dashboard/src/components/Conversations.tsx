import { useEffect, useState } from 'react'
import { api, type AuditEvent, type Conversation } from '../api'
import { historyUrl } from '../format'
import { useI18n } from '../i18n'

function Events({ tenant, conversationId }: { tenant: string; conversationId: string }) {
  const { t, f } = useI18n()
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

  if (error) return <p className="error">{t.eventsError(error)}</p>
  if (events === null) return <p className="muted">{t.eventsLoading}</p>
  if (events.length === 0) return <p className="muted">{t.eventsEmpty}</p>

  return (
    <ol className="events">
      {events.map((e, i) => {
        const detail = Object.entries(e.detail ?? {})
        return (
          <li key={i} className={e.result.startsWith('rejected') || e.result.includes('fail') || e.result === 'not_verified' ? 'is-warning' : ''}>
            <time dateTime={e.created_at}>{f.clock(e.created_at)}</time>
            <p>
              <strong>{t.tool[e.tool] ?? e.tool}</strong>: {t.result[e.result] ?? e.result}
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
  const { t, f } = useI18n()
  const [open, setOpen] = useState(false)
  return (
    <li>
      <details onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>
          <time dateTime={c.started_at}>{f.dateTime(c.started_at)}</time>
          <span className="who">{c.full_name ?? t.unidentified}</span>
          <span className={`outcome outcome-${c.outcome ?? 'pendiente'}`}>
            {c.outcome ? t.outcome[c.outcome] ?? c.outcome : t.noSummary}
          </span>
          <span className="muted">{f.duration(c.duration_secs)}</span>
        </summary>
        <div className="conversation-body">
          <dl className="facts">
            {c.language && (<div><dt>{t.language}</dt><dd>{t.languageName(c.language)}</dd></div>)}
            {c.late_reason && (<div><dt>{t.lateReason}</dt><dd>{c.late_reason}</dd></div>)}
            {c.promise_amount != null && (
              <div>
                <dt>{t.promise}</dt>
                <dd>{f.money(c.promise_amount)}{c.promise_date ? t.promiseFrom(f.shortDate(c.promise_date)) : ''}</dd>
              </div>
            )}
            {c.hardship != null && (<div><dt>{t.hardship}</dt><dd>{c.hardship ? t.yes : t.no}</dd></div>)}
            {c.sentiment_label && (
              <div>
                <dt>{t.moodAtEnd}</dt>
                <dd>
                  <span className={`mood mood-${c.sentiment_label}`}>{t.sentiment[c.sentiment_label]}</span>
                  {c.frustration_score != null && t.frustration(f.percent(c.frustration_score))}
                  {c.min_sentiment_score != null && c.sentiment_score != null && c.min_sentiment_score < c.sentiment_score &&
                    t.lowest(f.signed(c.min_sentiment_score), f.signed(c.sentiment_score))}
                </dd>
              </div>
            )}
            <div><dt>{t.toolCalls}</dt><dd>{c.tool_calls}</dd></div>
          </dl>
          <h3>{t.stepsTitle}</h3>
          {open && <Events tenant={tenant} conversationId={c.conversation_id} />}
          <p>
            <a href={historyUrl(c.conversation_id)} target="_blank" rel="noreferrer">
              {t.listen}
            </a>
          </p>
        </div>
      </details>
    </li>
  )
}

export function Conversations({ tenant, conversations }: { tenant: string; conversations: Conversation[] }) {
  const { t } = useI18n()
  return (
    <section className="block" aria-labelledby="conversaciones">
      <header className="block-head">
        <h2 id="conversaciones">{t.conversationsTitle}</h2>
        <p>{t.conversationsIntro}</p>
      </header>
      {conversations.length === 0 ? (
        <p className="empty">{t.conversationsEmpty}</p>
      ) : (
        <ul className="conversations" role="list">
          {conversations.map((c) => <Row key={c.conversation_id} tenant={tenant} c={c} />)}
        </ul>
      )}
    </section>
  )
}
