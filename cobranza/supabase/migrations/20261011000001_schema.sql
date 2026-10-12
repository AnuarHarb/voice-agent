-- Avanza Crédito collections: multi-tenant schema with row level security.
-- The backend connects as cobranza_app (no BYPASSRLS, not table owner) and pins
-- the tenant per transaction with set_config('app.tenant_id', ..., true).

create schema if not exists cobranza;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'cobranza_app') then
    create role cobranza_app login nobypassrls noinherit nocreatedb nocreaterole;
  end if;
end
$$;

alter role cobranza_app set search_path = cobranza, public;
alter role cobranza_app set statement_timeout = '10s';

revoke all on schema cobranza from public;
grant usage on schema cobranza to cobranza_app;

create or replace function cobranza.current_tenant() returns text
language sql stable
as $$ select nullif(current_setting('app.tenant_id', true), '') $$;

-- ---------------------------------------------------------------- tenants

create table cobranza.tenants (
  id          text primary key,
  name        text not null,
  key_hash    text unique,
  channel     text not null check (channel in ('whatsapp', 'telegram')),
  agent_id    text unique,
  created_at  timestamptz not null default now()
);

create table cobranza.tenant_policies (
  tenant_id                text primary key references cobranza.tenants(id),
  max_installments         int  not null check (max_installments between 1 and 12),
  min_installment_cop      int  not null check (min_installment_cop > 0),
  first_payment_max_days   int  not null check (first_payment_max_days between 1 and 30),
  hardship_enabled         boolean not null default true,
  hardship_installments    int  not null default 6,
  hardship_grace_days      int  not null default 30,
  timezone                 text not null default 'America/Bogota',
  -- Ley 2300 de 2023: Mon-Fri 07-19, Sat 08-15, never Sundays or holidays.
  weekday_start_hour       int  not null default 7,
  weekday_end_hour         int  not null default 19,
  saturday_start_hour      int  not null default 8,
  saturday_end_hour        int  not null default 15,
  session_ttl_minutes      int  not null default 30,
  max_verification_attempts int not null default 3
);

-- ------------------------------------------------------------ fintech data

create table cobranza.pii_vault (
  person_token      text primary key,
  tenant_id         text not null references cobranza.tenants(id),
  full_name         text not null,
  national_id       text not null,
  birth_date        date not null,
  phone_e164        text,
  telegram_chat_id  text,
  unique (tenant_id, national_id)
);

create table cobranza.accounts (
  id              text primary key,
  tenant_id       text not null references cobranza.tenants(id),
  person_token    text not null references cobranza.pii_vault(person_token),
  id_last4        char(4) not null,
  account_last4   char(4) not null,
  product         text not null,
  overdue_amount  numeric(14, 0) not null check (overdue_amount >= 0),
  total_balance   numeric(14, 0) not null check (total_balance >= overdue_amount),
  days_past_due   int not null check (days_past_due >= 0),
  status          text not null default 'active' check (status in ('active', 'in_dispute', 'current')),
  created_at      timestamptz not null default now()
);
create index on cobranza.accounts (tenant_id, id_last4);

-- ------------------------------------------------------- integration state

create table cobranza.sessions (
  token_hash       text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  account_id       text not null references cobranza.accounts(id),
  conversation_id  text,
  expires_at       timestamptz not null,
  created_at       timestamptz not null default now()
);

create table cobranza.payment_offers (
  plan_id               text primary key,
  tenant_id             text not null references cobranza.tenants(id),
  session_token_hash    text not null references cobranza.sessions(token_hash),
  account_id            text not null references cobranza.accounts(id),
  kind                  text not null check (kind in ('full', 'installments', 'hardship')),
  installments          int not null check (installments >= 1),
  installment_amount    numeric(14, 0) not null,
  last_installment_amount numeric(14, 0) not null,
  total_amount          numeric(14, 0) not null,
  first_due_date        date not null,
  hardship              boolean not null,
  created_at            timestamptz not null default now()
);

create table cobranza.payment_plans (
  plan_ref            text primary key,
  tenant_id           text not null references cobranza.tenants(id),
  account_id          text not null references cobranza.accounts(id),
  plan_id             text not null references cobranza.payment_offers(plan_id),
  idempotency_key     text not null,
  status              text not null default 'pending_payment'
                        check (status in ('pending_payment', 'paid', 'cancelled')),
  installments        int not null,
  installment_amount  numeric(14, 0) not null,
  total_amount        numeric(14, 0) not null,
  first_due_date      date not null,
  hardship            boolean not null,
  conversation_id     text,
  created_at          timestamptz not null default now(),
  unique (tenant_id, idempotency_key)
);

