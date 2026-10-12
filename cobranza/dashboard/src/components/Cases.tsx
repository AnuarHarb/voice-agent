import type { Case } from '../api'
import { useI18n } from '../i18n'

export function Cases({ cases }: { cases: Case[] }) {
  const { t, f } = useI18n()
  return (
    <section className="block" aria-labelledby="casos">
      <header className="block-head">
        <h2 id="casos">{t.casesTitle}</h2>
        <p>{t.casesIntro}</p>
      </header>
      {cases.length === 0 ? (
        <p className="empty">{t.casesEmpty}</p>
      ) : (
        <div className="table-wrap" role="region" aria-labelledby="casos" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colKind}</th>
                <th scope="col">{t.colRef}</th>
                <th scope="col">{t.colCustomer}</th>
                <th scope="col">{t.colDetail}</th>
                <th scope="col">{t.colStatus}</th>
                <th scope="col">{t.colDate}</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.ref}>
                  <td>{t.caseKind[c.kind] ?? c.kind}</td>
                  <th scope="row">{c.ref}</th>
                  <td>{c.full_name ?? t.unverified}</td>
                  <td className="wrap">{c.summary}</td>
                  <td>{t.caseStatus[c.status] ?? c.status}</td>
                  <td><time dateTime={c.created_at}>{f.dateTime(c.created_at)}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
