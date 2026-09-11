# BUILD C PART TWO — HANDOFF TO THE MAIN CHAT. 2026-09-11, late.

> Written by the Build C builder chat. The first handoff,
> `docs/BUILD_C_HANDOFF_2026-09-11.md`, covers the merged work (PR #78). This
> one covers **§3.5, the nightly backup**, which extends Build C rather than
> becoming its own build.
>
> **Branch** `feature/swayam-nightly-backup-054` · **Pull request** https://github.com/Abhishek-POSdesign/Swayam-Capital/pull/81
> **Worktree** `.claude/worktrees/swayam-cloud-hygiene-052`, own venv,
> `import swayam` re-proved to resolve inside it after the branch switch.
>
> **§3.5 IS BUILT.** What is not done, and what needs his hand, is section 6.

---

## 1. ⚠️ A LIVE HAZARD ON HIS DISK, STILL TRUE

**The corrected lifecycle rule is applied to the bucket and working.** Read back
tonight: `{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 365}}]}`

**But two checkouts still hold the BROKEN file**, and one is where he works:

| Location | Branch | File |
|---|---|---|
| **Primary folder** | `feature/swayam-look-clarity-055` | **BROKEN — three dead `db/` rules** |
| Build B worktree | `feature/swayam-build03-resting-orders-044` | **BROKEN** |
| This worktree | off current `main` | correct |

He ran the update command tonight and it failed **only because the path was
wrong**. Had it resolved it would have re-applied `Delete` at 30/365/1825 days
**all on prefix `db/`**, where the 30-day rule fires first and the others can
never act, while the real backups under `supabase/` match nothing at all.

**It is already applied and must not be run again from an old checkout.**

---

## 2. THE WORKTREE RULE — CORRECTED IN BOTH FILES

`CLAUDE.md` and `docs/builds/README.md` said *"never a git worktree, work in the
primary folder"* — the right reason attached to the wrong rule, and it
contradicted his own instruction to use a worktree. Now both say:

> Never a worktree that **SHARES** the primary folder's venv, because that venv
> is an editable install pointing at the primary tree. **A worktree with its OWN
> venv is allowed**, and must prove `import swayam` resolves inside itself first.

**A practical note for the next worktree builder:** `pip install -e .` fails on
Python 3.13 because `aiohttp` will not build from source. What worked was
freezing the known-good venv (`pip freeze`, stripping the editable `swayam`
line), installing with `--no-deps`, then `pip install -e . --no-deps`.

---

## 3. THE ROLLBACK WINDOW — BOTH HALVES, IN BUILD_05

- A rollback left serving for weeks ages out of the newest twenty and loses its
  image. **Recovery is one deploy from `main`.** Nothing is lost.
- **Two days is the RIGHT delete window, not an oversight.** It is what stops
  twenty becoming eighty. **Do not widen it later believing you are helping.**

Also recorded there: why the built policy keys on **count and age, never
tagged-versus-untagged** — once every image carries its commit SHA, a tag test
protects everything for ever.

---

## 4. §3.5 AS BUILT — TWO HALVES, AND WHY

**There was no scheduled backup anywhere.** Verified: the only deployed Cloud
Function is `swayam-recorder`; the only scheduler jobs were the recorder and the
AI compaction.

| The job | Where the data lives | Runs |
|---|---|---|
| Supabase → bucket | Both on the network | **Cloud, 02:00 IST** |
| Vault copy, newest thirty | `G:\My Drive\Second Brain` — his PC | **Local, 03:00 IST** |
| History sync, 631 MB | `data/history` — his PC | **Local, 03:00 IST** |
| Data Map section 7 | Repo + vault — his PC | **Local, 03:00 IST** |

The vault is a **local filesystem path** (`settings.vault_path`), not an API. A
data-centre job can reach neither it nor his D: drive.

### ⚠️ THE ONE-HOUR GAP IS ORDERING, NOT PADDING

**The local half copies the NEWEST backup out of the bucket.** If both halves
started at 02:00, the local one would race the cloud one and copy **last
night's** file while reporting success. **Nobody should close this gap later
thinking they are tidying up.** It is written into the script's own docstring
and into `cloudbuild.yaml`-adjacent comments for exactly that reason.

### What is deployed right now

| Resource | State |
|---|---|
| Cloud Run job `swayam-nightly-backup` | **Created**, `asia-southeast1`, runs `python -m swayam.services.record_backup --gcs` |
| Cloud Scheduler `swayam-nightly-backup-schedule` | **Created and ENABLED**, `0 2 * * *` Asia/Kolkata, next fire 02:00 IST |

**The job cannot succeed until PR #81 merges**, because the current image
predates the module. Tested rather than assumed — it failed with
`No module named swayam.services.record_backup`. **Left enabled deliberately: it
self-heals on the first build after merge, so he has nothing to remember.** One
or two failed executions in the log before then are expected and harmless; the
manual backups from tonight are current.

---

## 5. ADDITION TWO — THE DEAD FUNCTIONS. DECIDED: `scripts/backup_supabase.py` WINS.

`functions/cron_backup_db`, `cron_backup_ai_chat` and `cron_backup_weekly_zip`
**have never been deployed.** That is why `db/`, `ai-chat/` and `weekly/` sit in
the bucket with nothing maintaining them. **A thing built and never deployed
looks exactly like a thing that works, so they are marked dead here.**

**The decision, and it is not close.** `cron_backup_db` calls
`swayam/services/backup_service.py`, which contains this:

```python
except Exception as exc:
    logger.warning("Could not export table %s: %s", table_name, exc)
    data_by_table[table_name] = []
```

**A table it cannot read is silently recorded as EMPTY and the backup continues
and reports success.** A Supabase hiccup on `swayam_positions` would produce a
"successful" backup containing no positions — the exact failure that stops you
looking for the real backup.

Against that, the chosen path:

| | `backup_service.py` (dead) | `record_backup.py` (chosen) |
|---|---|---|
| Tables | 19 | 19 — same coverage |
| Unreadable table | **silently empty, job succeeds** | **fails the job** |
| Upload failure | not verified | **fails the job** |
| Objects verified after upload | no | **yes, counted** |
| Row counts + SHA-256 manifest | no | **yes** |
| Refuses schema-less backup | no | **yes** |
| **Restore drill** | never run | **passed, 19 tables, 600 rows** |

**A backup whose restore has never been tried is not a backup.** That is the
deciding line.

**Recommendation to the orchestrator:** delete those three directories in a
later docs/cleanup pass, or leave them with a dead marker. They are not wired to
anything and nothing in this build touches them.

---

## 6. ⚠️ WHAT ABHISHEK MUST DO HIMSELF

**a) The first history push, ~631 MB, once.**
Deliberately not automatic, so it never competes with his connection while he is
working. From the **primary folder** after merge:

