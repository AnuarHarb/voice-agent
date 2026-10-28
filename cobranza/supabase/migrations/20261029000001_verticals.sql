-- Vertical demos beyond collections: healthcare, retail, telecom and real estate.
-- One tenant ("demos") hosts all of them; each agent is branded as a fictional company.
-- All people, orders, plans and properties are fictional.

insert into cobranza.tenants (id, name, channel) values ('demos', 'Inmercity Demos', 'telegram');

-- ------------------------------------------------------------ shared identity

create table cobranza.vertical_customers (
  id                   text primary key,
  tenant_id            text not null references cobranza.tenants(id),
  vertical             text not null check (vertical in ('salud', 'retail', 'telco')),
  person_token         text not null references cobranza.pii_vault(person_token),
  id_last4             char(4) not null,
  consent_commercial   boolean not null default false
);
create index on cobranza.vertical_customers (tenant_id, vertical, id_last4);

create table cobranza.vertical_sessions (
  token_hash       text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  customer_id      text not null references cobranza.vertical_customers(id),
  conversation_id  text,
  expires_at       timestamptz not null,
  created_at       timestamptz not null default now()
);

create table cobranza.handoffs (
  ref              text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  customer_id      text references cobranza.vertical_customers(id),
  conversation_id  text,
  reason           text not null,
  created_at       timestamptz not null default now()
);

