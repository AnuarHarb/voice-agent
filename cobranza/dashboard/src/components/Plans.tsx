import type { Plan } from '../api'
import { useI18n } from '../i18n'

export function Plans({ plans }: { plans: Plan[] }) {
  const { t, f } = useI18n()
  return (
    <section className="block" aria-labelledby="planes">
      <header className="block-head">
        <h2 id="planes">{t.plansTitle}</h2>
        <p>{t.plansIntro}</p>
      </header>
      {plans.length === 0 ? (
        <p className="empty">{t.plansEmpty}</p>
      ) : (
        <div className="table-wrap" role="region" aria-labelledby="planes" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t.colPlan}</th>
                <th scope="col">{t.colCustomer}</th>
                <th scope="col" className="num">{t.colInstallments}</th>
                <th scope="col" className="num">{t.colInstallment}</th>
                <th scope="col" className="num">{t.colTotal}</th>
                <th scope="col">{t.colFirstDate}</th>
                <th scope="col">{t.colStatus}</th>
                <th scope="col">{t.colLink}</th>
                <th scope="col">{t.colRegistered}</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.plan_ref}>
                  <th scope="row">
                    {p.plan_ref}
                    {p.hardship && <span className="tag">{t.hardshipTag}</span>}
                  </th>
                  <td>{p.full_name}</td>
                  <td className="num">{p.installments}</td>
                  <td className="num">{f.money(p.installment_amount)}</td>
                  <td className="num">{f.money(p.total_amount)}</td>
                  <td><time dateTime={p.first_due_date}>{f.shortDate(p.first_due_date)}</time></td>
                  <td>{t.planStatus[p.status]}</td>
                  <td>
                    {p.link_status ? t.linkVia(t.linkStatus[p.link_status], p.link_channel) : t.noLink}
                    {p.pay_url && (
                      <>
                        {' · '}
                        <a href={p.pay_url} target="_blank" rel="noreferrer">
                          {p.status === 'paid' ? t.view : t.openAndPay}
                        </a>
                      </>
                    )}
                  </td>
                  <td><time dateTime={p.created_at}>{f.dateTime(p.created_at)}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
