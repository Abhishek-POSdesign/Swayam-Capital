# SWAYAM — RELEASE 1 BUILD LOG (2026-09-08)

> **Live running log of the Release 1 build.** Started 2026-09-07 night, Abhishek present.
> Updated as each step lands. Read this before continuing the build, after a compaction,
> or if you are a new agent picking this up.
>
> The plan being executed is `SWAYAM_PLAN_v9_BUILD_TONIGHT.md`. Do not re-plan it.
> Detail body is `SWAYAM_PHASE1_PLAN_2026-09-07_v6.md` (UI size standard is a hard gate).
> Verified state before this build is `SWAYAM_TRUTH_HANDOVER_2026-09-07.md`.
>
> Branch: `feature/swayam-release1-honest-paper-trade-008`, off `main` at `5f9b8df`.
> Working in the primary folder, NOT a worktree: the venv is an editable install
> pointing at this folder, so a worktree would silently test the wrong source tree.

---

## 0. THE ONE THING TO UNDERSTAND FIRST

**There is no separate test database. Everything runs against the live Supabase
project `wxijlrwoiaeaupaaqecc` ("Sikka Business Apps").** A staging project was
attempted and refused: the free tier allows two projects per account and Abhishek
already has two. Supabase quoted ₹0/month for a third, but the account limit, not
the price, is the blocker.

**That project is shared with two other apps.** `biz_*` is the Biz Research Hub,
`hub_*` is the B.tech Learning Hub, `blog_*` is the blog automation. Seventeen
tables belong to them. Every migration, backup and script in this build is scoped
to `swayam_*` only. Keep it that way.

Consequence for testing: the restore drill and any future destructive test build
into an isolated, prefixed or schema-separated area and drop it afterwards. Never
fault-inject against the live tables.

---

## 1. WHAT HAS CHANGED IN THE LIVE DATABASE

Verified by direct query at the end of each step.

| Change | State |
|---|---|
| `swayam_schema_migrations` table created | **Permanent.** New tonight. 11 rows. |
| `swayam_restore_drill` schema | Created, verified, **dropped**. Zero leftovers confirmed. |
| `swayam_positions` | 67 rows, 64 archived + 3 open. **Unchanged.** |
| `swayam_journal_entries` | 67 rows. **Unchanged.** |
| Every other `swayam_*` table | **Unchanged.** |
| `biz_*`, `hub_*`, `blog_*` (17 tables) | **Untouched.** |

No existing row, column or table has been altered or deleted at any point.

---

## 2. STEPS COMPLETED

### Step 0 — baseline, backup, restore. DONE, proved 2026-09-07.

- **`migrations/000_baseline.sql`** — the first authoritative statement of the live
  schema, read from `pg_catalog`, not inferred from the migration files. Covers all
  19 tables with columns, defaults, primary keys, uniques, checks, foreign keys,
  indexes and sequences.
- **Disk vs database reconciliation:** the ten files on disk (001, 002, 004-007,
  013-016) are all applied and all match. **003 and 008-012 never existed** — the
  gap is a naming accident, not missing schema. No live object is unexplained, and
  no file describes an object that is absent. This question had been open since the
  Codex audit; it is now closed.
- **`scripts/backup_supabase.py`** — full logical backup of the 19 `swayam_*` tables.
  Row count and SHA-256 per file, a manifest, and a Cloud Storage upload that
  **re-lists the bucket and fails the job on a short object count.** The previous
  `backup_service.py` returned success on a failed upload; that is the bug this
  exists not to repeat.
  - First backup: **19 tables, 600 rows, 21 objects** at
    `gs://swayam-backups/supabase/2026-09-07T17-12-15Z/`
- **`scripts/restore_drill.py`** — rebuilds the schema from the backup's own DDL into
  an isolated schema, reloads every row, compares row counts **and** content hashes,
  then drops the schema. The previous `restore_from_backup.py` counted INSERT lines
  and returned success without restoring anything.
  - **RESTORE DRILL: PASSED.** 19/19 tables, 600/600 rows, every table PASS on both
    row count and content.
  - Bug found and fixed during the drill: `swayam_config.current_reentry_ramp_tier`
    holds the JSON value `null` in a `NOT NULL jsonb` column. JSON null is not SQL
    NULL. The loader now reads real column types from `information_schema` instead
    of guessing which columns are JSON.

**What the drill proves:** the backup artifact is complete, its schema is valid DDL,
and every row reloads with identical content.
**What it does NOT prove:** recovery if the whole Supabase project were lost. That
needs a second project. Say this plainly; do not overstate it.

