-- Commercial catalog: products, product policies, purpose-based contact, credit offers.

-- ---------------------------------------------------------------- products

create table cobranza.products (
  tenant_id     text not null references cobranza.tenants(id),
  product_code  text not null,
  kind          text not null check (kind in ('tarjeta', 'libre_inversion', 'vehiculo', 'microcredito')),
  display_name  text not null,
  primary key (tenant_id, product_code)
);

create table cobranza.product_policies (
  tenant_id     text not null references cobranza.tenants(id),
  product_code  text not null,
  policy        jsonb not null,
  primary key (tenant_id, product_code),
  foreign key (tenant_id, product_code) references cobranza.products(tenant_id, product_code)
);

alter table cobranza.accounts
  add column product_code text,
  add column minimum_payment numeric(14, 0) not null default 0 check (minimum_payment >= 0),
  add column due_date date;

alter table cobranza.contacts
  add column purpose text not null default 'cobranza'
    check (purpose in ('cobranza', 'comercial'));

create index on cobranza.contacts (tenant_id, purpose, contacted_at);

create table cobranza.contact_consents (
  id           bigint generated always as identity primary key,
  tenant_id    text not null references cobranza.tenants(id),
  person_token text not null references cobranza.pii_vault(person_token),
  purpose      text not null check (purpose in ('cobranza', 'comercial')),
  channel      text not null check (channel in ('voice', 'whatsapp', 'telegram', 'sms', 'email')),
  granted_at   timestamptz not null default now(),
  revoked_at   timestamptz
);
create index on cobranza.contact_consents (tenant_id, person_token, purpose, channel);

alter table cobranza.payment_offers drop constraint if exists payment_offers_kind_check;
alter table cobranza.payment_offers add constraint payment_offers_kind_check
  check (kind in ('full', 'installments', 'hardship', 'minimum', 'refinance', 'promise'));

create table cobranza.credit_offers (
  offer_id            text primary key,
  tenant_id           text not null references cobranza.tenants(id),
  person_token        text not null references cobranza.pii_vault(person_token),
  session_token_hash  text references cobranza.sessions(token_hash),
  conversation_id     text,
  amount              numeric(14, 0) not null check (amount > 0),
  rate_ea             numeric(8, 4) not null,
  available_terms     int[] not null,
  status              text not null default 'offered'
    check (status in ('offered', 'accepted', 'rejected', 'expired', 'locked', 'disbursed')),
  expires_at          timestamptz not null,
  disbursement_ref    text unique,
  created_at          timestamptz not null default now()
);

create table cobranza.disbursement_otps (
  offer_id    text primary key references cobranza.credit_offers(offer_id),
  tenant_id   text not null references cobranza.tenants(id),
  code_hash   text not null,
  attempts    int not null default 0 check (attempts >= 0),
  expires_at  timestamptz not null,
  created_at  timestamptz not null default now()
);

-- -------------------------------------------------------- row level security

