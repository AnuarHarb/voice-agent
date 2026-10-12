-- Read-only role for the fintech's back-office console. Unlike cobranza_app (the voice
-- integration), it may read the vault: it plays the fintech's own staff, not the agent.
-- Row level security still pins every query to one tenant. Set its password out of band:
--   alter role cobranza_console password '...';

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'cobranza_console') then
    create role cobranza_console login nobypassrls noinherit nocreatedb nocreaterole;
  end if;
end
$$;

alter role cobranza_console set search_path = cobranza, public;
alter role cobranza_console set statement_timeout = '10s';
alter role cobranza_console set default_transaction_read_only = on;

grant usage on schema cobranza to cobranza_console;
grant execute on function cobranza.current_tenant() to cobranza_console;

-- Sessions and payment offers are left out: they hold token hashes the console never needs.
do $$
declare t text;
begin
  foreach t in array array[
    'tenant_policies', 'pii_vault', 'accounts', 'payment_plans', 'payment_links', 'contacts',
    'disputes', 'callbacks', 'call_outcomes', 'audit_log', 'tenant_agents'
  ] loop
    execute format('grant select on cobranza.%I to cobranza_console', t);
    execute format(
      'create policy console_read on cobranza.%I for select to cobranza_console
         using (tenant_id = cobranza.current_tenant())', t);
  end loop;
end
$$;

grant select (id, name, channel) on cobranza.tenants to cobranza_console;
create policy console_list on cobranza.tenants for select to cobranza_console using (true);