### Step 1 — database connection and migration runner. DONE 2026-09-07.

- **`src/swayam/db_direct.py`** — the project had **no Postgres connection at all**.
  That is the root reason `apply_migration.py` could only print SQL for a human to
  paste, and why no version table existed. Connection string lives in
  `SUPABASE_DB_URL` in `.env`, never in the repo. Tooling only; the app still uses
  the Supabase REST API as before.
  - Normalises the URL by splitting user info on the **last** `@`, because Supabase
    passwords routinely contain `@` and a verbatim paste otherwise fails as a
    baffling host-not-found error.
- **`scripts/apply_migration.py`** — rewritten. One transaction per migration,
  SHA-256 recorded for the exact text that ran, numeric order, pending only, and a
  **hard refusal to run if an already-applied migration file has been edited.**
- **`swayam_schema_migrations`** created and seeded: `000_baseline` plus the ten
  hand-applied files recorded as already applied, not re-executed.
  - `apply_migration.py status` → **11 applied, 0 pending.**

---

## 3. CONNECTION GOTCHA, RECORDED SO IT IS NOT REDISCOVERED

The Supabase **direct** host `db.wxijlrwoiaeaupaaqecc.supabase.co` resolves
**IPv6 only**, and Abhishek's connection drops IPv6 intermittently. It authenticated
once and then timed out on every subsequent attempt.

`.env` now points at the **session pooler**:
`aws-1-ap-south-1.pooler.supabase.com:5432`, user `postgres.wxijlrwoiaeaupaaqecc`.
Note it is **aws-1**, not aws-0; aws-0 returns `ENOTFOUND tenant/user`.

Session mode (5432), not transaction mode (6543), because migrations need session
state and DDL transactions.

---

## 4. STILL BROKEN AT THIS POINT — nothing below is fixed yet

Do not tell Abhishek any of these are done until they are proved on the running
system.

- Lot size is still **75** in 15 places. Truth is **65**, confirmed on all 3,935
  NIFTY rows of the FYERS contract master, column index 3.
- Order-preview margin still hardcoded ₹32,000 / ₹1,15,000.
- Capital, risk caps and the deployable margin ceiling not wired to `funds()`.
- Risk gate not rebuilt; readiness still has power over the trade path.
- Paper fills still use the entered premium, no bid/ask, no charges.
- Execution still not idempotent; a double press still creates two positions.
- Trade lifecycle still not atomic; a failed journal write still returns HTTP 500.
- 67 build-test positions not yet quarantined; 3 still show as open.
- Remaining fabricated values still present.
- Google sign-in not yet applied; the site is still public.
- Live site still cannot write to the vault; Drive API not yet enabled.
- FYERS token still resolved only at container start, so a refresh needs a redeploy.
- 2 backend tests still failing; `rule-panel.js:35` browser error still swallowed.

---

## 5. VERIFIED FACTS, CHECKED FIRST-HAND 2026-09-07 NIGHT

| Fact | Value | How checked |
|---|---|---|
| NIFTY lot size | **65** | FYERS contract master `NSE_FO.csv`, col 3, all 3,935 NIFTY rows |
| FYERS token | Valid | `market_status()` returned 200 |
| Total Balance | ₹9,71,002.38 | `funds()` id 1 |
| Clear Balance | ₹1,00,000 | `funds()` id 3 |
| Collaterals | ₹8,71,002.38 | `funds()` id 5 |
| NIFTY spot | 23,779.15 | live quote |
| Positions | 67 paper, 3 open | live database |
| RLS | **Off on all 19 tables** | Supabase advisory |

---

## 6. DECISIONS MADE DURING THIS BUILD

| Decision | Why |
|---|---|
| Work in the primary folder, not a git worktree | The venv is an editable install pointing at the primary `src/`. A worktree would silently test the wrong code. |
| No staging Supabase project | Account limit of two free projects. Restore drill runs isolated inside the live database instead, and this limitation is stated rather than hidden. |
| Session pooler over direct connection | Direct host is IPv6-only and unreliable here. |
| Abhishek uses the **live site** tomorrow | His decision, stated 2026-09-07. Therefore the Drive API vault write and the runtime token read are pulled into tonight from Release 2. |
| Google sign-in ships tonight | His decision, overriding the recommendation to defer it until after tomorrow's session. |
| Sensibull-grade Strategy Builder is NOT tonight | That is Release 3. Told to him plainly so he does not expect it in the morning. |

---

*Real-money trading remains code-blocked. Nothing in this document is a claim of
readiness. Update this file as each further step lands.*