do $$
declare t text;
begin
  foreach t in array array[
    'products', 'product_policies', 'contact_consents', 'credit_offers', 'disbursement_otps'
  ] loop
    execute format('alter table cobranza.%I enable row level security', t);
    execute format(
      'create policy tenant_isolation on cobranza.%I to cobranza_app
         using (tenant_id = cobranza.current_tenant())
         with check (tenant_id = cobranza.current_tenant())', t);
    execute format('grant select on cobranza.%I to cobranza_app', t);
  end loop;
end
$$;

grant select, insert, update on cobranza.credit_offers to cobranza_app;
grant select, insert, update on cobranza.disbursement_otps to cobranza_app;
grant select, insert on cobranza.contact_consents to cobranza_app;

do $$
declare t text;
begin
  foreach t in array array['products', 'product_policies', 'contact_consents', 'credit_offers']
  loop
    execute format('grant select on cobranza.%I to cobranza_console', t);
    execute format(
      'create policy console_read on cobranza.%I for select to cobranza_console
         using (tenant_id = cobranza.current_tenant())', t);
  end loop;
end
$$;

-- ---------------------------------------------------------------- branding

update cobranza.tenants set name = 'Banco Avanza' where id = 'avanza';

-- ---------------------------------------------------------------- products

insert into cobranza.products (tenant_id, product_code, kind, display_name) values
  ('avanza', 'tarjeta',         'tarjeta',         'Tarjeta de crédito'),
  ('avanza', 'libre_inversion', 'libre_inversion', 'Crédito de libre inversión'),
  ('avanza', 'vehiculo',        'vehiculo',        'Crédito de vehículo'),
  ('avanza', 'microcredito',    'microcredito',    'Microcrédito'),
  ('nexo',   'libre_inversion', 'libre_inversion', 'Crédito de libre inversión');

-- Policy JSON: Ley 2300 hours + options.mode per product.

insert into cobranza.product_policies (tenant_id, product_code, policy) values
  ('avanza', 'libre_inversion', '{
    "timezone": "America/Bogota",
    "weekday_start_hour": 7, "weekday_end_hour": 19,
    "saturday_start_hour": 8, "saturday_end_hour": 15,
    "session_ttl_minutes": 30, "max_verification_attempts": 3,
    "options": {
      "mode": "overdue",
      "max_installments": 3, "min_installment_cop": 150000,
      "first_payment_max_days": 5,
      "hardship_enabled": true, "hardship_installments": 6, "hardship_grace_days": 30
    }
  }'::jsonb),
  ('avanza', 'tarjeta', '{
    "timezone": "America/Bogota",
    "weekday_start_hour": 7, "weekday_end_hour": 19,
    "saturday_start_hour": 8, "saturday_end_hour": 15,
    "session_ttl_minutes": 30, "max_verification_attempts": 3,
    "options": {
      "mode": "card_preventive",
      "refinance_min_balance_cop": 500000,
      "refinance_terms": [6, 12, 24]
    }
  }'::jsonb),
  ('avanza', 'vehiculo', '{
    "timezone": "America/Bogota",
    "weekday_start_hour": 7, "weekday_end_hour": 19,
    "saturday_start_hour": 8, "saturday_end_hour": 15,
    "session_ttl_minutes": 30, "max_verification_attempts": 3,
    "options": {
      "mode": "overdue",
      "max_installments": 2, "min_installment_cop": 150000,
      "first_payment_max_days": 5,
      "hardship_enabled": false, "hardship_installments": 1, "hardship_grace_days": 0,
      "escalate_when_days_past_due_gt": 60
    }
  }'::jsonb),
  ('avanza', 'microcredito', '{
    "timezone": "America/Bogota",
    "weekday_start_hour": 7, "weekday_end_hour": 19,
    "saturday_start_hour": 8, "saturday_end_hour": 15,
    "session_ttl_minutes": 30, "max_verification_attempts": 3,
    "options": {
      "mode": "promise",
      "promise_max_days": 7
    }
  }'::jsonb),
  ('nexo', 'libre_inversion', '{
    "timezone": "America/Bogota",
    "weekday_start_hour": 7, "weekday_end_hour": 19,
    "saturday_start_hour": 8, "saturday_end_hour": 15,
    "session_ttl_minutes": 30, "max_verification_attempts": 3,
    "options": {
      "mode": "overdue",
      "max_installments": 2, "min_installment_cop": 200000,
      "first_payment_max_days": 3,
      "hardship_enabled": false, "hardship_installments": 1, "hardship_grace_days": 0
    }
  }'::jsonb);

-- Backfill existing accounts

update cobranza.accounts set
  product_code = 'libre_inversion',
  product = 'Crédito de libre inversión'
where id in ('acc_avz_0001', 'acc_avz_0002', 'acc_avz_pytest');

update cobranza.accounts set
  product_code = 'vehiculo',
  product = 'Crédito de vehículo'
where id = 'acc_avz_0003';

update cobranza.accounts set
  product_code = 'libre_inversion',
  product = 'Crédito de libre inversión'
where id = 'acc_nxo_0001';

update cobranza.accounts set product_code = case
  when tenant_id = 'nexo' then 'libre_inversion'
  when product ilike '%tarjeta%' then 'tarjeta'
  when product ilike '%vehículo%' or product ilike '%vehiculo%' then 'vehiculo'
  when product ilike '%micro%' then 'microcredito'
  else 'libre_inversion'
end
where product_code is null;

update cobranza.accounts a set product = p.display_name
from cobranza.products p
where p.tenant_id = a.tenant_id and p.product_code = a.product_code
  and a.product_code is not null;

alter table cobranza.accounts alter column product_code set not null;
alter table cobranza.accounts
  add foreign key (tenant_id, product_code) references cobranza.products(tenant_id, product_code);

-- Additional demo customers (fictional)

insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date) values
  ('per_avz_diana',  'avanza', 'Diana Mejía Ortiz',    '52123456',   '1992-08-20'),
  ('per_avz_pablo',  'avanza', 'Pablo Herrera Luna',   '80112233',   '1988-01-11'),
  ('per_avz_sofia',  'avanza', 'Sofía Castaño Ruiz',   '33445566',   '1995-07-07'),
  ('per_avz_luis',   'avanza', 'Luis Ángel Duque',     '66778899',   '1980-12-01'),
  ('per_avz_elena',  'avanza', 'Elena Vargas Prieto',  '11223344',   '1993-04-18'),
  ('per_avz_jorge',  'avanza', 'Jorge Salazar Niño',   '99887766',   '1987-09-25'),
  ('per_avz_camila', 'avanza', 'Camila Ríos Mesa',     '44556677',   '1991-03-03');

insert into cobranza.accounts
  (id, tenant_id, person_token, id_last4, account_last4, product, product_code,
   overdue_amount, total_balance, days_past_due, status, minimum_payment, due_date)
values
  ('acc_avz_tarjeta_01', 'avanza', 'per_avz_diana', '3456', '8821', 'Tarjeta de crédito', 'tarjeta',
   0, 3200000, 0, 'current', 380000, current_date + 3),
  ('acc_avz_tarjeta_paid', 'avanza', 'per_avz_pablo', '2233', '1102', 'Tarjeta de crédito', 'tarjeta',
   0, 890000, 0, 'current', 0, current_date + 10),
  ('acc_avz_veh_75', 'avanza', 'per_avz_sofia', '5566', '7744', 'Crédito de vehículo', 'vehiculo',
   1800000, 12000000, 75, 'active', 0, null),
  ('acc_avz_micro_01', 'avanza', 'per_avz_luis', '8899', '3310', 'Microcrédito', 'microcredito',
   185000, 185000, 8, 'active', 0, null),
  ('acc_avz_elena_tarjeta', 'avanza', 'per_avz_elena', '3344', '2201', 'Tarjeta de crédito', 'tarjeta',
   0, 2100000, 0, 'current', 120000, current_date + 5),
  ('acc_avz_elena_libre', 'avanza', 'per_avz_elena', '3344', '2202', 'Crédito de libre inversión', 'libre_inversion',
   950000, 4100000, 14, 'active', 0, null);

-- Jorge: all products current — commercial offer person
insert into cobranza.accounts
  (id, tenant_id, person_token, id_last4, account_last4, product, product_code,
   overdue_amount, total_balance, days_past_due, status, minimum_payment, due_date)
values
  ('acc_avz_jorge_tarjeta', 'avanza', 'per_avz_jorge', '7766', '9001', 'Tarjeta de crédito', 'tarjeta',
   0, 1500000, 0, 'current', 0, current_date + 20),
  ('acc_avz_jorge_libre', 'avanza', 'per_avz_jorge', '7766', '9002', 'Crédito de libre inversión', 'libre_inversion',
   0, 8000000, 0, 'current', 0, null);

insert into cobranza.credit_offers
  (offer_id, tenant_id, person_token, amount, rate_ea, available_terms, status, expires_at)
values
  ('ofr_avz_jorge_seed', 'avanza', 'per_avz_jorge', 5000000, 24.5, array[12, 24, 36], 'offered', now() + interval '7 days');

insert into cobranza.accounts
  (id, tenant_id, person_token, id_last4, account_last4, product, product_code,
   overdue_amount, total_balance, days_past_due, status, minimum_payment, due_date)
values
  ('acc_avz_camila_libre', 'avanza', 'per_avz_camila', '6677', '4400', 'Crédito de libre inversión', 'libre_inversion',
   0, 5200000, 0, 'current', 0, null);

insert into cobranza.credit_offers
  (offer_id, tenant_id, person_token, amount, rate_ea, available_terms, status, expires_at)
values
  ('ofr_avz_camila_seed', 'avanza', 'per_avz_camila', 3500000, 22.0, array[6, 12, 18], 'offered', now() + interval '7 days');

insert into cobranza.contact_consents (tenant_id, person_token, purpose, channel)
select distinct tenant_id, person_token, 'cobranza', 'voice' from cobranza.pii_vault where tenant_id = 'avanza';
insert into cobranza.contact_consents (tenant_id, person_token, purpose, channel)
select distinct tenant_id, person_token, 'cobranza', 'voice' from cobranza.pii_vault where tenant_id = 'nexo';
insert into cobranza.contact_consents (tenant_id, person_token, purpose, channel) values
  ('avanza', 'per_avz_jorge', 'comercial', 'voice'),
  ('avanza', 'per_avz_camila', 'comercial', 'voice');

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
  v_person text;
  v_code text;
  v_kind text;
begin
  if v_tenant is null then
    raise exception 'no tenant in context';
  end if;
  if (select count(*) from cobranza.accounts where tenant_id = v_tenant) >= 40 then
    raise exception 'demo customer limit reached' using errcode = 'P0001';
  end if;
  if exists (select 1 from cobranza.accounts a join cobranza.pii_vault v on v.person_token = a.person_token
             where a.tenant_id = v_tenant and a.id_last4 = v_last4 and v.birth_date = p_birth_date) then
    raise exception 'identity already in use' using errcode = '23505';
  end if;

  v_code := case p_product
    when 'Tarjeta de crédito' then 'tarjeta'
    when 'Crédito de vehículo' then 'vehiculo'
    when 'Microcrédito' then 'microcredito'
    else 'libre_inversion'
  end;

  v_person := 'per_' || v_tenant || '_' || v_suffix;
  insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date, telegram_chat_id)
  values (v_person, v_tenant, p_full_name, p_national_id, p_birth_date,
          (select telegram_chat_id from cobranza.pii_vault
            where tenant_id = v_tenant and telegram_chat_id is not null limit 1));

  insert into cobranza.contact_consents (tenant_id, person_token, purpose, channel)
  values (v_tenant, v_person, 'cobranza', 'voice');

  v_account := 'acc_' || v_tenant || '_' || v_suffix;
  insert into cobranza.accounts
    (id, tenant_id, person_token, id_last4, account_last4, product, product_code,
     overdue_amount, total_balance, days_past_due, status, minimum_payment, due_date)
  values (
    v_account, v_tenant, v_person, v_last4,
    lpad((floor(random() * 10000))::int::text, 4, '0'), p_product, v_code,
    p_overdue_amount, p_total_balance, p_days_past_due,
    case when p_days_past_due = 0 then 'current' else 'active' end,
    case when v_code = 'tarjeta' and p_days_past_due = 0 then greatest(50000, p_overdue_amount) else 0 end,
    case when v_code = 'tarjeta' and p_days_past_due = 0 then current_date + 5 else null end
  );
  return v_account;
end
$$;
