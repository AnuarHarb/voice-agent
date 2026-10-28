import { Link, useParams } from 'react-router'
import { useL } from '../content/l10n'
import { useCaseById } from '../content/useCases'
import { QuickDemo } from '../site/QuickDemo'

export default function Demo({ caseId, compact = false }: { caseId?: string; compact?: boolean }) {
  const { l } = useL()
  const params = useParams()
  const id = caseId ?? params.id ?? ''
  const item = useCaseById(id)

  if (!item || !item.demo) {
    return (
      <section className="section">
        <h1>{l({ es: 'Este caso aún no tiene demo', en: 'This case has no demo yet' })}</h1>
        <Link to="/casos">{l({ es: 'Volver a los casos', en: 'Back to use cases' })}</Link>
      </section>
    )
  }

  return (
    <section className="section" aria-labelledby="demo-title">
      <header hidden={compact}>
        <p className="mono-label"><Link to={`/casos/${item.id}`}>{l(item.title)}</Link> / DEMO</p>
        <h1 id="demo-title" className="display">{l({ es: 'Llama al agente', en: 'Call the agent' })}</h1>
      </header>
      <QuickDemo lockedId={item.id} />
    </section>
  )
}
