-- Telegram is the default channel for every tenant; WhatsApp stays behind the adapter
-- until a Meta-approved utility template exists.
update cobranza.tenants set channel = 'telegram' where channel = 'whatsapp';
alter table cobranza.tenants alter column channel set default 'telegram';