```
.\.venv\Scripts\python.exe scripts/nightly_local.py --first-history-push
```

Until it runs, the nightly task prints a clear line saying the history is not
copied and how to copy it. **Cost afterwards: ₹1.07 a month** — read from
Google's Billing Catalog API, 1,218 SKUs scanned, Standard Storage Singapore at
$0.020/GiB/month.

**b) Register the local nightly task at 03:00.**
Run once, in PowerShell as himself, from anywhere:

```powershell
$root   = "D:\Claude\POS\Trading-Platform\Swayam Capital"
$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" `
                                  -Argument "scripts\nightly_local.py" `
                                  -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -Daily -At 3:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "Swayam nightly local" -Action $action `
                       -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` is the catch-up: a night his PC was off runs at next
logon rather than being skipped in silence. **This build did not register it —
a scheduled task is a system setting and is his to create.**

**c) Look at the Home line in both themes.** See section 7.

---

## 7. VERIFIED, AND THE ONE THING NOT VERIFIED

| Claim | Proof |
|---|---|
| Worktree isolated | `import swayam` resolves inside this worktree, re-proved after the branch switch |
| Backup works end to end | 19 tables, **900 rows**, **21 objects uploaded and verified** through the new storage-client path |
| Bucket state | Three backups present: 07 Sep, and two from 11 Sep |
| Local task works | Vault copy landed; **both** Data Map copies refreshed. **The `history_local` result was recorded here as a pass and it was a FAULT — see 7.1.** Re-run from the primary folder 2026-09-12 00:47 IST and now correct |
| Data Map markers respected | Everything above the opening marker untouched, end marker intact |
| Home line | Rendered on the running page against the real backend: *"Your record was backed up less than an hour ago · 19 tables, 900 rows · protects against damage inside the database, not loss of the project"* |
| Backup-age endpoint | `HTTP 200` through the real server, correct live JSON |
| Tests | **Python 706 passed, 0 failed. JavaScript 348 passed**, including the bundle and syntax check |
| Vault untouched | Journal folder: **1 note before, 1 after** |
| Cloud job | Tested; failed exactly as predicted pending the post-merge image |

**⚠️ NOT VERIFIED: how the Home line LOOKS in each theme.** The accessibility
tree confirms the rendered text and the bundle test passes, but the browser
pane returned blank screenshots for this layout and I could not get a usable
image. **The text and behaviour are proven; the appearance is not.** Worth his
eye after merge. It uses the existing `.why` class, and `var(--down)` when stale,
both already theme-aware.

---

### 7.1 ⚠️ THE FAULT THIS HANDOFF ORIGINALLY RECORDED AS A PASS

**Found by the main chat reviewing PR #81, fixed on `feature/swayam-backup-messages-057`.**

The row above used to read: *"`history_local` correctly said `unavailable —
data/history not present on this machine`"*. It was presented as proof the
error path worked. **It was a false statement about his machine, published into
his vault.**

**What was actually wrong.** `history_local()` looked in exactly one place —
`ROOT_DIR / "data" / "history"`, where `ROOT_DIR` is wherever the script runs
from. Run from the worktree, that folder is legitimately absent, because
`data/` is gitignored and a worktree starts without ignored files. The script
then drew a conclusion about **his whole machine** from that single lookup. The
truth was **631 MB sitting in his primary folder.**

**Two consequences, and the second is the serious one:**

1. This handoff recorded a wrong answer as a verified pass.
2. **The Data Map in his vault — the note he hands to future chats — stated
   that his most vulnerable data was missing.** Data that exists in exactly one
   place on Earth, that took 8,576 FYERS requests to assemble.

**The fix was the message, not the logic.** The logic was right: in production
the task runs from the primary folder, where that path is correct.

```
before:  "data/history not present on this machine"     a claim about the machine
after:   f"data/history not found at {src}"             a statement of what and where
```

**Swept across every message in the script, and made structural rather than
left to care.** `attempt()` now takes a required `where` argument naming WHAT
was being read, and each function's own error names WHERE it looked. A message
that cannot say both is now impossible to write by omission:

| Figure | Message shape now |
|---|---|
| local history | `could not read the local backtest history: data/history not found at <full path>` |
| bucket reads | name the exact `gs://bucket/prefix/` |
| gcloud reads | name the command that failed and its exit code |
| the database | names the table |

