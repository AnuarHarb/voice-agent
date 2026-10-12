import type { Plan } from '../api'
import { LINK_STATUS, PLAN_STATUS, dateTime, money, shortDate } from '../format'

export function Plans({ plans }: { plans: Plan[] }) {
  return (
    <section className="block" aria-labelledby="planes">
      <header className="block-head">
        <h2 id="planes">Planes registrados</h2>
        <p>Cada plan sale de una opción que calculó la política de crédito; el agente no puede inventar montos.</p>
      </header>
      {plans.length === 0 ? (
        <p className="empty">Todavía no hay planes. Llama al agente y acepta una opción para ver aparecer el primero.</p>
      ) : (
        <div className="table-wrap" role="region" aria-labelledby="planes" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">Plan</th>
                <th scope="col">Cliente</th>
                <th scope="col" className="num">Cuotas</th>
                <th scope="col" className="num">Valor cuota</th>
                <th scope="col" className="num">Total</th>
                <th scope="col">Primera fecha</th>
                <th scope="col">Estado</th>
                <th scope="col">Link de pago</th>
                <th scope="col">Registrado</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.plan_ref}>
                  <th scope="row">
                    {p.plan_ref}
                    {p.hardship && <span className="tag">Dificultad</span>}
                  </th>
                  <td>{p.full_name}</td>
                  <td className="num">{p.installments}</td>
                  <td className="num">{money(p.installment_amount)}</td>
                  <td className="num">{money(p.total_amount)}</td>
                  <td><time dateTime={p.first_due_date}>{shortDate(p.first_due_date)}</time></td>
                  <td>{PLAN_STATUS[p.status]}</td>
                  <td>
                    {p.link_status ? `${LINK_STATUS[p.link_status]}${p.link_channel ? ` por ${p.link_channel}` : ''}` : 'Sin link'}
                    {p.pay_url && (
                      <>
                        {' · '}
                        <a href={p.pay_url} target="_blank" rel="noreferrer">
                          {p.status === 'paid' ? 'Ver' : 'Abrir y pagar'}
                        </a>
                      </>
                    )}
                  </td>
                  <td><time dateTime={p.created_at}>{dateTime(p.created_at)}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
