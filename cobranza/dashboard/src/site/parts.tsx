import { Link } from 'react-router'
import { useL } from '../content/l10n'
import { industryById, type ScriptLine, type UseCase } from '../content/useCases'

export function CaseTag({ item }: { item: UseCase }) {
  const { l } = useL()
  return item.demo
    ? <span className="pill pill-live">{l({ es: 'Demo en vivo', en: 'Live demo' })}</span>
    : <span className="pill">{l({ es: 'Concepto', en: 'Concept' })}</span>
}

export function CaseCard({ item }: { item: UseCase }) {
  const { l } = useL()
  return (
    <article className="card">
      <div className="meta">
        <span className="mono-label">{l(industryById(item.industry)!.name)}</span>
        <CaseTag item={item} />
      </div>
      <h3><Link className="card-link" to={`/casos/${item.id}`}>{l(item.title)}</Link></h3>
      <p>{l(item.problem)}</p>
      <p className="mono-label">{l({ es: 'Métrica', en: 'Metric' })} / {l(item.metric)}</p>
    </article>
  )
}

export function Script({ lines }: { lines: ScriptLine[] }) {
  const { l } = useL()
  return (
    <ol className="script" role="list">
      {lines.map((line, i) => (
        <li key={i} className={line.kind}>
          <span className="who">
            {line.kind === 'tool' ? `TOOL / ${line.name}` : line.kind === 'agent' ? 'AGENT_01' : l({ es: 'CLIENTE', en: 'CUSTOMER' })}
          </span>
          <span className="says">{line.kind === 'tool' ? l(line.result) : l(line.text)}</span>
        </li>
      ))}
    </ol>
  )
}
