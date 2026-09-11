-- =====================================================================
-- 024_resting_orders.sql
--
-- Build B. docs/builds/BUILD_03_RESTING_ORDERS.md section 3.1.
--
-- WHY THIS TABLE EXISTS. His words, 10 September 2026, after the first
-- live send: "I can place 111, 112, or 113 because it's a limit order...
-- It should not execute if the price is not available, but must be
-- sitting in the system till the time the bid and ask reach the price I
-- want."
--
-- Until now a limit the book had not reached refused the whole ticket and
-- died there. It cost him his strangle on 10 September and gave his condor
-- the name of the preset he had loaded first. An order needs somewhere to
-- WAIT. This is that place.
--
-- ONE TABLE, ONE DAY. Every order here expires at the bell of the day it
-- was placed. Nothing in this build outlives a session.
--
-- NOTHING HERE IS MONEY UNTIL IT FILLS. A resting order holds no margin,
-- books no charge, writes no note and touches no position. The moment it
-- fills it goes through exactly the path a leg he pressed Send on takes,
-- and the money is made there, by the same code, with the same charges.
--
-- Additive only. No existing table is altered and no existing row is
-- touched. Trade 7cd4d017 is not edited by this migration.
-- =====================================================================


CREATE TABLE IF NOT EXISTS public.swayam_orders (
  -- The order's own identity. A modify keeps it, so his book does not
  -- reshuffle under him when he changes a price.
  id uuid PRIMARY KEY,

  -- The trade this order belongs to, or NULL for an entry that will OPEN a
  -- trade when it fills. "new trade, opens when it fills" on his screen is
  -- exactly this column being null.
  position_id uuid NULL,

  -- The ticket that placed it. Not in the build document, and needed by two
  -- things the build document asks for:
  --   1. When no leg of an entry ticket could fill, the FIRST of its orders
  --      to fill opens the trade and "the rest become add_leg orders on that
  --      trade". Without this column there is no way to know which orders
  --      are "the rest".
  --   2. His instruction of 2026-09-10: a resting exit that expires at the
  --      bell as the LAST leg of an Exit everything must be announced. That
  --      needs to know the legs were one press.
  group_id uuid NULL,

  -- What filling it will do. entry opens a trade, add_leg joins one,
  -- exit_leg squares one off, reverse flips one, exit_all_leg is one leg of
  -- an Exit everything and is the kind the bell warning looks for.
  kind text NOT NULL CHECK (kind IN ('entry', 'add_leg', 'exit_leg', 'reverse', 'exit_all_leg')),

  -- The leg exactly as the ticket sent it: direction, strike, option_type,
  -- expiry_date, quantity_lots, the underlying, and for an exit the sequence
  -- of the leg being closed. Nothing is recomputed from it; it is replayed.
  leg jsonb NOT NULL,

  -- HIS price. The only number on this row he chose.
  limit_price numeric NOT NULL CHECK (limit_price > 0),

  -- resting  - waiting for the book
  -- filling  - claimed by one process and being sent RIGHT NOW. Lives for a
  --            moment. It exists so that the move from resting to filled is
  --            one conditional update only one process can win, which is his
  --            requirement of 2026-09-10. A row stranded here means a process
  --            died mid-send: it is NOT re-armed automatically, because
  --            nobody can know from here whether the leg reached the trade.
  --            It is shown to him as needing a look, which is the honest
  --            answer.
  -- filled | cancelled | expired | failed - final.
  status text NOT NULL DEFAULT 'resting'
    CHECK (status IN ('resting', 'filling', 'filled', 'cancelled', 'expired', 'failed')),

  placed_at timestamptz NOT NULL DEFAULT now(),

  -- 15:30 IST of the day it was placed. The bell, and nothing beyond it.
  expires_at timestamptz NOT NULL,

  filled_at timestamptz NULL,

  -- The fill exactly as services/fills.py reported it: price, which side of
  -- the book it took, the traded price at the time, and how it read.
  fill jsonb NULL,

  -- What filling it produced: the position it joined or opened, and the
  -- sequence the leg was given there.
  result jsonb NULL,

  -- THE EXCHANGE'S DAILY PRICE BAND, read ONCE when the order is placed.
  --
  -- Settled by a read-only test against live FYERS on 2026-09-10 evening:
  -- the FYERS QUOTE call carries no band at all. The market DEPTH call does,
  -- as lower_ckt, upper_ckt and tick_Size.
  --
  -- band_source is 'FYERS depth' when it was read and 'unavailable' when the
  -- depth call failed. There is no third case: a band is never invented, and
  -- an order whose band could not be read still rests, with the screen
  -- saying so in words.
  band_lower numeric NULL,
  band_upper numeric NULL,
  band_source text NULL,

  -- One press, one order, exactly as the execution key works everywhere else.
  idempotency_key text NULL,

  -- Why it went to 'failed'. Never blank when the status is failed.
  failure_reason text NULL,

  -- The phase mark the position would get, read from swayam_phase at
  -- placement, so an order says what it was even if the phase changes while
  -- it waits.
  provenance text NULL
);


-- The watcher's only question, several times a minute: what is still
-- resting, and has anything reached the bell.
CREATE INDEX IF NOT EXISTS idx_swayam_orders_status_expires
  ON public.swayam_orders USING btree (status, expires_at);

-- The position area asks for one trade's orders, and the group asks for its
-- siblings when the first of them fills.
CREATE INDEX IF NOT EXISTS idx_swayam_orders_position
  ON public.swayam_orders USING btree (position_id);

CREATE INDEX IF NOT EXISTS idx_swayam_orders_group
  ON public.swayam_orders USING btree (group_id);

-- His book for the day, newest first.
CREATE INDEX IF NOT EXISTS idx_swayam_orders_placed_at
  ON public.swayam_orders USING btree (placed_at);


COMMENT ON TABLE public.swayam_orders IS
  'Limit orders waiting for the book to reach them. One trading day only; everything resting expires at 15:30 IST. A row here holds no margin and has cost nothing until it fills.';

COMMENT ON COLUMN public.swayam_orders.position_id IS
  'The trade it belongs to. NULL for an entry order that will open a new trade when it fills.';

COMMENT ON COLUMN public.swayam_orders.group_id IS
  'The ticket press that placed it. Sibling entry orders join the trade the first of them opens; sibling exit_all_leg orders are one Exit everything, which is what the bell warning reads.';

COMMENT ON COLUMN public.swayam_orders.status IS
  'resting, filling (claimed by one process, in flight), filled, cancelled, expired, failed. A row stranded in filling means a process died mid-send and is never re-armed automatically.';

COMMENT ON COLUMN public.swayam_orders.band_source IS
  'FYERS depth when the daily price band was read from the depth call at placement; unavailable when that call failed and the order rests without a band check. Never anything else, because a band is never invented.';

COMMENT ON COLUMN public.swayam_orders.expires_at IS
  '15:30 IST of the day it was placed. A resting order does not outlive its session.';
