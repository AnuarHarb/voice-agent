import type { Tenant } from '../api'
import { useI18n } from '../i18n'

type CaseCard = {
  id: string
  title: string
  problem: string
  agentLabel: string
}

const CASES: CaseCard[] = [
  {
    id: 'tarjeta_preventiva',
    title: 'Tarjeta · preventiva',
    problem: 'Recordar el pago antes del vencimiento sin caer en mora.',
    agentLabel: 'tarjeta_preventiva',
  },
  {
    id: 'libre_inversion_mora',
    title: 'Libre inversión · mora temprana',
    problem: 'Ponerse al día con acuerdos que la política permite.',
    agentLabel: 'libre_inversion_mora',
  },
  {
    id: 'vehiculo_mora',
    title: 'Vehículo · mora media',
    problem: 'Recuperar lo vencido con pocas opciones y escalar a tiempo.',
    agentLabel: 'vehiculo_mora',
  },
  {
    id: 'microcredito',
    title: 'Microcrédito · mora temprana',
    problem: 'Llamadas cortas que terminan en link o promesa con fecha.',
    agentLabel: 'microcredito',
  },
  {
    id: 'oferta_cupo',
    title: 'Oferta comercial',
    problem: 'Ofrecer cupo disponible a clientes al día, con consentimiento comercial.',
    agentLabel: 'oferta_cupo',
  },
]

type Props = {
  tenant: Tenant
  agents: { label: string; agent_id: string }[]
}

export function CasesCatalog({ tenant, agents }: Props) {
  const { t } = useI18n()
  const agentFor = (label: string) => agents.find((a) => a.label === label)?.agent_id

  return (
    <section className="block cases-catalog" aria-labelledby="casos-title">
      <h2 id="casos-title">{t.casesCatalogTitle}</h2>
      <p className="lede">{t.casesCatalogLead}</p>
      <div className="cases-grid">
        {CASES.map((item) => {
          const agentId = agentFor(item.agentLabel)
          const talkUrl = agentId
            ? `https://elevenlabs.io/app/talk-to?agent_id=${encodeURIComponent(agentId)}`
            : undefined
          return (
            <article key={item.id} className="case-card">
              <h3>{item.title}</h3>
              <p>{item.problem}</p>
              <figure>
                <figcaption>{t.casesConsoleCaption}</figcaption>
                <div className="case-placeholder" role="img" aria-label={t.casesScreenshotPending} />
              </figure>
              <audio controls preload="none" aria-label={t.casesAudioPending}>
                <track kind="captions" />
              </audio>
              {talkUrl ? (
                <p>
                  <a href={talkUrl} target="_blank" rel="noopener noreferrer">
                    {t.casesTryLive}
                  </a>
                </p>
              ) : (
                <p className="muted">{t.casesAgentPending}</p>
              )}
            </article>
          )
        })}
      </div>
      <p className="muted">{t.casesTenantNote(tenant.name)}</p>
    </section>
  )
}
