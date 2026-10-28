import type { ConversionStats } from '../api'
import { useI18n } from '../i18n'

export function Conversion({ stats }: { stats: ConversionStats }) {
  const { t, f } = useI18n()
  return (
    <section className="block conversion" aria-labelledby="conversion-title">
      <h2 id="conversion-title">{t.conversionTitle}</h2>
      <dl className="conversion-stats">
        <div>
          <dt>{t.conversionOffered}</dt>
          <dd>{stats.offered}</dd>
        </div>
        <div>
          <dt>{t.conversionDisbursed}</dt>
          <dd>{stats.accepted}</dd>
        </div>
        <div>
          <dt>{t.conversionRejected}</dt>
          <dd>{stats.rejected}</dd>
        </div>
        <div>
          <dt>{t.conversionAmount}</dt>
          <dd>{f.money(Number(stats.disbursed_amount))}</dd>
        </div>
      </dl>
    </section>
  )
}
