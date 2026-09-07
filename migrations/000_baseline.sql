-- =====================================================================
-- 000_baseline.sql
-- The authoritative statement of what the Swayam database IS, captured
-- directly from the live Supabase project wxijlrwoiaeaupaaqecc on
-- 2026-09-08 by reading pg_catalog, not by reading the migration files.
--
-- WHY THIS FILE EXISTS
--   The migration files on disk are numbered 001, 002, 004-007, 013-016.
--   003 and 008-012 do not exist. There was no version table, and no
--   migration had ever actually been executed by a script: the old
--   apply_migration.py printed the SQL and asked a human to paste it.
--   Nobody could state what the live schema was. This file ends that.
--
-- SCOPE
--   swayam_* tables ONLY. This Supabase project is shared with the Biz
--   Research Hub (biz_*), the B.tech Learning Hub (hub_*) and the blog
--   automation (blog_*). Nothing in this file touches those.
--
-- Re-running this against the live database is safe: every CREATE is
-- guarded, and nothing is ever dropped. The ALTER ... ADD CONSTRAINT
-- statements will error if the constraint already exists, which is the
-- intended behaviour when using this file to rebuild an empty schema.
-- =====================================================================

-- ---------- sequences ----------
CREATE SEQUENCE IF NOT EXISTS public.swayam_ai_notebook_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.swayam_ai_pinned_decisions_id_seq;
CREATE SEQUENCE IF NOT EXISTS public.swayam_ai_session_summaries_id_seq;

-- ---------- tables ----------

CREATE TABLE IF NOT EXISTS public.swayam_ai_conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  started_at timestamp with time zone NOT NULL DEFAULT now(),
  last_active_at timestamp with time zone NOT NULL DEFAULT now(),
  title text,
  archived boolean NOT NULL DEFAULT false,
  notes text
);

CREATE TABLE IF NOT EXISTS public.swayam_ai_messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  role text NOT NULL,
  content text NOT NULL,
  context_snapshot jsonb,
  provider text,
  input_tokens integer,
  output_tokens integer,
  latency_ms integer,
  position_id uuid,
  session_date date NOT NULL DEFAULT CURRENT_DATE,
  attachment_url text,
  attachment_mime text
);

