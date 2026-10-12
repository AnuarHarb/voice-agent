# Cobranza responsable · Avanza Crédito

Voice agent on ElevenLabs Agents that handles early-stage collections in Spanish for a fictional Colombian fintech. It verifies identity, offers only the plans the credit policy allows, and sends the payment link over WhatsApp or Telegram. Two tenants share one template: **Avanza Crédito** (WhatsApp) and **Nexo Finanzas** (Telegram).

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

With `CHANNEL_MODE=log`, payment links are printed in the logs instead of being sent. Use `live` once WhatsApp or Telegram credentials are set. The link opens `/pay/<token>`, a simulated checkout page.

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