The same sweep was applied to `record_backup.py`, which feeds the Home line.

**Corrected in his vault at 2026-09-12 00:47 IST**, re-run from the primary
folder. It now reads:

```
| Backtest history on my PC | 630 MB at D:\...\Swayam Capital\data\history |
| Backtest history copied to the bucket | nothing under gs://swayam-backups/history/ yet |
```

**The lesson worth keeping:** a message that names the path it looked in cannot
mislead, and this one would have shown the fault to its own author immediately.
Every "unavailable" in this project should say what it could not read and where
it looked, and never a conclusion about the machine, the account or the world.

---

## 8. FOR THE MAIN CHAT

1. **The one-hour gap between the halves is load-bearing.** Section 4.
2. **The three `cron_backup_*` directories are dead.** Section 5. Decide whether
   to delete them or mark them in the tree.
3. **`data/history` still has no copy** until he runs 6(a). It is 631 MB of
   four years of market data existing in exactly one place.
4. **Two stale checkouts hold the broken lifecycle file.** Section 1.
5. ~~**The build machine change from PR #78 is still unmeasured.**~~ **MEASURED
   2026-09-12 — see 9.3. `E2_STANDARD_2` is not a problem.**
6. **The Home line's appearance is the only unverified thing in this build.**
7. **#81 shipped a Dockerfile line that could not work and the build failed.**
   Section 9. Fixed on `feature/swayam-dockerignore-migrations-058`, and this
   time proved by building the image.

---

## 9. ⚠️ THE BUILD FOR #81 FAILED. THE WORK NEVER WENT LIVE.

**Found by the main chat, 2026-09-12.** The site was never at risk — it kept
serving the image from #78, which carries the new look. Only #81 was missing.

```
Step 0: COPY failed: file not found in build context or excluded by
        .dockerignore: stat migrations/: file does not exist
```

### 9.1 What was wrong, and why the verification did not catch it