CREATE TABLE IF NOT EXISTS public.swayam_ai_notebook (
  id bigint NOT NULL DEFAULT nextval('swayam_ai_notebook_id_seq'::regclass),
  entry_text text NOT NULL,
  source_message_id uuid,
  source_conversation_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_ai_pinned_decisions (
  id bigint NOT NULL DEFAULT nextval('swayam_ai_pinned_decisions_id_seq'::regclass),
  rule_text text NOT NULL,
  pinned_at timestamp with time zone NOT NULL DEFAULT now(),
  active boolean NOT NULL DEFAULT true,
  source_message_id uuid
);

CREATE TABLE IF NOT EXISTS public.swayam_ai_session_summaries (
  id bigint NOT NULL DEFAULT nextval('swayam_ai_session_summaries_id_seq'::regclass),
  session_date date NOT NULL,
  summary_block jsonb NOT NULL,
  message_count integer NOT NULL,
  compacted_at timestamp with time zone NOT NULL DEFAULT now(),
  covered_message_ids uuid[] NOT NULL DEFAULT '{}'::uuid[]
);

CREATE TABLE IF NOT EXISTS public.swayam_ai_usage_daily (
  day date NOT NULL,
  provider text NOT NULL,
  model text NOT NULL,
  total_input_tokens integer NOT NULL DEFAULT 0,
  total_output_tokens integer NOT NULL DEFAULT 0,
  request_count integer NOT NULL DEFAULT 0,
  estimated_cost_inr numeric(10,2) NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS public.swayam_backtest_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  run_at timestamp with time zone NOT NULL DEFAULT now(),
  rule_snapshot jsonb NOT NULL,
  strategy_name text NOT NULL,
  date_range_start date NOT NULL,
  date_range_end date NOT NULL,
  n_trades integer NOT NULL,
  win_rate numeric(5,4),
  avg_rr numeric(6,3),
  expectancy_inr numeric(12,2),
  max_drawdown_pct numeric(5,4),
  trades jsonb NOT NULL,
  notes text
);

CREATE TABLE IF NOT EXISTS public.swayam_bhavcopy (
  date date NOT NULL,
  vix_close numeric(8,2) NOT NULL,
  vix_open numeric(8,2),
  vix_high numeric(8,2),
  vix_low numeric(8,2),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_config (
  key text NOT NULL,
  value jsonb NOT NULL,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_by text
);

CREATE TABLE IF NOT EXISTS public.swayam_home_snapshot (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  snapshot_type text NOT NULL,
  generated_at timestamp with time zone NOT NULL DEFAULT now(),
  payload jsonb NOT NULL,
  ai_tokens_used integer
);

CREATE TABLE IF NOT EXISTS public.swayam_journal_entries (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  position_id uuid,
  entry_date date NOT NULL,
  entry_type text NOT NULL,
  md_path text,
  chart_image_path text,
  body_summary text,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_lessons (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  position_id uuid NOT NULL,
  trade_closed_at timestamp with time zone NOT NULL,
  strategy_name text NOT NULL,
  outcome text NOT NULL,
  realised_pnl_inr numeric(12,2) NOT NULL,
  rr_planned numeric(6,2),
  rr_actual numeric(6,2),
  lesson_text text NOT NULL,
  lesson_source text NOT NULL DEFAULT 'ai_generated'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_macro_events (
  event_key text NOT NULL,
  event_name text NOT NULL,
  event_date date NOT NULL,
  event_time_ist time without time zone,
  country text NOT NULL,
  category text,
  importance text,
  highlighted boolean NOT NULL DEFAULT false,
  impact_brief text,
  fetched_at timestamp with time zone NOT NULL DEFAULT now(),
  curated_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS public.swayam_nifty_daily_bars (
  trade_date date NOT NULL,
  symbol text NOT NULL DEFAULT 'NIFTY'::text,
  open numeric(10,2) NOT NULL,
  high numeric(10,2) NOT NULL,
  low numeric(10,2) NOT NULL,
  close numeric(10,2) NOT NULL,
  volume bigint,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_notification_devices (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  device_token text NOT NULL,
  browser_ua text,
  platform text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  last_seen_at timestamp with time zone NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.swayam_positions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  opened_at timestamp with time zone NOT NULL DEFAULT now(),
  mode text NOT NULL,
  strategy_name text NOT NULL,
  underlying text NOT NULL,
  expiry_date date NOT NULL,
  legs jsonb NOT NULL,
  net_debit_credit_inr numeric(12,2) NOT NULL,
  max_loss_inr numeric(12,2) NOT NULL,
  max_profit_inr numeric(12,2) NOT NULL,
  breakeven_points jsonb NOT NULL,
  stop_level numeric(12,2),
  target_level numeric(12,2),
  risk_at_entry_inr numeric(12,2) NOT NULL,
  status text NOT NULL DEFAULT 'open'::text,
  notes text,
  time_in_trade_minutes integer,
  spot_at_entry numeric(12,2),
  spot_at_exit numeric(12,2),
  points_in_trade numeric(8,2),
  directional_view text,
  setup_technical text,
  setup_location text,
  moneyness_summary text,
  with_or_against_trend text,
  charges_inr numeric(10,2) NOT NULL DEFAULT 0,
  rules_followed boolean DEFAULT true,
  rules_broken_reason text,
  exit_reason text,
  entry_rationale text,
  exit_rationale text
);

CREATE TABLE IF NOT EXISTS public.swayam_readiness_log (
  log_date date NOT NULL,
  verdict text NOT NULL,
  factors jsonb NOT NULL,
  trading_allowed boolean NOT NULL,
  size_cap_pct numeric(4,3),
  computed_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.swayam_rule_evolution_log (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  changed_at timestamp with time zone NOT NULL DEFAULT now(),
  rule_name text NOT NULL,
  old_value jsonb,
  new_value jsonb NOT NULL,
  changed_by text NOT NULL,
  reason text,
  reverted_at timestamp with time zone
);

CREATE TABLE IF NOT EXISTS public.swayam_trade_history (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  position_id uuid,
  closed_at timestamp with time zone NOT NULL DEFAULT now(),
  close_reason text NOT NULL,
  realized_pnl_inr numeric(12,2) NOT NULL,
  total_charges_inr numeric(12,2),
  holding_days integer NOT NULL,
  exit_legs jsonb NOT NULL,
  journal_md_path text,
  ai_context_summary jsonb,
  journal_reflection text
);

-- ---------- primary keys and unique constraints ----------
ALTER TABLE public.swayam_ai_conversations     ADD CONSTRAINT swayam_ai_conversations_pkey     PRIMARY KEY (id);
ALTER TABLE public.swayam_ai_messages          ADD CONSTRAINT swayam_ai_messages_pkey          PRIMARY KEY (id);
ALTER TABLE public.swayam_ai_notebook          ADD CONSTRAINT swayam_ai_notebook_pkey          PRIMARY KEY (id);
ALTER TABLE public.swayam_ai_pinned_decisions  ADD CONSTRAINT swayam_ai_pinned_decisions_pkey  PRIMARY KEY (id);
ALTER TABLE public.swayam_ai_session_summaries ADD CONSTRAINT swayam_ai_session_summaries_pkey PRIMARY KEY (id);
ALTER TABLE public.swayam_ai_session_summaries ADD CONSTRAINT swayam_ai_session_summaries_session_date_key UNIQUE (session_date);
ALTER TABLE public.swayam_ai_usage_daily       ADD CONSTRAINT swayam_ai_usage_daily_pkey       PRIMARY KEY (day);
ALTER TABLE public.swayam_backtest_runs        ADD CONSTRAINT swayam_backtest_runs_pkey        PRIMARY KEY (id);
ALTER TABLE public.swayam_bhavcopy             ADD CONSTRAINT swayam_bhavcopy_pkey             PRIMARY KEY (date);
ALTER TABLE public.swayam_config               ADD CONSTRAINT swayam_config_pkey               PRIMARY KEY (key);
ALTER TABLE public.swayam_home_snapshot        ADD CONSTRAINT swayam_home_snapshot_pkey        PRIMARY KEY (id);
ALTER TABLE public.swayam_journal_entries      ADD CONSTRAINT swayam_journal_entries_pkey      PRIMARY KEY (id);
ALTER TABLE public.swayam_lessons              ADD CONSTRAINT swayam_lessons_pkey              PRIMARY KEY (id);
ALTER TABLE public.swayam_macro_events         ADD CONSTRAINT swayam_macro_events_pkey         PRIMARY KEY (event_key);
ALTER TABLE public.swayam_nifty_daily_bars     ADD CONSTRAINT swayam_nifty_daily_bars_pkey     PRIMARY KEY (trade_date);
ALTER TABLE public.swayam_notification_devices ADD CONSTRAINT swayam_notification_devices_pkey PRIMARY KEY (id);
ALTER TABLE public.swayam_notification_devices ADD CONSTRAINT swayam_notification_devices_device_token_key UNIQUE (device_token);
ALTER TABLE public.swayam_positions            ADD CONSTRAINT swayam_positions_pkey            PRIMARY KEY (id);
ALTER TABLE public.swayam_readiness_log        ADD CONSTRAINT swayam_readiness_log_pkey        PRIMARY KEY (log_date);
ALTER TABLE public.swayam_rule_evolution_log   ADD CONSTRAINT swayam_rule_evolution_log_pkey   PRIMARY KEY (id);
ALTER TABLE public.swayam_trade_history        ADD CONSTRAINT swayam_trade_history_pkey        PRIMARY KEY (id);

-- ---------- check constraints ----------
ALTER TABLE public.swayam_ai_messages     ADD CONSTRAINT swayam_ai_messages_role_check           CHECK (role = ANY (ARRAY['user'::text, 'assistant'::text, 'system'::text]));
ALTER TABLE public.swayam_journal_entries ADD CONSTRAINT swayam_journal_entries_entry_type_check CHECK (entry_type = ANY (ARRAY['entry'::text, 'daily_update'::text, 'exit'::text, 'no_trade_day'::text]));
ALTER TABLE public.swayam_lessons         ADD CONSTRAINT swayam_lessons_outcome_check            CHECK (outcome = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'BREAKEVEN'::text]));
ALTER TABLE public.swayam_positions       ADD CONSTRAINT swayam_positions_mode_check             CHECK (mode = ANY (ARRAY['paper'::text, 'live'::text]));
ALTER TABLE public.swayam_positions       ADD CONSTRAINT swayam_positions_status_check           CHECK (status = ANY (ARRAY['open'::text, 'closed'::text, 'stopped'::text, 'archived'::text]));
ALTER TABLE public.swayam_readiness_log   ADD CONSTRAINT swayam_readiness_log_verdict_check      CHECK (verdict = ANY (ARRAY['green'::text, 'yellow'::text, 'red'::text]));
ALTER TABLE public.swayam_trade_history   ADD CONSTRAINT swayam_trade_history_close_reason_check CHECK (close_reason = ANY (ARRAY['target_hit'::text, 'stop_hit'::text, 'time_exit'::text, 'manual'::text]));

-- ---------- foreign keys ----------
ALTER TABLE public.swayam_ai_messages         ADD CONSTRAINT swayam_ai_messages_conversation_id_fkey          FOREIGN KEY (conversation_id) REFERENCES public.swayam_ai_conversations(id) ON DELETE CASCADE;
ALTER TABLE public.swayam_ai_messages         ADD CONSTRAINT swayam_ai_messages_position_id_fkey              FOREIGN KEY (position_id) REFERENCES public.swayam_positions(id) ON DELETE SET NULL;
ALTER TABLE public.swayam_ai_notebook         ADD CONSTRAINT swayam_ai_notebook_source_conversation_id_fkey   FOREIGN KEY (source_conversation_id) REFERENCES public.swayam_ai_conversations(id) ON DELETE SET NULL;
ALTER TABLE public.swayam_ai_notebook         ADD CONSTRAINT swayam_ai_notebook_source_message_id_fkey        FOREIGN KEY (source_message_id) REFERENCES public.swayam_ai_messages(id) ON DELETE SET NULL;
ALTER TABLE public.swayam_ai_pinned_decisions ADD CONSTRAINT swayam_ai_pinned_decisions_source_message_id_fkey FOREIGN KEY (source_message_id) REFERENCES public.swayam_ai_messages(id) ON DELETE SET NULL;
ALTER TABLE public.swayam_journal_entries     ADD CONSTRAINT swayam_journal_entries_position_id_fkey          FOREIGN KEY (position_id) REFERENCES public.swayam_positions(id);
ALTER TABLE public.swayam_lessons             ADD CONSTRAINT swayam_lessons_position_id_fkey                  FOREIGN KEY (position_id) REFERENCES public.swayam_positions(id) ON DELETE CASCADE;
ALTER TABLE public.swayam_trade_history       ADD CONSTRAINT swayam_trade_history_position_id_fkey            FOREIGN KEY (position_id) REFERENCES public.swayam_positions(id);

-- ---------- indexes ----------
CREATE INDEX IF NOT EXISTS idx_swayam_ai_conversations_last_active  ON public.swayam_ai_conversations    USING btree (last_active_at DESC) WHERE (NOT archived);
CREATE INDEX IF NOT EXISTS idx_swayam_ai_messages_conversation      ON public.swayam_ai_messages         USING btree (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_swayam_ai_notebook_created           ON public.swayam_ai_notebook         USING btree (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_ai_pinned_active              ON public.swayam_ai_pinned_decisions USING btree (active, pinned_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_ai_session_summaries_date     ON public.swayam_ai_session_summaries USING btree (session_date DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_backtest_runs_run_at          ON public.swayam_backtest_runs       USING btree (run_at DESC);
CREATE INDEX IF NOT EXISTS idx_home_snapshot_type_time              ON public.swayam_home_snapshot       USING btree (snapshot_type, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_journal_entries_position_id   ON public.swayam_journal_entries     USING btree (position_id);
CREATE INDEX IF NOT EXISTS idx_swayam_lessons_closed_at             ON public.swayam_lessons             USING btree (trade_closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_lessons_outcome               ON public.swayam_lessons             USING btree (outcome);
CREATE INDEX IF NOT EXISTS idx_swayam_lessons_position              ON public.swayam_lessons             USING btree (position_id);
CREATE INDEX IF NOT EXISTS idx_macro_events_date                    ON public.swayam_macro_events        USING btree (event_date);
CREATE INDEX IF NOT EXISTS idx_macro_events_highlighted             ON public.swayam_macro_events        USING btree (highlighted, event_date);
CREATE INDEX IF NOT EXISTS idx_notification_devices_last_seen       ON public.swayam_notification_devices USING btree (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_positions_opened_at           ON public.swayam_positions           USING btree (opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_positions_status              ON public.swayam_positions           USING btree (status);
CREATE INDEX IF NOT EXISTS idx_swayam_rule_evolution_log_changed_at ON public.swayam_rule_evolution_log  USING btree (changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_swayam_trade_history_closed_at       ON public.swayam_trade_history       USING btree (closed_at DESC);

-- =====================================================================
-- DISK VERSUS DATABASE, reconciled 2026-09-08
--
-- Applied and matching the live database:
--   001_initial_schema.sql
--   002_ai_conversations_and_rule_log.sql
--   004_readiness_meditation_nullable.sql
--   005_ai_memory_system.sql
--   006_swayam_lessons_and_journal_fields.sql
--   007_allow_archived_status.sql
--   013_ai_chat_attachments.sql
--   014_home_snapshot_cache.sql
--   015_macro_events.sql
--   016_notification_devices.sql
--
-- Never existed: 003, and 008 through 012. The numbering gap is a
-- naming accident, not missing schema. Every live object above is
-- explained by one of the ten files listed.
--
-- Live objects with no file to explain them: none.
-- Files describing objects not present live: none.
--
-- Row Level Security is DISABLED on all 19 tables. That is recorded
-- here as fact, not endorsed. It is addressed by the access-control
-- work, not by this baseline.
-- =====================================================================
