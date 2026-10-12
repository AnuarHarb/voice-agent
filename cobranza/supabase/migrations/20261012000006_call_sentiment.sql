-- Post-call sentiment from ElevenLabs analysis: how the customer felt, not who they are.
alter table cobranza.call_outcomes
  add column sentiment_label     text check (sentiment_label in ('positive', 'neutral', 'negative')),
  add column sentiment_score     numeric(3, 2),
  add column frustration_score   numeric(3, 2),
  add column min_sentiment_score numeric(3, 2);
