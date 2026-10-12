-- Fictional seed data. Tenant keys are not stored here: run
-- backend/scripts/set_tenant_key.py to issue a key and store only its hash.

insert into cobranza.tenants (id, name, channel) values
  ('avanza', 'Avanza Crédito', 'whatsapp'),
  ('nexo',   'Nexo Finanzas',  'telegram');

insert into cobranza.tenant_policies
  (tenant_id, max_installments, min_installment_cop, first_payment_max_days,
   hardship_enabled, hardship_installments, hardship_grace_days)
values
  ('avanza', 3, 150000, 5, true, 6, 30),
  ('nexo',   2, 200000, 3, false, 1, 0);

insert into cobranza.pii_vault (person_token, tenant_id, full_name, national_id, birth_date) values
  ('per_avz_laura',  'avanza', 'Laura Gómez Rincón',   '1020304417', '1990-05-14'),
  ('per_avz_carlos', 'avanza', 'Carlos Restrepo Díaz', '79855521',   '1985-11-02'),
  ('per_avz_marta',  'avanza', 'Marta Ospina Vélez',   '43217788',   '1978-03-30'),
  -- Same last four digits and birth date as Laura, in another tenant: the
  -- isolation demo shows each key only ever reaches its own customer.
  ('per_nxo_andres', 'nexo',   'Andrés Pérez Cano',    '1098764417', '1990-05-14');

insert into cobranza.accounts
  (id, tenant_id, person_token, id_last4, account_last4, product,
   overdue_amount, total_balance, days_past_due)
values
  ('acc_avz_0001', 'avanza', 'per_avz_laura',  '4417', '4417', 'Crédito de consumo', 1200000, 4800000, 21),
  ('acc_avz_0002', 'avanza', 'per_avz_carlos', '5521', '9034', 'Crédito de consumo',  450000, 2700000, 12),
  ('acc_avz_0003', 'avanza', 'per_avz_marta',  '7788', '6120', 'Crédito de libranza', 2300000, 9100000, 45),
  ('acc_nxo_0001', 'nexo',   'per_nxo_andres', '4417', '3381', 'Tarjeta de crédito',   800000, 3500000, 18);
