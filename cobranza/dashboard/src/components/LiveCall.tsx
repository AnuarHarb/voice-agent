import { lazy, Suspense } from 'react'
import { MicIcon, MicOffIcon, PhoneIcon, PhoneOffIcon } from 'lucide-react'
import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ui/conversation'
import { Message, MessageContent } from '@/components/ui/message'
import { ShimmeringText } from '@/components/ui/shimmering-text'
import { useI18n } from '../i18n'
import type { LiveCall as Call } from '../live'

const Orb = lazy(() => import('@/components/ui/orb').then((m) => ({ default: m.Orb })))

const ORB_COLORS: Record<string, [string, string]> = {
  avanza: ['#847dff', '#635bff'],
  nexo: ['#847dff', '#635bff'],
}

function StatusLine({ call, agentName }: { call: Call; agentName: string }) {
  const { t } = useI18n()
  if (call.micDenied) return <p className="error">{t.micDenied}</p>
  if (call.error) return <p className="error">{call.error}</p>
  if (call.status === 'connecting') return <ShimmeringText text={t.connecting(agentName)} />
  if (call.status !== 'connected') return <p className="muted">{t.ready}</p>
  if (call.agentState === 'thinking') return <ShimmeringText text={t.thinking(agentName)} />
  return <p>{call.agentState === 'talking' ? t.talking(agentName) : t.listening(agentName)}</p>
}

export function LiveCall({ call, tenant, agentName }: { call: Call; tenant: string; agentName: string }) {
  const { t, f } = useI18n()
  const live = call.status === 'connected' || call.status === 'connecting'
  const colors = ORB_COLORS[tenant] ?? ORB_COLORS.avanza

  return (
    <section className="block live" id="en-vivo" aria-labelledby="en-vivo-titulo">
      <header className="block-head">
        <h2 id="en-vivo-titulo">{t.liveTitle}</h2>
        <p>{t.liveIntro(agentName)}</p>
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
                <dt>{t.callingAs}</dt>
                <dd>{call.caller.full_name}</dd>
              </div>
              <div>
                <dt>{t.nationalId}</dt>
                <dd>«{f.spokenDigits(call.caller.national_id.slice(-4))}»</dd>
              </div>
              <div>
                <dt>{t.birthDate}</dt>
                <dd>«{f.longDate(call.caller.birth_date)}»</dd>
              </div>
            </dl>
          )}

          <div className="live-actions">
            {live ? (
              <>
                <button type="button" className="call hang-up" onClick={call.end}>
                  <PhoneOffIcon aria-hidden="true" /> {t.hangUp}
                </button>
                <button type="button" className="ghost" onClick={call.toggleMute} aria-pressed={call.isMuted}>
                  {call.isMuted ? <MicOffIcon aria-hidden="true" /> : <MicIcon aria-hidden="true" />}
                  {call.isMuted ? t.unmute : t.mute}
                </button>
              </>
            ) : (
              <button type="button" className="call" onClick={() => call.start()}>
                <PhoneIcon aria-hidden="true" /> {t.callAgent(agentName)}
              </button>
            )}
          </div>
        </div>

        <Conversation className="transcript" aria-label={t.transcriptLabel(agentName)}>
          <ConversationContent className="transcript-content">
            {call.lines.length === 0 ? (
              <p className="transcript-empty">{live ? t.transcriptLive(agentName) : t.transcriptIdle}</p>
            ) : (
              call.lines.map((line) =>
                line.kind === 'tool' ? (
                  <p key={line.id} className={`tool-step${line.ok === false ? ' is-error' : ''}`}>
                    {line.ok === null ? (
                      <ShimmeringText text={`${t.tool[line.tool] ?? line.tool}…`} />
                    ) : (
                      <>{line.ok ? '✓' : '✕'} {t.tool[line.tool] ?? line.tool}</>
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
          <ConversationScrollButton aria-label={t.scrollLatest} />
        </Conversation>
      </div>
    </section>
  )
}