create table cobranza.payment_links (
  link_token   text primary key,
  tenant_id    text not null references cobranza.tenants(id),
  plan_ref     text not null unique references cobranza.payment_plans(plan_ref),
  channel      text not null,
  status       text not null default 'pending' check (status in ('pending', 'sent', 'failed', 'paid')),
  message_id   text,
  sent_at      timestamptz,
  expires_at   timestamptz not null,
  created_at   timestamptz not null default now()
);

create table cobranza.contacts (
  id               bigint generated always as identity primary key,
  tenant_id        text not null references cobranza.tenants(id),
  account_id       text references cobranza.accounts(id),
  phone_hash       text,
  channel          text not null check (channel in ('voice', 'whatsapp', 'telegram', 'sms', 'email')),
  direction        text not null default 'inbound' check (direction in ('inbound', 'outbound')),
  result           text not null,
  opt_out          boolean not null default false,
  conversation_id  text,
  contacted_at     timestamptz not null default now()
);
create index on cobranza.contacts (tenant_id, account_id, contacted_at);

create table cobranza.disputes (
  case_ref         text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  account_id       text not null references cobranza.accounts(id),
  reason           text not null,
  status           text not null default 'open' check (status in ('open', 'resolved')),
  conversation_id  text,
  created_at       timestamptz not null default now()
);

create table cobranza.callbacks (
  callback_ref      text primary key,
  tenant_id         text not null references cobranza.tenants(id),
  account_id        text references cobranza.accounts(id),
  reason            text not null,
  preferred_window  text not null,
  status            text not null default 'pending' check (status in ('pending', 'done')),
  conversation_id   text,
  created_at        timestamptz not null default now()
);

create table cobranza.call_outcomes (
  conversation_id  text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  agent_id         text not null,
  outcome          text,
  promise_amount   numeric(14, 0),
  promise_date     date,
  late_reason      text,
  hardship         boolean,
  language         text,
  call_successful  text,
  evaluation       jsonb not null default '{}'::jsonb,
  duration_secs    int,
  received_at      timestamptz not null default now()
);

create table cobranza.audit_log (
  id               bigint generated always as identity primary key,
  tenant_id        text not null references cobranza.tenants(id),
  conversation_id  text,
  tool             text not null,
  result           text not null,
  detail           jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now()
);
create index on cobranza.audit_log (tenant_id, conversation_id, tool);

-- -------------------------------------------------------- row level security

