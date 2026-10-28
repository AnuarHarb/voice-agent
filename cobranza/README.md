# Cobranza responsable · Avanza Crédito

Voice agents on ElevenLabs for fictional Colombian fintech demos. **Banco Avanza** ships five case agents (tarjeta preventiva, libre inversión, vehículo, microcrédito, oferta comercial) on one integration; **Nexo Finanzas** stays a second tenant for isolation. Policy is per product (`product_policies`); contact compliance uses `person_id` and `purpose` (`cobranza` | `comercial`). WhatsApp remains implemented but disabled pending Meta templates.

**Compliance (pending validation):** microcrédito-specific Ley 2300 rules and the commercial do-not-call registry are not automated; the demo applies the general contact window.

This file covers setup and operations. For how the system is split between the client (the fintech's systems), the integration and the agent, see the [root README](../README.md).

```
cobranza/
  backend/              FastAPI (deploys to Railway)
    app/integration/    tools, tenant auth, session tokens, masking, Ley 2300, channels, post-call webhook
    app/fintech_sim/    credit policy, plan calculation, Colombian holidays
    tests/              pytest against the real Supabase database
    scripts/admin.py    tenant keys, demo recipients, agent registration
  supabase/migrations/  schema, RLS, app role, seed data
  agent_configs/        _template.json + one file per fintech
  tool_configs/         one webhook tool per file
  procedure_configs/    structured and free-form procedures
  knowledge_base/       FAQ, Ley 2300, data processing notice
  test_configs/         11 agent tests + named tool mocks
  prompts/              system prompt
  scripts/agents.py     build / validate / push / test
```

## 1. Database (Supabase)

Project `avanza-cobranza` (`thebjscyzczyghbuqtvz`, us-east-1). The migrations in `supabase/migrations/` are already applied. To reproduce them on another project, run `supabase db push` or paste them in order into the SQL editor, then set the password of the app role:

```sql
alter role cobranza_app with password '<strong password>';
```

The backend connects as `cobranza_app`, which has `NOBYPASSRLS`. Each transaction runs `set_config('app.tenant_id', ...)`, and every table filters on `tenant_id = cobranza.current_tenant()`. Use the transaction pooler (port 6543).

Demo customers (seed):

| Tenant | Customer | Last 4 of cédula | Date of birth | Account |
| --- | --- | --- | --- | --- |
| avanza | Laura | 4417 | 1990-05-14 | `acc_avz_0001` (ends 4417, $1.200.000 overdue, 21 days) |
| avanza | Carlos | 5521 | 1985-11-02 | `acc_avz_0002` |
| avanza | Marta | 7788 | 1978-03-30 | `acc_avz_0003` |
| nexo | Andrés | 4417 | 1990-05-14 | `acc_nxo_0001` (same identity as Laura, other tenant) |

More can be created from the console (see section 5).

To receive the payment link on your own phone:

```sh
cd backend
uv run python scripts/admin.py set-recipient acc_avz_0001 --phone +57XXXXXXXXXX
uv run python scripts/admin.py set-recipient acc_nxo_0001 --telegram-chat-id <chat id>
```

## 2. Backend

```sh
cd backend
cp .env.example .env        # fill DATABASE_URL and the rest
uv sync
uv run uvicorn app.main:app --reload
uv run pytest               # 29 tests, hits the real database
```

Railway: create a service with root directory `cobranza/backend` (it uses `Dockerfile` and `railway.json`, health check `/health`), generate a public domain, and set the variables from `backend/.env.example`. Do not put `TENANT_KEY_*` or `DATABASE_ADMIN_URL` in Railway: the backend only stores key hashes.

With `CHANNEL_MODE=log`, payment links are printed in the logs instead of being sent. Use `live` once `TELEGRAM_BOT_TOKEN` is set and the customer's `telegram_chat_id` is in the vault (`scripts/admin.py set-recipient`). The link opens `/pay/<token>`, a simulated checkout page.

## 3. Agent (ElevenLabs)

```sh
cp .env.example .env                                        # ELEVENLABS_API_KEY, BACKEND_URL
uv run --project backend python scripts/agents.py build     # offline: render + validate against the ElevenLabs OpenAPI
uv run --project backend python scripts/agents.py push      # create or update everything
uv run --project backend python scripts/agents.py test      # run the 11 tests on every agent
npx elevenlabs agents test <agent_id>                       # the CLI works on the same agents
uv run --project backend python scripts/agents.py voices    # find a Colombian female voice
```

`push` creates, per tenant: the workspace secret holding the tenant key, the 8 webhook tools, the KB documents, the tests, the agent, the procedures (in dependency order) and the published version. The first run also creates the post-call webhook and prints its HMAC secret once: copy it to `POST_CALL_WEBHOOK_SECRET` in Railway. If `DATABASE_ADMIN_URL` is set, it registers each `agent_id` in `cobranza.tenant_agents`. Otherwise it prints the command to run:

```sh
uv run python backend/scripts/admin.py register-agent avanza <agent_id>
```

IDs live in `deploy_state.json`, so running `push` again updates the existing resources instead of duplicating them. The script exists because the CLI's `agents push` does not cover procedures, workspace secrets or per-tenant tool sets. `build/` holds the exact payloads that are sent.

Placeholders in the configs use `${...}`: `${env:NAME:default}`, `${file:path}`, `${tool:name}`, `${procedure:name}`, `${kb:name}`. `{{...}}` is left for ElevenLabs dynamic variables at runtime.

### Design notes

- The session token is returned by `verify_identity` into the `secret__session_token` dynamic variable through a sanitized assignment. Later tools read it from there, so the LLM never sees it.
- Each tenant has its own tool set with its own header secret. `X-Tenant-Id` is fixed per agent, and the backend rejects a mismatch and logs it in `audit_log`.
- A `plan_id` is only accepted if it was offered to the same session. `idempotency_key` is the conversation id, so a repeated confirmation does not create a second plan.
- The native `retry` step hangs up when it runs out of attempts. To keep "retry once, then offer a callback", the build generates `reintento_<tool>` sub-procedures that escalate to `escalamiento_falla_tecnica`.
- LLM: `claude-haiku-4-5`, chosen for latency and cost after a real call; `claude-sonnet-5` is the stronger option (the API does not offer `claude-sonnet-5-5`). Change it with `ELEVENLABS_LLM`.

## 4. Isolation demo

```sh
curl -s -X POST $BACKEND_URL/tools/account-summary \
  -H "X-Tenant-Key: $TENANT_KEY_NEXO" -H "Content-Type: application/json" \
  -d '{"session_token":"<Avanza session token>","conversation_id":"demo"}'
# -> 401 invalid_session, and a rejected row in cobranza.audit_log
```

`tests/test_tools_api.py` covers this case, and also an RLS check run directly in Postgres with the app role.

## 5. Back-office console (`dashboard/`)

A React + Vite app that plays the fintech's collections desk: test customers with their ID and birth date,
debts, plans registered by voice, every conversation with the agent's step-by-step audit trail, and open cases.
It refreshes every 10 seconds and switches between tenants.

- Data comes from read-only `GET /console/...` endpoints in the backend (`app/fintech_sim/console.py`).
- They connect as `cobranza_console` (migration `20261012000005`): it may read `pii_vault`, which the voice
  integration role cannot, but RLS still scopes each query to one tenant and the role cannot write.
  Set its password with `alter role cobranza_console password '...'` and put the URL in `CONSOLE_DATABASE_URL`.
- The console has no login and shows full IDs of fictional customers. Do not point it at real data.
- "Agregar cliente al azar" calls `POST /console/{tenant}/customers`, which generates a random fictional customer
  and inserts it through `cobranza.create_demo_customer` (migration `20261012000008`), run as `cobranza_app` inside
  one tenant. The function can only add rows, caps each tenant at 40 accounts, keeps last 4 digits plus birth date
  unique per tenant, and copies the tenant's demo Telegram chat.
- Switching tenant hangs up any live call and clears its transcript.
- The header switches the interface between Spanish and English (`src/i18n.tsx`: both dictionaries share one type,
  so a missing translation fails the build). The choice is saved in the browser; the first visit follows the
  browser language. Only the interface changes: the agents still greet in Spanish and switch if the customer does.
- "Llamada en vivo" calls the agent from the browser with `@elevenlabs/react` and [ElevenLabs UI](https://ui.elevenlabs.io)
  components (Orb, Conversation, Message, ShimmeringText, vendored in `src/components/ui/`). The agents send
  `agent_tool_request` / `agent_tool_response` client events so the transcript shows each tool step. Every call
  spends ElevenLabs credits.

```sh
cd dashboard
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

On Railway: a second service with root directory `cobranza/dashboard` (it builds with its `Dockerfile` and serves
with Caddy), and the variable `VITE_API_URL` set to the backend's public URL.
