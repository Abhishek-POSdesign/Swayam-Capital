# SESSION LOG — the night of 8/9 September 2026

> **This is a HISTORICAL RECORD, not an authority.** For what is true right now,
> read `docs/SWAYAM_START_HERE.md`, then `docs/PLAN.md`, then `CLAUDE.md` in the
> repo. This file exists so a session that has lost its memory can see what was
> found, how it was proven, and why the code looks the way it does.

---

## Why this session mattered

He has never taken a paper trade. Everything below was found by walking the
trade path he was about to use for the first time, and breaking it on purpose.
**Four separate faults would have stopped or corrupted his first trade.** None
had been found by three previous independent audits, because all of them only
appear when a real trade is opened and closed.

The session ran from about 22:20 IST on 8 September to 04:00 IST on 9 September.
Four pull requests, all merged and deployed: **#41, #42, #43, #44**.

---

## 1. There were 26 fabricated trades in his Second Brain

**What was wrong.** His real trade journal folder,
`02 - Projects/Trading/04 - Journal/`, held 26 markdown notes dated 8 September,
all named "Violating Spread". Checked against the database: **only 4 had a
matching row. The other 22 existed nowhere but his vault.**

**How they got there.** `tests/db_guard.py` cages the database. Nothing caged
the vault. Every writer in `api/journal_writer.py` fell back to the live vault
path when no override was passed, so any test that mocks the database, and
therefore never trips the database guard, wrote a real file into the folder
holding his trading record.

**What was done.** He identified them with one fact: **he has taken no trade of
his own since 31 March 2026**, so anything later that he did not create is test
data. They were deleted. His vault is under git with automatic backups, so they
remain recoverable.

**The cage.** `journal_writer._default_vault_base()` refuses outright while a
test is running, and `tests/conftest.py::cage_the_vault` redirects writes to a
temporary folder. A test that redirected the vault path itself is respected, the
same way the database guard respects an injected client. Reads are untouched,
because the AI persona genuinely reads his Method files.

**Proof.** His journal folder held 0 notes before a full suite run and 0 after.
It had never been possible to say that before.

---

## 2. The Trade Journal invented numbers and wrote to his database

Four faults were already known and written into the plan. Two more were found
while fixing them, and he added a rule of his own.

| Fault | What it was |
|---|---|
| A ninth invented constant | A hardcoded five-lakh "margin base" divided his cumulative result and his drawdown, in two places. His live balance is ₹9,71,002, so every percentage was nearly double |
| A write fired by opening a page | The journal posted to an archive endpoint on the first load of every browser session, with nothing clicked |
| Analytics ignored provenance | It had **no filter of any kind** beyond dates, so all 81 build-test rows fed the curve, the drawdown, the expectancy and every per-strategy figure |
| Two marks for one idea | `provenance` and a date-cutoff `status = 'archived'` that could disagree. This was his own question |
| **The silent zero** | Both endpoints read `realized_pnl_inr` and `unrealized_pnl_inr` off `swayam_positions`. **Neither column exists.** Every trade without a trade-history row scored a flat ₹0, and that table is empty |
| **Zeros on an empty book** | A 0.0% win rate and a 100.0% discipline rate rendered as real figures |

**His rule, given that night:** "I only want the trade that is squared off to go
in as a trade journal." A trade now scores only when it is closed **and** its
result can be read.

---

## 3. Charges belonged to the trade. He corrected it: they belong to the leg

**His words, 9 September:** "The charges should not be recorded as per the
trade. Charges are recorded as per the leg. The buy leg has its own charges, and
the sell leg has its own charges. Why would squaring one leg charge for the
whole trade?... Whenever we buy or sell, the charges will be calculated then and
there."

He was right, and the system was worse than the plan said. **Nothing was charged
at entry at all.** The only charge ever booked was a flat ₹150 times the number
of legs, once, at the close.

