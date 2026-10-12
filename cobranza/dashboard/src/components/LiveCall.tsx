import { lazy, Suspense } from 'react'
import { MicIcon, MicOffIcon, PhoneIcon, PhoneOffIcon } from 'lucide-react'
import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ui/conversation'
import { Message, MessageContent } from '@/components/ui/message'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { longDate, spokenDigits, TOOL } from '../format'
import type { LiveCall as Call } from '../live'

const Orb = lazy(() => import('@/components/ui/orb').then((m) => ({ default: m.Orb })))

const ORB_COLORS: Record<string, [string, string]> = {
  avanza: ['#7fd3b0', '#1f8a66'],
  nexo: ['#9db4f2', '#2f4fa8'],
}

function StatusLine({ call, agentName }: { call: Call; agentName: string }) {
  if (call.error) return <p className="error">{call.error}</p>
  if (call.status === 'connecting') return <ShimmeringText text={`Conectando con ${agentName}…`} />
  if (call.status !== 'connected') return <p className="muted">Lista para llamar</p>
  if (call.agentState === 'thinking') return <ShimmeringText text={`${agentName} está consultando…`} />
  return <p>{call.agentState === 'talking' ? `${agentName} está hablando` : `${agentName} te escucha`}</p>
}

export function LiveCall({ call, tenant, agentName }: { call: Call; tenant: string; agentName: string }) {
  const live = call.status === 'connected' || call.status === 'connecting'
  const colors = ORB_COLORS[tenant] ?? ORB_COLORS.avanza

  return (
    <section className="block live" id="en-vivo" aria-labelledby="en-vivo-titulo">
      <header className="block-head">
        <h2 id="en-vivo-titulo">Llamada en vivo</h2>
        <p>
          Habla con {agentName} desde aquí con tu micrófono. El plan o el caso aparece en las tablas apenas cuelgues.
          Cada llamada consume créditos de ElevenLabs.
        </p>
      </header>

      <div className="live-grid">
        <div className="live-agent">
          <div className="orb" aria-hidden="true">
            <Suspense fallback={null}>
              <Orb
                colors={colors}
                agentState={call.agentState}
                volumeMode={call.status === 'connected' ? 'manual' : 'auto'}
                getInputVolume={call.getInputVolume}
                getOutputVolume={call.getOutputVolume}
              />
            </Suspense>
          </div>
          <div className="live-status" aria-live="polite">
            <StatusLine call={call} agentName={agentName} />
          </div>

          {call.caller && live && (
            <dl className="caller">
              <div>
                <dt>Llamas como</dt>
                <dd>{call.caller.full_name}</dd>
              </div>
              <div>
                <dt>Cédula</dt>
                <dd>«{spokenDigits(call.caller.national_id.slice(-4))}»</dd>
              </div>
              <div>
                <dt>Nacimiento</dt>
                <dd>«{longDate(call.caller.birth_date)}»</dd>
              </div>
            </dl>
          )}

          <div className="live-actions">
            {live ? (
              <>
                <button type="button" className="call hang-up" onClick={call.end}>
                  <PhoneOffIcon aria-hidden="true" /> Colgar
                </button>
                <button type="button" className="ghost" onClick={call.toggleMute} aria-pressed={call.isMuted}>
                  {call.isMuted ? <MicOffIcon aria-hidden="true" /> : <MicIcon aria-hidden="true" />}
                  {call.isMuted ? 'Activar micrófono' : 'Silenciar'}
                </button>
              </>
            ) : (
              <button type="button" className="call" onClick={() => call.start()}>
                <PhoneIcon aria-hidden="true" /> Llamar a {agentName}
              </button>
            )}
          </div>
        </div>

        <Conversation className="transcript" aria-label={`Transcripción con ${agentName}`}>
          <ConversationContent className="transcript-content">
            {call.lines.length === 0 ? (
              <p className="transcript-empty">
                {live
                  ? `Saluda a ${agentName}; lo que digan los dos aparece aquí.`
                  : 'La transcripción aparece aquí durante la llamada. Para llamar como un cliente, usa el botón de su tarjeta.'}
              </p>
            ) : (
              call.lines.map((line) =>
                line.kind === 'tool' ? (
                  <p key={line.id} className={`tool-step${line.ok === false ? ' is-error' : ''}`}>
                    {line.ok === null ? (
                      <ShimmeringText text={`${TOOL[line.tool] ?? line.tool}…`} />
                    ) : (
                      <>{line.ok ? '✓' : '✕'} {TOOL[line.tool] ?? line.tool}</>
                    )}
                  </p>
                ) : (
                  <Message key={line.id} from={line.kind === 'user' ? 'user' : 'assistant'} className="py-1.5">
                    <MessageContent>
                      <p>{line.text}</p>
                    </MessageContent>
                  </Message>
                ),
              )
            )}
          </ConversationContent>
          <ConversationScrollButton aria-label="Ir al último mensaje" />
        </Conversation>
      </div>
    </section>
  )
}
