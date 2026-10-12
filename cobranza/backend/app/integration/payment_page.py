"""Simulated checkout behind the link sent by WhatsApp or Telegram.
In a real deployment this is the fintech's existing payment gateway."""

from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.db import connection
from app.integration.formatting import date_text, money_text

router = APIRouter(prefix="/pay", tags=["payment page"])

_STYLE = """
:root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { margin: 0; min-height: 100dvh; display: grid; place-items: center; background: Canvas; }
main { width: min(28rem, 100% - 2rem); padding: 2rem 0; }
header p { margin: 0; opacity: .7; font-size: .9rem; }
h1 { margin: .25rem 0 1.5rem; font-size: 1.5rem; text-wrap: balance; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .5rem 1rem; margin: 0 0 1.5rem; }
dt { opacity: .7; } dd { margin: 0; font-variant-numeric: tabular-nums; text-align: end; }
button { width: 100%; padding: .9rem; font: inherit; font-weight: 600; border-radius: .6rem;
         border: 0; background: #0b6b4f; color: white; cursor: pointer; }
button:focus-visible { outline: 3px solid #f0b429; outline-offset: 2px; }
footer { margin-top: 1.5rem; font-size: .8rem; opacity: .7; }
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
{body}
<footer><p>Pago simulado para la demo. No se procesa dinero real.</p></footer>
</main>
</body>
</html>"""
    )


async def _load(link_token: str):
    async with connection() as conn:
        return await conn.fetchrow("select * from cobranza.payment_link_view($1)", link_token)


def _not_available() -> HTMLResponse:
    response = _page("Link no disponible", "<h1>Este link de pago no está disponible</h1>"
                                         "<p>Puede haber vencido. Comunícate con tu entidad.</p>")
    response.status_code = 404
    return response


@router.get("/{link_token}", response_class=HTMLResponse)
async def show(link_token: str) -> HTMLResponse:
    view = await _load(link_token)
    if view is None or view["expires_at"] < datetime.now(timezone.utc):
        return _not_available()
    tenant = escape(view["tenant_name"])
    amount = money_text(view["installment_amount"])
    installments = (f"{view['installments']} cuotas de {amount}" if view["installments"] > 1 else amount)
    paid = view["plan_status"] == "paid"
    action = ("<p role=\"status\">Este plan ya está pagado. Gracias.</p>" if paid else
              f"""<form method="post" action="/pay/{escape(link_token)}">
  <button type="submit">Pagar {amount}</button>
</form>""")
    return _page(
        f"Pago {tenant}",
        f"""<header>
  <p>{tenant}</p>
  <h1>Tu plan de pago {escape(view['plan_ref'])}</h1>
</header>
<section aria-label="Detalle del plan">
  <dl>
    <dt>Cuenta</dt><dd>terminada en {escape(view['account_last4'])}</dd>
    <dt>Plan</dt><dd>{installments}</dd>
    <dt>Total</dt><dd>{money_text(view['total_amount'])}</dd>
    <dt>Primera fecha</dt><dd><time datetime="{view['first_due_date'].isoformat()}">{date_text(view['first_due_date'])}</time></dd>
  </dl>
  {action}
</section>""",
    )


@router.post("/{link_token}", response_class=HTMLResponse)
async def pay(link_token: str) -> HTMLResponse:
    async with connection() as conn:
        ok = await conn.fetchval("select cobranza.confirm_simulated_payment($1)", link_token)
    if not ok:
        return _not_available()
    view = await _load(link_token)
    return _page(
        "Pago recibido",
        f"""<header>
  <p>{escape(view['tenant_name'])}</p>
  <h1>Pago recibido</h1>
</header>
<p role="status">Registramos el pago de tu plan {escape(view['plan_ref'])}. Gracias por ponerte al día.</p>""",
    )