do $$
declare t text;
begin
  foreach t in array array[
    'tenant_policies', 'pii_vault', 'accounts', 'sessions', 'payment_offers',
    'payment_plans', 'payment_links', 'contacts', 'disputes', 'callbacks',
    'call_outcomes', 'audit_log'
  ] loop
    execute format('alter table cobranza.%I enable row level security', t);
    execute format(
      'create policy tenant_isolation on cobranza.%I to cobranza_app
         using (tenant_id = cobranza.current_tenant())
         with check (tenant_id = cobranza.current_tenant())', t);
  end loop;
end
$$;

alter table cobranza.tenants enable row level security;

-- The app role never reads tenants or the vault directly.
grant select on cobranza.tenant_policies to cobranza_app;
grant select, update (overdue_amount, status) on cobranza.accounts to cobranza_app;
grant select, insert, delete on cobranza.sessions to cobranza_app;
grant select, insert on cobranza.payment_offers to cobranza_app;
grant select, insert, update (status) on cobranza.payment_plans to cobranza_app;
grant select, insert, update (status, message_id, sent_at) on cobranza.payment_links to cobranza_app;
grant select, insert on cobranza.contacts to cobranza_app;
grant select, insert on cobranza.disputes to cobranza_app;
grant select, insert on cobranza.callbacks to cobranza_app;
grant select, insert, update on cobranza.call_outcomes to cobranza_app;
grant select, insert on cobranza.audit_log to cobranza_app;

-- ------------------------------------------------- security definer gateways

create or replace function cobranza.resolve_tenant(p_key_hash text)
returns table (id text, name text, channel text)
language sql stable security definer set search_path = cobranza, pg_temp
as $$ select t.id, t.name, t.channel from cobranza.tenants t where t.key_hash = p_key_hash $$;

create or replace function cobranza.tenant_by_agent(p_agent_id text)
returns table (id text, name text)
language sql stable security definer set search_path = cobranza, pg_temp
as $$ select t.id, t.name from cobranza.tenants t where t.agent_id = p_agent_id $$;

-- Matches identity inside the caller's tenant only and returns account ids,
-- never vault fields.
create or replace function cobranza.match_identity(p_id_last4 text, p_birth_date date)
returns table (account_id text, first_name text)
language plpgsql stable security definer set search_path = cobranza, pg_temp
as $$
declare v_tenant text := cobranza.current_tenant();
begin
  if v_tenant is null then
    raise exception 'tenant context missing';
  end if;
  return query
    select a.id, split_part(v.full_name, ' ', 1)
    from cobranza.accounts a
    join cobranza.pii_vault v on v.person_token = a.person_token and v.tenant_id = a.tenant_id
    where a.tenant_id = v_tenant
      and right(v.national_id, 4) = p_id_last4
      and v.birth_date = p_birth_date;
end
$$;

create or replace function cobranza.first_name_for_account(p_account_id text)
returns text
language sql stable security definer set search_path = cobranza, pg_temp
as $$
  select split_part(v.full_name, ' ', 1)
  from cobranza.accounts a
  join cobranza.pii_vault v on v.person_token = a.person_token
  where a.id = p_account_id and a.tenant_id = cobranza.current_tenant()
$$;

create or replace function cobranza.recipient_for_account(p_account_id text)
returns table (phone_e164 text, telegram_chat_id text)
language sql stable security definer set search_path = cobranza, pg_temp
as $$
  select v.phone_e164, v.telegram_chat_id
  from cobranza.accounts a
  join cobranza.pii_vault v on v.person_token = a.person_token
  where a.id = p_account_id and a.tenant_id = cobranza.current_tenant()
$$;

create or replace function cobranza.accounts_for_phone(p_phone_e164 text)
returns table (account_id text)
language sql stable security definer set search_path = cobranza, pg_temp
as $$
  select a.id
  from cobranza.accounts a
  join cobranza.pii_vault v on v.person_token = a.person_token
  where v.phone_e164 = p_phone_e164 and a.tenant_id = cobranza.current_tenant()
$$;

-- Public payment page: resolves a link token without a tenant key.
create or replace function cobranza.payment_link_view(p_link_token text)
returns table (
  tenant_name text, plan_ref text, account_last4 text, installments int,
  installment_amount numeric, total_amount numeric, first_due_date date,
  hardship boolean, link_status text, plan_status text, expires_at timestamptz
)
language sql stable security definer set search_path = cobranza, pg_temp
as $$
  select t.name, p.plan_ref, a.account_last4::text, p.installments, p.installment_amount,
         p.total_amount, p.first_due_date, p.hardship, l.status, p.status, l.expires_at
  from cobranza.payment_links l
  join cobranza.payment_plans p on p.plan_ref = l.plan_ref
  join cobranza.accounts a on a.id = p.account_id
  join cobranza.tenants t on t.id = l.tenant_id
  where l.link_token = p_link_token
$$;

create or replace function cobranza.confirm_simulated_payment(p_link_token text)
returns boolean
language plpgsql volatile security definer set search_path = cobranza, pg_temp
as $$
declare v_plan text; v_tenant text;
begin
  select l.plan_ref, l.tenant_id into v_plan, v_tenant
  from cobranza.payment_links l
  where l.link_token = p_link_token and l.expires_at > now() and l.status in ('sent', 'pending');
  if v_plan is null then
    return false;
  end if;
  update cobranza.payment_links set status = 'paid' where link_token = p_link_token;
  update cobranza.payment_plans set status = 'paid' where plan_ref = v_plan;
  insert into cobranza.audit_log (tenant_id, tool, result, detail)
  values (v_tenant, 'payment_page', 'simulated_payment', jsonb_build_object('plan_ref', v_plan));
  return true;
end
$$;

revoke all on all functions in schema cobranza from public;
grant execute on function
  cobranza.current_tenant(),
  cobranza.resolve_tenant(text),
  cobranza.tenant_by_agent(text),
  cobranza.match_identity(text, date),
  cobranza.first_name_for_account(text),
  cobranza.recipient_for_account(text),
  cobranza.accounts_for_phone(text),
  cobranza.payment_link_view(text),
  cobranza.confirm_simulated_payment(text)
to cobranza_app;
