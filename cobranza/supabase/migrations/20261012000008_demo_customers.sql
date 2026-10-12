-- Fictitious customers created from the console. The console role stays read-only:
-- the backend calls this gateway as cobranza_app inside one tenant, and it can only
-- add a person and an account to that tenant, never touch existing rows.
create or replace function cobranza.create_demo_customer(
  p_full_name text, p_national_id text, p_birth_date date, p_product text,
  p_overdue_amount numeric, p_total_balance numeric, p_days_past_due int
) returns text
language plpgsql security definer set search_path = cobranza, pg_temp
as $$
declare
  v_tenant text := cobranza.current_tenant();
  v_suffix text := substr(md5(random()::text), 1, 8);
  v_last4  text := right(p_national_id, 4);
  v_account text;
begin
  if v_tenant is null then
    raise exception 'no tenant in context';
  end if;
  if (select count(*) from cobranza.accounts where tenant_id = v_tenant) >= 40 then
    raise exception 'demo customer limit reached' using errcode = 'P0001';
  end if;
  -- Identity is matched on last four digits plus birth date, so they must stay unique per tenant.
  if exists (select 1 from cobranza.accounts a join cobranza.pii_vault v on v.person_token = a.person_token
             where a.tenant_id = v_tenant and a.id_last4 = v_last4 and v.birth_date = p_birth_date) then
    raise exception 'identity already in use' using errcode = '23505';
  end if;

  insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date, telegram_chat_id)
  values ('per_' || v_tenant || '_' || v_suffix, v_tenant, p_full_name, p_national_id, p_birth_date,
          (select telegram_chat_id from cobranza.pii_vault
            where tenant_id = v_tenant and telegram_chat_id is not null limit 1));

  v_account := 'acc_' || v_tenant || '_' || v_suffix;
  insert into cobranza.accounts
    (id, tenant_id, person_token, id_last4, account_last4, product, overdue_amount, total_balance, days_past_due)
  values (v_account, v_tenant, 'per_' || v_tenant || '_' || v_suffix, v_last4,
          lpad((floor(random() * 10000))::int::text, 4, '0'), p_product,
          p_overdue_amount, p_total_balance, p_days_past_due);
  return v_account;
end
$$;

revoke all on function cobranza.create_demo_customer(text, text, date, text, numeric, numeric, int) from public;
grant execute on function cobranza.create_demo_customer(text, text, date, text, numeric, numeric, int) to cobranza_app;
