alter function cobranza.current_tenant() set search_path = pg_catalog, pg_temp;

-- tenants and tenant_agents keep RLS enabled with no policy on purpose: the app role
-- reaches them only through the security definer functions resolve_tenant and tenant_by_agent.
comment on table cobranza.tenants is 'Deny-all RLS by design; read via cobranza.resolve_tenant().';
comment on table cobranza.tenant_agents is 'Deny-all RLS by design; read via cobranza.tenant_by_agent().';
