import type { Case } from '../api'
import { dateTime } from '../format'

export function Cases({ cases }: { cases: Case[] }) {
  return (
    <section className="block" aria-labelledby="casos">
      <header className="block-head">
        <h2 id="casos">Casos para el equipo</h2>
        <p>Disputas, pedidos de llamada con un asesor y solicitudes de no volver a contactar.</p>
      </header>
      {cases.length === 0 ? (
        <p className="empty">Sin casos abiertos.</p>
      ) : (
        <div className="table-wrap" role="region" aria-labelledby="casos" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">Tipo</th>
                <th scope="col">Referencia</th>
                <th scope="col">Cliente</th>
                <th scope="col">Detalle</th>
                <th scope="col">Estado</th>
                <th scope="col">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.ref}>
                  <td>{c.kind[0].toUpperCase() + c.kind.slice(1)}</td>
                  <th scope="row">{c.ref}</th>
                  <td>{c.full_name ?? 'Sin verificar'}</td>
                  <td className="wrap">{c.summary}</td>
                  <td>{c.status === 'pending' ? 'Pendiente' : c.status === 'open' ? 'Abierta' : c.status}</td>
                  <td><time dateTime={c.created_at}>{dateTime(c.created_at)}</time></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
