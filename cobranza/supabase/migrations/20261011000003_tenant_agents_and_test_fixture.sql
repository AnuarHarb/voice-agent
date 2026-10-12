-- Several ElevenLabs agents can belong to one tenant (production agent, test agent, branches).

create table cobranza.tenant_agents (
  agent_id   text primary key,
  tenant_id  text not null references cobranza.tenants(id),
  label      text not null default 'production',
  created_at timestamptz not null default now()
);
alter table cobranza.tenant_agents enable row level security;

insert into cobranza.tenant_agents (agent_id, tenant_id, label)
select agent_id, id, 'production' from cobranza.tenants where agent_id is not null;

alter table cobranza.tenants drop column agent_id;

create or replace function cobranza.tenant_by_agent(p_agent_id text)
returns table (id text, name text)
language sql stable security definer set search_path = cobranza, pg_temp
as $$
  select t.id, t.name
  from cobranza.tenant_agents ta
  join cobranza.tenants t on t.id = ta.tenant_id
  where ta.agent_id = p_agent_id
$$;

revoke all on function cobranza.tenant_by_agent(text) from public;
grant execute on function cobranza.tenant_by_agent(text) to cobranza_app;

-- Fixture used only by the automated backend tests, so they never touch demo customers.
insert into cobranza.tenant_agents (agent_id, tenant_id, label) values
  ('agent_pytest_avanza', 'avanza', 'pytest');

insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date) values
  ('per_avz_pytest', 'avanza', 'Prueba Automatizada', '900000001', '2000-01-01');

insert into cobranza.accounts
  (id, tenant_id, person_token, id_last4, account_last4, product,
   overdue_amount, total_balance, days_past_due)
values
  ('acc_avz_pytest', 'avanza', 'per_avz_pytest', '0001', '0001', 'Crédito de consumo', 600000, 1800000, 15);