| | Was | Is |
|---|---|---|
| Entry | Nothing, ever | Each leg costed as it is bought or sold |
| Exit | Flat ₹150 × legs | Each leg costed at its real exit price, on the reversed side |
| One-lot condor round trip | ₹600 | About ₹223 |
| Held across 1 April 2026 | One rate | Entry on the old schedule, exit on the new one |

**Costing leg by leg is exact, not an approximation.** Brokerage is per order and
every other line is a percentage of that leg's own turnover, so the parts sum to
the whole to the paisa: 35.47 + 25.22 + 34.80 + 25.22 = 120.71, which is what
those four legs cost in a single call.

**Why this matters more than it looks.** His FY 2025-26, verified against the raw
broker file: gross **+₹6,109**, charges **−₹92,408**, net **−₹86,299**. Costs are
what ended his last trading year.

---

## 4. His first paper trade could not have been closed

This is the one that would have hit him at the desk.

**Fault A, the blocker.** The close writes `closed_at` and `journal_path` to
`swayam_positions`. **Neither column existed.** Proved against the live schema
with the exact payload the close sends, not by reading code. Nobody had noticed
because nobody has ever closed a trade.

The order of operations is what makes it dangerous:

1. The result is INSERTED into `swayam_trade_history`. Recorded correctly.
2. The UPDATE marking the position closed fails on the missing column.
3. He sees HTTP 503.
4. The position still reads `open`.
5. He presses close again, and step 1 runs a SECOND time.

**Fault B.** Step 5 double counted the trade. Migration 020 adds a unique index
on `swayam_trade_history.position_id`, and the close checks for an existing
result first, so a retry completes the half-finished close instead of
duplicating it. That is the rule migration 019 gave the entry side; the exit side
had never been checked.

**Fault C.** The note's path was only ever kept in an in-memory dict, so the row
never carried it. At close there was nothing to append to and his note would
have read "Exit: to be filled at close" for ever. It is stored on the row now,
and a row written earlier recovers it from `swayam_journal_entries.md_path`.

**Fault D.** A NOTE IS NOT A TRADE, and the exit side had never learned it. A
failed exit note raised HTTP 500 with the position already closed in the
database, so his screen said the close had failed when it had not. It queues to
the outbox now, and `scripts/drain_journal_outbox.py` learned how to finish a
close note, which it could not do before, so such a row would have sat there for
ever.

**And a second money bug in the entry path.** The desk sends no contract size.
The stored leg was a straight copy of the request, so the size was stored as
empty, and the close refuses to value a leg it cannot size rather than guess. The
leg now stores the size the SERVER resolved from the FYERS contract master,
which is 65.

---

## 5. Two smaller things that would have cost him time

**His record was describing setups he never wrote.** The expanded trade row
filled empty fields with written-sounding defaults: "Standard breakout", "Key
support/resistance level", "Standard option spread", "With Trend", "Manual /
Target", a directional view of "Neutral", and "100% Rules Followed". All dashes
now, and discipline has three states, because "not recorded" is neither followed
nor violated.

**The script he runs first was lying to him.** `Refresh-Token.ps1` still said the
live site keeps the old token until it restarts. It reads Secret Manager at
request time now. At 2 pm that message would have sent him into an unnecessary
redeploy inside a 90-minute window.

---

## 6. The guard that stops this class of fault returning

`tests/test_written_columns_exist.py` reads every column the trade path writes,
from the source, and every column the migrations create, and compares them. It is
offline and deterministic: no database, no network. **Proven to fail without
migration 020 and pass with it.**

Neither existing cage covers this. The database guard stops a test writing the
wrong DATA. The vault cage stops it writing the wrong FILE. Neither catches
writing to a column that is not there.

---

## 7. What was verified, and what was not

**Verified on the running system, 9 September.**

- Live walk of 14 endpoints against a real backend: all 200. Twenty consecutive
  rule validations: 20 of 20. The option chain returned 41 strikes with real
  prices against a spot of 23,635.10. Capital read his real ₹9,71,111 from FYERS.
