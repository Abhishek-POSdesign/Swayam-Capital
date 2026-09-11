# BUILD C PART TWO — HANDOFF TO THE MAIN CHAT. 2026-09-11, later the same evening.

> Written by the Build C builder chat. The first handoff,
> `docs/BUILD_C_HANDOFF_2026-09-11.md`, covers the merged work (PR #78). This
> one covers the SECOND pull request, which extends Build C rather than
> becoming its own build, on his instruction.
>
> **Branch** `feature/swayam-nightly-backup-054`, cut off `main` at `aab9f54`
> (after #76, #77, #78 and #79 were all merged).
> **Worktree** `.claude/worktrees/swayam-cloud-hygiene-052`, reusing Build C's
> venv. `import swayam` re-proved to resolve inside that worktree after the
> branch switch.
>
> **§3.5 IS NOT BUILT YET.** Everything below §4 is done and committed. §3.5 is
> designed, unblocked, and described here so the orchestrator can object before
> it is built.

---

## 1. ⚠️ A LIVE HAZARD ON HIS DISK, RIGHT NOW

**The corrected lifecycle rule is applied to the bucket and is working.**
Verified by reading it back tonight:

```json
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 365}}]}
```

**But two checkouts on his machine still hold the BROKEN file**, and one of
them is the folder he actually works in:

| Location | Branch | File |
|---|---|---|
| **Primary folder** | `feature/swayam-look-clarity-055` (cut before #78 merged) | **BROKEN — three dead `db/` rules** |
| Build B worktree `nifty-resting-orders-074c38` | `feature/swayam-build03-resting-orders-044` | **BROKEN** |
| Build C worktree | off current `main` | correct |

He ran the update command tonight and it failed **only because the path was
wrong.** Had it resolved, it would have re-applied the three dead rules:
`Delete` at 30, 365 and 1825 days, **all on prefix `db/`**, where the 30-day
rule fires first and the other two can never act — while the real backups under
`supabase/` match no rule at all and are governed by nothing.

**Nobody should run this command from an old checkout:**

```
gcloud storage buckets update gs://swayam-backups --lifecycle-file=gcs_lifecycle_backups.json
```

It is already applied and does not need running again. Once those branches
merge or rebase onto `main` there is one file and the hazard is gone.

---

## 2. THE WORKTREE RULE, CORRECTED IN BOTH PLACES

`CLAUDE.md` and `docs/builds/README.md` both said *"never a git worktree, work
in the primary folder."* That was **the right reason attached to the wrong
rule**, and it bit this builder: it contradicted his own instruction to use a
worktree because another chat held the primary folder.

**The real rule, now written in both files:**

> Never a worktree that **SHARES** the primary folder's venv, because that venv
> is an editable install pointing at the primary tree and a builder using it
> would silently test the wrong source. **A worktree with its OWN venv is
> allowed**, and is how Build B and Build C were both done.

Both files now also carry the proof a worktree builder must run first:

```
.\.venv\Scripts\python.exe -c "import swayam; print(swayam.__file__)"
```

The printed path must contain that worktree's own folder name.

**Note for the orchestrator:** the venv itself is not trivial to stand up.
`pip install -e .` fails on Python 3.13 because `aiohttp` will not build from
source. What worked was freezing the known-good venv (`pip freeze`, stripping
the editable `swayam` line) and installing it with `--no-deps`, then
`pip install -e . --no-deps`. Worth knowing before the next worktree builder
loses twenty minutes to it.

---

## 3. THE ROLLBACK WINDOW, BOTH HALVES, IN BUILD_05

Added to `docs/builds/BUILD_05_CLOUD_HYGIENE.md` under §3.2, in his framing,
so nobody widens the window later believing they are helping:

- **A rollback left serving for weeks** will age out of the newest twenty and
  eventually lose its image. The revision is safe — the prune step refuses to
  delete whatever serves traffic — but the image behind it is not.
  **The recovery is one deploy from `main`.** Nothing is lost.
- **Two days is the RIGHT delete window, not an oversight.** It is precisely
  what stops twenty becoming eighty again. A longer window is how 35.8 GB
  accumulated in the first place.

The same section now also records **why the built policy differs from what the
document specified**: it keys on **count and age, never tagged-versus-untagged**,
because once §3.1 tags every image with its commit SHA, a "keep every tagged
image" rule protects everything for ever and the pile returns within a month.

---

## 4. THE COST OF COPYING HIS BACKTEST HISTORY: ₹1.07 A MONTH

He asked to be told before it is switched on. Read from **Google's own Cloud
Billing Catalog API**, not quoted from memory — 1,218 Cloud Storage SKUs
scanned:

| | |
|---|---|
| Standard Storage Singapore (`asia-southeast1`, where `swayam-backups` lives) | **$0.020000 per GiB/month** |
| Standard Storage Mumbai (`asia-south1`) | $0.023000 per GiB/month |
| His `data/history` | **631 MB = 0.616 GiB** |
| **Cost** | **$0.0123/month ≈ ₹1.07/month** |

At ten times the size it is about ₹11 a month.

**What is at stake for that rupee:** `data/history` exists **only on his PC**
and nowhere else. From `PLAN.md` §2.15: 59,292,184 minute option bars (540 MB),
4,569,843 NSE daily option rows (73 MB), 804,379 NIFTY minute bars, 4,141 daily
bars. The minute bars alone took **90 minutes and 8,576 FYERS requests** to
assemble. `data/` is gitignored, so git does not hold it. The roadmap says the
bucket is its copy; **that copy has never been made.**

---

## 5. §3.5 AS IT WILL BE BUILT — THE ORCHESTRATOR SHOULD OBJECT NOW IF AT ALL

### 5.1 It cannot be one job, and here is why

| The job | Where the data lives | Can a cloud job do it? |
|---|---|---|
| Supabase → bucket | Both on the network | **Yes** |
| Vault copy, last 30 nights | `G:\My Drive\Second Brain` — **his PC** | **No** |
| History sync, 631 MB | `data/history` — **his PC** | **No** |

The vault is reached as a **local filesystem path** (`settings.vault_path` in
`journal_writer.py`), not an API. Cloud Scheduler runs in a Google data centre
and can reach neither his G: drive nor his D: drive. A single cloud job would
therefore deliver the database backup and silently do nothing for the other
two.

### 5.2 His schedule, which resolves the timing question

**Confirmed by him 2026-09-11: his PC is on roughly 8–9 pm to 4 am** — he works
a night shift. So **02:00 IST, as §3.5 specifies, falls inside his PC-on
window**, and it is nowhere near his trading window of 1:00–2:30 pm. The
original instruction — "never in his window and never something he has to
remember" — is satisfied.

### 5.3 The shape

- **Cloud half.** Cloud Scheduler → the Supabase backup, **nightly 02:00 IST**,
  writing to `gs://swayam-backups/supabase/`. Runs whether his PC is on or not.
  **This is the half that protects his trade record and it must not depend on
  his machine being awake**, because "mostly on" is not "always on".
- **Local half.** A scheduled task on his PC, also 02:00 IST, doing the vault
  copy (newest thirty, pruned, obeying the vault cage) and the history sync.
  With catch-up, so a night his PC was off runs at next logon rather than being
  skipped in silence.
- **The history sync is a sync, not a re-upload** — only what changed. Most
  nights that is nothing.
- **The first upload is 631 MB and will be a deliberate one-off he triggers**,
  not something that fires at 02:00 while he is working and competes with his
  connection. After it, the nightly sync carries only changes.
- **Home's last-backup age** reads the real newest object in the bucket, never
  a stored constant. Red past 48 hours. **It is the only line of Home this
  build touches**, per his standing rule for the night.

### 5.4 What the orchestrator should push back on if it disagrees

1. Splitting cloud and local at all, versus running everything locally.
2. Making the first 631 MB push manual rather than automatic.
3. 02:00 for the local half, given he is **awake and working** at 02:00 — a
   later slot such as 03:30 would be further from his attention, though still
   inside his PC-on window.

---

## 6. STATE OF THE BRANCH

| Commit | What |
|---|---|
| `b9977e9` | The worktree rule corrected; the rollback window explained in BUILD_05 |

Files changed so far: `CLAUDE.md`, `docs/builds/README.md`,
`docs/builds/BUILD_05_CLOUD_HYGIENE.md`.

**No pull request opened yet** — it opens when §3.5 is built, so the orchestrator
reviews one coherent change rather than a half-finished one.

**Nothing in §3.5 has been built.** The manual backup taken during Build C
(`gs://swayam-backups/supabase/2026-09-11T13-18-31Z/`, 883 rows, open condor
included) remains the only backup of his record newer than 7 September.

---

## 7. STILL TRUE FROM THE FIRST HANDOFF

- **No nightly backup runs anywhere.** Verified again tonight: the only deployed
  Cloud Function is `swayam-recorder`, and the only scheduler jobs are
  `swayam-recorder-schedule` and `swayam-ai-compaction`. The
  `functions/cron_backup_db`, `cron_backup_ai_chat` and `cron_backup_weekly_zip`
  directories exist in the repository but **are not deployed** — which is why
  the `db/`, `ai-chat/` and `weekly/` prefixes exist in the bucket with nothing
  maintaining them.
- Images sat at **19**, revisions at **20**, after the Build C cleanup.
- The build machine is now `E2_STANDARD_2`. **The first build after #78 merged
  is the measurement** — under about fifteen minutes and it stays; far beyond,
  or a machine-caused failure, and it reverts in one line.
