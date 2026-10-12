import { useState } from 'react'
import { PhoneIcon, UserPlusIcon } from 'lucide-react'
import { api, type Customer } from '../api'
import { ACCOUNT_STATUS, longDate, money, spokenDigits } from '../format'

type Props = {
  tenant: string
  customers: Customer[]
  agentName: string
  onCall?: (customer: Customer) => void
  onAdded: () => Promise<unknown>
}

export function Customers({ tenant, customers, agentName, onCall, onAdded }: Props) {
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const [fresh, setFresh] = useState<string | null>(null)

  const add = async () => {
    setAdding(true)
    setError('')
    try {
      const { account_id } = await api.createCustomer(tenant)
      await onAdded()
      setFresh(account_id)
      requestAnimationFrame(() =>
        document.getElementById(`card-${account_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAdding(false)
    }
  }

  return (
    <section className="block" aria-labelledby="clientes">
      <header className="block-head">
        <h2 id="clientes">Clientes</h2>
        <p>Datos ficticios para probar. Para verificarte con {agentName}, di los últimos cuatro dígitos de la cédula y la fecha de nacimiento.</p>
        <p className="add-customer">
          <button type="button" className="ghost" onClick={add} disabled={adding}>
            <UserPlusIcon aria-hidden="true" /> {adding ? 'Creando…' : 'Agregar cliente al azar'}
          </button>
          <span role="status" className="error">{error}</span>
        </p>
      </header>
      <ul className="customers" role="list">
        {customers.map((c) => (
          <li key={c.account_id}>
            <article
              id={`card-${c.account_id}`}
              className={c.account_id === fresh ? 'customer fresh' : 'customer'}
              aria-labelledby={`c-${c.account_id}`}
            >
              <header>
                <h3 id={`c-${c.account_id}`}>{c.full_name}</h3>
                <p className={`status status-${c.status}`}>
                  {c.opted_out ? 'No contactar' : ACCOUNT_STATUS[c.status]}
                </p>
              </header>

              <dl className="test-data">
                <div>
                  <dt>Cédula</dt>
                  <dd>
                    {c.national_id.slice(0, -4)}
                    <mark>{c.national_id.slice(-4)}</mark>
                  </dd>
                </div>
                <div>
                  <dt>Nacimiento</dt>
                  <dd><time dateTime={c.birth_date}>{longDate(c.birth_date)}</time></dd>
                </div>
              </dl>
              <p className="say">
                Di: «{spokenDigits(c.national_id.slice(-4))}» y «{longDate(c.birth_date)}».
              </p>
              {onCall && !c.opted_out && (
                <button type="button" className="ghost call-as" onClick={() => onCall(c)}>
                  <PhoneIcon aria-hidden="true" /> Llamar como {c.full_name.split(' ')[0]}
                </button>
              )}

              <dl className="debt">
                <div>
                  <dt>En mora</dt>
                  <dd className="overdue">{money(c.overdue_amount)}</dd>
                </div>
                <div>
                  <dt>Días de mora</dt>
                  <dd>{c.days_past_due}</dd>
                </div>
                <div>
                  <dt>Saldo total</dt>
                  <dd>{money(c.total_balance)}</dd>
                </div>
              </dl>

              <footer>
                <p>{c.product}, cuenta terminada en {c.account_last4}</p>
                <p>{c.calls === 1 ? '1 llamada' : `${c.calls} llamadas`}</p>
              </footer>
            </article>
          </li>
        ))}
      </ul>
    </section>
  )
}