create table cobranza.notifications (
  id           bigint generated always as identity primary key,
  tenant_id    text not null references cobranza.tenants(id),
  customer_id  text references cobranza.vertical_customers(id),
  kind         text not null check (kind in ('appointment_reminder', 'return_label', 'checkout_link')),
  reference    text not null,
  status       text not null default 'simulated',
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------- healthcare

create table cobranza.clinic_specialists (
  id         text primary key,
  tenant_id  text not null references cobranza.tenants(id),
  name       text not null,
  specialty  text not null
);

create table cobranza.clinic_slots (
  id             text primary key,
  tenant_id      text not null references cobranza.tenants(id),
  specialist_id  text not null references cobranza.clinic_specialists(id),
  starts_at      timestamptz not null,
  taken          boolean not null default false
);
create index on cobranza.clinic_slots (tenant_id, starts_at);

create table cobranza.appointments (
  ref          text primary key,
  tenant_id    text not null references cobranza.tenants(id),
  customer_id  text not null references cobranza.vertical_customers(id),
  slot_id      text not null references cobranza.clinic_slots(id),
  status       text not null default 'booked' check (status in ('booked', 'cancelled')),
  created_at   timestamptz not null default now()
);

-- -------------------------------------------------------------------- retail

create table cobranza.orders (
  order_no         text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  customer_id      text not null references cobranza.vertical_customers(id),
  status           text not null check (status in ('preparing', 'shipped', 'out_for_delivery', 'delivered')),
  carrier          text,
  -- Offsets from today keep the demo data fresh: an ETA is never in the past.
  eta_offset_days  int,
  delivered_days_ago int,
  items            text not null,
  total            numeric(14, 0) not null
);

create table cobranza.order_returns (
  ref         text primary key,
  tenant_id   text not null references cobranza.tenants(id),
  order_no    text not null references cobranza.orders(order_no),
  reason      text not null,
  created_at  timestamptz not null default now()
);

create table cobranza.carts (
  id           text primary key,
  tenant_id    text not null references cobranza.tenants(id),
  customer_id  text not null references cobranza.vertical_customers(id),
  items        text not null,
  total        numeric(14, 0) not null,
  status       text not null default 'open' check (status in ('open', 'link_sent', 'recovered', 'declined'))
);

-- ------------------------------------------------------------------- telecom

create table cobranza.telco_services (
  id             text primary key,
  tenant_id      text not null references cobranza.tenants(id),
  customer_id    text not null references cobranza.vertical_customers(id),
  plan           text not null,
  monthly_price  numeric(14, 0) not null,
  area           text not null,
  modem_state    text not null default 'ok' check (modem_state in ('ok', 'unresponsive')),
  status         text not null default 'active' check (status in ('active', 'cancelling')),
  applied_offer  text
);

create table cobranza.telco_outages (
  tenant_id    text not null references cobranza.tenants(id),
  area         text not null,
  active       boolean not null,
  description  text not null,
  primary key (tenant_id, area)
);

create table cobranza.telco_tickets (
  ref          text primary key,
  tenant_id    text not null references cobranza.tenants(id),
  customer_id  text not null references cobranza.vertical_customers(id),
  issue        text not null,
  created_at   timestamptz not null default now()
);

create table cobranza.retention_offers (
  id            text primary key,
  tenant_id     text not null references cobranza.tenants(id),
  reason        text not null check (reason in ('precio', 'falla', 'necesidad')),
  headline      text not null,
  discount_pct  int not null check (discount_pct between 0 and 50),
  months        int not null check (months between 1 and 12)
);

create table cobranza.cancellations (
  ref             text primary key,
  tenant_id       text not null references cobranza.tenants(id),
  customer_id     text not null references cobranza.vertical_customers(id),
  reason          text not null,
  effective_date  date not null,
  created_at      timestamptz not null default now()
);

-- --------------------------------------------------------------- real estate

create table cobranza.properties (
  id         text primary key,
  tenant_id  text not null references cobranza.tenants(id),
  title      text not null,
  zone       text not null,
  bedrooms   int not null,
  price      numeric(14, 0) not null,
  kind       text not null check (kind in ('venta', 'arriendo'))
);

create table cobranza.re_leads (
  id               text primary key,
  tenant_id        text not null references cobranza.tenants(id),
  conversation_id  text not null,
  name             text not null,
  zone             text,
  budget           numeric(14, 0),
  bedrooms         int,
  timeline         text,
  score            text not null check (score in ('alto', 'medio', 'bajo')),
  created_at       timestamptz not null default now(),
  unique (tenant_id, conversation_id)
);

create table cobranza.advisor_slots (
  id         text primary key,
  tenant_id  text not null references cobranza.tenants(id),
  advisor    text not null,
  starts_at  timestamptz not null,
  taken      boolean not null default false
);
create index on cobranza.advisor_slots (tenant_id, starts_at);

create table cobranza.advisor_bookings (
  ref         text primary key,
  tenant_id   text not null references cobranza.tenants(id),
  lead_id     text not null references cobranza.re_leads(id),
  slot_id     text not null references cobranza.advisor_slots(id),
  created_at  timestamptz not null default now()
);

-- -------------------------------------------------------- row level security

do $$
declare t text;
begin
  foreach t in array array[
    'vertical_customers', 'vertical_sessions', 'handoffs', 'notifications',
    'clinic_specialists', 'clinic_slots', 'appointments',
    'orders', 'order_returns', 'carts',
    'telco_services', 'telco_outages', 'telco_tickets', 'retention_offers', 'cancellations',
    'properties', 're_leads', 'advisor_slots', 'advisor_bookings'
  ] loop
    execute format('alter table cobranza.%I enable row level security', t);
    execute format(
      'create policy tenant_isolation on cobranza.%I to cobranza_app
         using (tenant_id = cobranza.current_tenant())
         with check (tenant_id = cobranza.current_tenant())', t);
    execute format(
      'create policy console_read on cobranza.%I for select to cobranza_console
         using (tenant_id = cobranza.current_tenant())', t);
    execute format('grant select on cobranza.%I to cobranza_app, cobranza_console', t);
  end loop;
end
$$;

grant insert, delete on cobranza.vertical_sessions to cobranza_app;
grant insert on cobranza.handoffs, cobranza.notifications, cobranza.order_returns,
  cobranza.telco_tickets, cobranza.cancellations, cobranza.re_leads,
  cobranza.advisor_bookings, cobranza.appointments to cobranza_app;
grant update (status) on cobranza.appointments to cobranza_app;
grant update (taken) on cobranza.clinic_slots, cobranza.advisor_slots to cobranza_app;
grant update (status) on cobranza.carts to cobranza_app;
grant update (status, applied_offer) on cobranza.telco_services to cobranza_app;
grant update (consent_commercial) on cobranza.vertical_customers to cobranza_app;
grant update (name, zone, budget, bedrooms, timeline, score) on cobranza.re_leads to cobranza_app;

-- ------------------------------------------------------- security definer gateways

-- Matches identity inside the caller's tenant and vertical; returns ids, never vault fields.
create or replace function cobranza.match_vertical_customer(p_vertical text, p_id_last4 text, p_birth_date date)
returns table (customer_id text, first_name text)
language plpgsql stable security definer set search_path = cobranza, pg_temp
as $$
declare v_tenant text := cobranza.current_tenant();
begin
  if v_tenant is null then
    raise exception 'tenant context missing';
  end if;
  return query
    select c.id, split_part(v.full_name, ' ', 1)
    from cobranza.vertical_customers c
    join cobranza.pii_vault v on v.person_token = c.person_token and v.tenant_id = c.tenant_id
    where c.tenant_id = v_tenant
      and c.vertical = p_vertical
      and right(v.national_id, 4) = p_id_last4
      and v.birth_date = p_birth_date;
end
$$;

-- Keeps demo calendars fresh: future slots exist for the next 7 days, Monday to Saturday.
create or replace function cobranza.ensure_demo_slots()
returns void
language plpgsql security definer set search_path = cobranza, pg_temp
as $$
declare
  v_tenant text := cobranza.current_tenant();
  d date;
  h int;
  s record;
  a text;
begin
  if v_tenant is distinct from 'demos' then
    return;
  end if;
  for d in select generate_series(current_date + 1, current_date + 7, interval '1 day')::date loop
    continue when extract(isodow from d) = 7;
    foreach h in array array[9, 11, 14, 16] loop
      for s in select id from cobranza.clinic_specialists where tenant_id = v_tenant loop
        insert into cobranza.clinic_slots (id, tenant_id, specialist_id, starts_at)
        values ('slot_' || s.id || '_' || to_char(d, 'MMDD') || '_' || h, v_tenant, s.id,
                (d::timestamp + make_interval(hours => h)) at time zone 'America/Bogota')
        on conflict (id) do nothing;
      end loop;
      foreach a in array array['Laura Mejía', 'Andrés Cifuentes'] loop
        insert into cobranza.advisor_slots (id, tenant_id, advisor, starts_at)
        values ('adv_' || substr(md5(a), 1, 4) || '_' || to_char(d, 'MMDD') || '_' || h, v_tenant, a,
                (d::timestamp + make_interval(hours => h)) at time zone 'America/Bogota')
        on conflict (id) do nothing;
      end loop;
    end loop;
  end loop;
end
$$;

revoke all on function cobranza.match_vertical_customer(text, text, date) from public;
revoke all on function cobranza.ensure_demo_slots() from public;
grant execute on function cobranza.match_vertical_customer(text, text, date) to cobranza_app;
grant execute on function cobranza.ensure_demo_slots() to cobranza_app;

-- ------------------------------------------------------------------- seed data

insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date) values
  ('per_dem_mariana',  'demos', 'Mariana Londoño Pérez',  '52341612',   '1989-02-17'),
  ('per_dem_julian',   'demos', 'Julián Cardona Ruiz',    '71254408',   '1976-09-03'),
  ('per_dem_santiago', 'demos', 'Santiago Beltrán Mora',  '1018442290', '1994-06-21'),
  ('per_dem_valeria',  'demos', 'Valeria Ospina Gil',     '1037561144', '1991-12-09'),
  ('per_dem_hernan',   'demos', 'Hernán Ruiz Soto',       '79443107',   '1982-04-30'),
  ('per_dem_natalia',  'demos', 'Natalia Arboleda Vega',  '1152887731', '1993-08-12'),
  ('per_dem_camilo',   'demos', 'Camilo Yepes Roldán',    '98765210',   '1985-01-25'),
  ('per_dem_esteban',  'demos', 'Esteban Guzmán Torres',  '1020876543', '1990-10-10');

insert into cobranza.vertical_customers (id, tenant_id, vertical, person_token, id_last4, consent_commercial) values
  ('cus_dem_mariana',  'demos', 'salud',  'per_dem_mariana',  '1612', false),
  ('cus_dem_julian',   'demos', 'salud',  'per_dem_julian',   '4408', false),
  ('cus_dem_santiago', 'demos', 'retail', 'per_dem_santiago', '2290', false),
  ('cus_dem_valeria',  'demos', 'retail', 'per_dem_valeria',  '1144', true),
  ('cus_dem_hernan',   'demos', 'retail', 'per_dem_hernan',   '3107', false),
  ('cus_dem_natalia',  'demos', 'telco',  'per_dem_natalia',  '7731', false),
  ('cus_dem_camilo',   'demos', 'telco',  'per_dem_camilo',   '5210', false),
  ('cus_dem_esteban',  'demos', 'telco',  'per_dem_esteban',  '6543', false);

insert into cobranza.clinic_specialists (id, tenant_id, name, specialty) values
  ('spe_card', 'demos', 'Dra. Elena Marín',   'cardiología'),
  ('spe_med',  'demos', 'Dr. Tomás Quintero', 'medicina general'),
  ('spe_derm', 'demos', 'Dra. Paula Arango',  'dermatología');

do $$
begin
  perform set_config('app.tenant_id', 'demos', true);
  perform cobranza.ensure_demo_slots();

  -- Mariana already has a cardiology appointment she can reschedule.
  insert into cobranza.appointments (ref, tenant_id, customer_id, slot_id)
  select 'CIT-DEMO01', 'demos', 'cus_dem_mariana', id
  from cobranza.clinic_slots
  where tenant_id = 'demos' and specialist_id = 'spe_card'
  order by starts_at limit 1;

  update cobranza.clinic_slots set taken = true
  where id = (select slot_id from cobranza.appointments where ref = 'CIT-DEMO01');
end
$$;

insert into cobranza.orders
  (order_no, tenant_id, customer_id, status, carrier, eta_offset_days, delivered_days_ago, items, total) values
  ('MN-10482', 'demos', 'cus_dem_santiago', 'out_for_delivery', 'Servientrega', 0, null, 'Chaqueta de cuero y cinturón', 389900),
  ('MN-10377', 'demos', 'cus_dem_santiago', 'delivered', 'Servientrega', null, 3, 'Jeans slim azul', 159900),
  ('MN-10110', 'demos', 'cus_dem_hernan', 'delivered', 'Coordinadora', null, 45, 'Zapatos casuales', 219900),
  ('MN-10533', 'demos', 'cus_dem_valeria', 'shipped', 'Coordinadora', 2, null, 'Vestido de lino', 179900);

insert into cobranza.carts (id, tenant_id, customer_id, items, total) values
  ('crt_dem_valeria', 'demos', 'cus_dem_valeria', 'Tenis blancos talla 37', 249900),
  ('crt_dem_hernan', 'demos', 'cus_dem_hernan', 'Morral de viaje', 189900);

insert into cobranza.telco_services (id, tenant_id, customer_id, plan, monthly_price, area, modem_state) values
  ('svc_dem_natalia', 'demos', 'cus_dem_natalia', 'Fibra 300 Mbps', 99900, 'Laureles', 'unresponsive'),
  ('svc_dem_camilo', 'demos', 'cus_dem_camilo', 'Fibra 300 Mbps', 99900, 'Belén', 'ok'),
  ('svc_dem_esteban', 'demos', 'cus_dem_esteban', 'Fibra 500 Mbps', 129900, 'Envigado', 'ok');

insert into cobranza.telco_outages (tenant_id, area, active, description) values
  ('demos', 'Laureles', false, 'Sin fallas reportadas en la zona.'),
  ('demos', 'Belén', true, 'Falla de fibra en la zona de Belén. El equipo técnico estima restablecer el servicio en unas tres horas.'),
  ('demos', 'Envigado', false, 'Sin fallas reportadas en la zona.');

insert into cobranza.retention_offers (id, tenant_id, reason, headline, discount_pct, months) values
  ('ret_precio', 'demos', 'precio', 'Descuento en la mensualidad', 20, 6),
  ('ret_falla', 'demos', 'falla', 'Visita técnica sin costo y un mes de crédito', 10, 1),
  ('ret_necesidad', 'demos', 'necesidad', 'Cambio a un plan más pequeño sin cargo', 30, 3);

insert into cobranza.properties (id, tenant_id, title, zone, bedrooms, price, kind) values
  ('prop_01', 'demos', 'Apartamento remodelado con balcón', 'Chapinero', 2, 520000000, 'venta'),
  ('prop_02', 'demos', 'Apartamento amplio cerca al parque', 'Chapinero', 3, 780000000, 'venta'),
  ('prop_03', 'demos', 'Apartaestudio amoblado', 'Chapinero', 1, 3200000, 'arriendo'),
  ('prop_04', 'demos', 'Apartamento nuevo con gimnasio', 'Usaquén', 2, 640000000, 'venta'),
  ('prop_05', 'demos', 'Casa con patio', 'Cedritos', 3, 910000000, 'venta'),
  ('prop_06', 'demos', 'Apartamento familiar', 'Cedritos', 3, 4800000, 'arriendo');

insert into cobranza.contact_consents (tenant_id, person_token, purpose, channel)
select 'demos', person_token, 'comercial', 'voice'
from cobranza.vertical_customers where tenant_id = 'demos' and consent_commercial;