#81 added `COPY migrations/ ./migrations/` to the `Dockerfile`. **`.dockerignore`
excluded `migrations/`**, so the folder was never in the build context. The two
files contradicted each other and nothing reconciled them.

**The backup was proven on a developer's disk, where `migrations/` is simply
present. The image was never built.** Every test that passed — 19 tables, 900
rows, 21 objects verified — passed outside the container. It was a path nobody
ran.

**The fix:** `migrations/` **removed** from `.dockerignore`, not re-included
with a negation, because directory negation in `.dockerignore` is unreliable.
The folder is 118 KB.

### 9.2 PROVED BY BUILDING THE IMAGE, NOT BY READING THE DOCKERFILE

Cloud Build `5d104148-81e3-4b61-980b-5e8836d0dc39`, **SUCCESS in 2m32s**. The
build pushed nothing and deployed nothing — no `images:` key — then looked
inside the image it had just made:

```
Step #0  Step 15/20 : COPY migrations/ ./migrations/

Step #1  ls -la /app/migrations
         total 140
         -rw-rw-rw- 1 root root 18222 000_baseline.sql
         -rw-rw-rw- 1 root root  4680 001_initial_schema.sql
         ... every migration present

Step #2  PROOF: _baseline_sql resolved to /app/migrations/000_baseline.sql
         PROOF: exists = True | bytes = 18222
```

Step #2 calls **the exact function that would have failed**. The build was cold,
not cached: `npm ci` installed 52 packages and pip installed its collected
packages in the same run.

### 9.3 THE BUILD MACHINE, MEASURED AT LAST

**2m32s on `E2_STANDARD_2`**, against a 4m52s average on `E2_HIGHCPU_8`.

**Not a like-for-like comparison, and it should not be quoted as one:** the
4m52s average covered build + push + deploy, while this run was build plus two
seconds of verification, with no push and no deploy. **What it does establish is
that the image build itself is comfortably fast on the default machine** — far
under the fifteen-minute threshold he set for reverting. The true like-for-like
is the first real trigger build after this merges.

### 9.4 WHAT THE CODE READS AT RUNTIME, AND WHETHER IT IS IN THE IMAGE

He asked for this sweep because `.dockerignore` also excludes `scripts/`,
`tests/` and `docs/`.

| What the code reads | Excluded by `.dockerignore`? | In the image? |
|---|---|---|
| `migrations/000_baseline.sql` — the backup's schema | **was excluded** | **THE BUG. Now in, and proved** |
| `src/swayam/data/method_files/` — trading brief, risk and readiness rules | no | **yes**, `COPY src/` |
| `data/nse_holidays_2026.json`, `data/nifty50_constituents.json` | re-included by negation | **yes**, copied explicitly |
| `data/backups/<stamp>/` — where the backup writes | `/data/*` excluded | **fine** — created at runtime with `mkdir(parents=True)`, never read from the image |
| `web/dist/` | excluded from context | **yes** — built in stage 1 and copied from it, not from the context |
| `scripts/` — the CLI wrappers | **excluded** | **no, and nothing needs it.** The Cloud Run job runs `python -m swayam.services.record_backup`, the module, not the script |
| `tests/`, `docs/`, `*.md` except README | excluded | no, and nothing reads them at runtime |

**One pre-existing instance of the same shape, not introduced by this build and
not fixed here:** `src/swayam/local_db.py:87` does
`from scripts.apply_duckdb_migrations import apply_duckdb_migrations`, and
`scripts/` is excluded from the image. **It is wrapped in `try/except` with a
fallback that creates the table directly**, so it degrades rather than breaks,
and DuckDB is local-backtesting rather than a container path. Worth knowing it
is there.

### 9.5 THE LESSON, WHICH IS RECORDED IN BUILD_05 §3.5 TOO

> "It heals on the first build after merge" assumed that build would succeed.
> **An enabled scheduler pointing at an image that does not exist yet is a
> promise resting on a build nobody had run.**

Two rules follow:

1. **A change to the `Dockerfile` or `.dockerignore` is not verified until an
   image has been BUILT.** Reading either file proves nothing — they interact,
   and the interaction is exactly where this failed.
2. **Do not enable a schedule pointing at an artefact that does not exist yet.**
   Build it first, or leave the schedule off until something real is behind it.
   "It will heal itself" is a forecast, not a verification.