- Migration 020 applied by him. Both columns confirmed present on the live schema
  afterwards. 81 rows untouched.
- Live revision `swayam-dashboard-00050-69d` runs the image built from `main` at
  `70b0814`, checked by image digest.
- Python 433 pass, 1 fail. JavaScript 215 pass, 0 fail.
- Position count 81 before and after every suite run. Vault journal folder 0
  notes before and after.

**NOT verified, and this is the whole point of the live test.**

- **Opening and closing a real trade.** Both write to his live record, so they
  are proven only by test against the real code path with the database faked.
- The recorder has still never written an object to its bucket.
- The token being re-read in production without a restart.
- Everything about an open position: the Home strip's colour, its combined profit
  and loss, its running-loss headroom, the desk's margin-used figure.

---

## 8. The one long-standing test failure

`tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`
fails with `ValueError: not enough values to unpack`. Confirmed identical on a
clean tree by stashing every change, repeatedly, across this whole session. It
pre-dates all of this work. **Do not "fix" it by weakening the assertion.**

---

## 9. Housekeeping done at the end of the session

- Every leftover branch deleted, local and remote, after proving each one's merge
  commit is an ancestor of `main`. **The repository now has exactly one branch:
  `main`.** Zero open pull requests, one worktree.
- The side worktree at `wt-swayam-023` removed.
- Two dead frontend components that still hardcoded the old NIFTY lot of 75 were
  deleted. Nothing imported them; the risk was a copy-paste regression.
- `WHERE EVERYTHING LIVES.md` carries a refreshed "this file is not current"
  banner naming everything that changed, and is mirrored to the vault.
- `docs/SWAYAM_START_HERE.md` mirrored to `00 - Developer Logs/`.

---

## 10. What happens next

1. **The live market test, at his desk, in his 14:00 window.** It is the gate to
   paper trading and it has never been run. `docs/PLAN.md` section 1 is the
   script: four things he does, six read from the logs afterwards.
2. **Then the trade lifecycle**, `docs/PLAN.md` section 2.11, in his own words: a
   trade has a number, legs are added and squared off inside it, and it closes
   when every leg is closed or when he says so. He specified it himself.
3. Then backups and the kill switch.
4. **Calendars are briefed and not built.** He said explicitly they are to be
   discussed the day after the live test. Do not push him.

---

## 11. One question still open for him

The rule "no single-leg trades ever" is still evaluated by the backend. His rules
one-pager says that rule is gone, and the desk does not render it, so nothing
wrong reaches his screen. It has not been removed because it is his to delete.
Ask him.

---

---

## 12. THE AFTERNOON HE ACTUALLY TRADED

Sections 1 to 11 above were written before the market opened. What follows
happened between 13:30 and 15:30 IST on 2026-09-09, and it is the more important
half.

**He took three paper trades. All three made a gross profit. All three lost
money.** Gross +195, charges 585, net -390, charges 300% of gross. The full audit
is  section 2.12.0.

**Four separate things stopped him, all fixed the same afternoon.**

1. The close wrote two columns that did not exist. Migration 020.
2. A ghost position survived on Home after he had closed it, because an
   in-process list shadowed the database.
3. Live profit and loss had never worked once: it sent the word NIFTY where
   FYERS wants a symbol.
4. **The execution key was minted once per browser and never released**, so his
   first trade worked and every later one was refused. He could not trade twice
   in one afternoon and the screen gave him no way out.

**And the live site wrote his first trade note into a container folder and
reported success.** The Windows vault path became a relative directory on Linux,
mkdir created it, the write succeeded, and the note died with the container.
That is now refused and queued instead.

**His verdict on the whole experience:** immature execution, immature exit,
immature monitoring. Taking a position is more immature than buying a soda
bottle. That verdict is the reason section 2.12 exists.

**What the recorder actually wrote,** measured from its first real file: 10,332
rows, twelve columns entirely zero including the underlying spot and every Greek.

---

*Nothing in this file overrides `MY TRADING RULES - ONE PAGE.md`.*
