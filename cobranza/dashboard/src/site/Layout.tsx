import { useEffect } from 'react'
import { NavLink, Link, Outlet, useLocation } from 'react-router'
import { LanguageSwitch } from '../components/LanguageSwitch'
import { useL } from '../content/l10n'

function Logo() {
  return (
    <>
      <img className="logo logo-light" src="/brand/logo-horizontal-positivo.svg" alt="Inmercity Labs" height="28" />
      <img className="logo logo-dark" src="/brand/logo-horizontal-negativo.svg" alt="Inmercity Labs" height="28" />
    </>
  )
}

export function Layout() {
  const { l } = useL()
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
    if (pathname !== '/consola') document.title = 'Inmercity / Agents'
  }, [pathname])
  const links = [
    { to: '/casos', label: { es: 'Casos de uso', en: 'Use cases' } },
    { to: '/como-funciona', label: { es: 'Cómo funciona', en: 'How it works' } },
    { to: '/integracion', label: { es: 'Integración', en: 'Integration' } },
    { to: '/consola', label: { es: 'Detrás de cámaras', en: 'Behind the scenes' } },
  ]
  return (
    <div className="site">
      <a className="skip" href="#contenido">{l({ es: 'Saltar al contenido', en: 'Skip to content' })}</a>
      <header className="site-header">
        <Link to="/" className="site-logo" aria-label="Inmercity Labs"><Logo /></Link>
        <nav aria-label={l({ es: 'Principal', en: 'Main' })}>
          <ul role="list">
            {links.map((x) => (
              <li key={x.to}><NavLink to={x.to}>{l(x.label)}</NavLink></li>
            ))}
          </ul>
        </nav>
        <div className="site-tools">
          <Link className="btn btn-quiet" to="/presentacion">{l({ es: 'Presentar', en: 'Present' })}</Link>
          <LanguageSwitch />
        </div>
      </header>
      <main id="contenido" className="site-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <p className="mono-label">Inmercity / Agents</p>
        <p>Inmercity Labs. Building Intelligence.</p>
        <p className="muted">{l({
          es: 'Los demos usan nombres, cuentas y datos ficticios. Los casos marcados como concepto aún no están en producción.',
          en: 'Demos use fictional names, accounts and data. Cases marked as concept are not in production yet.',
        })}</p>
      </footer>
    </div>
  )
}
