# BUILD C, CLOUD HYGIENE — HANDOFF TO THE MAIN CHAT. 2026-09-11 evening.

> Written by the Build C builder chat. Everything below was checked on the
> running system today, with the command that produced it. Where something was
> not done, it says so plainly.
>
> **Branch** `feature/swayam-cloud-hygiene-052` · **Pull request** https://github.com/Abhishek-POSdesign/Swayam-Capital/pull/78
> **Worktree** `.claude/worktrees/swayam-cloud-hygiene-052` with its own venv.
> The primary folder was never touched; it is on `feature/swayam-look-round2-053`.

---

## 1. THE HEADLINE

| | Before | After |
|---|---|---|
| Dashboard images in `asia-southeast1/swayam` | **84** | **19** |
| Cloud Run revisions | **83** | **20** |
| Freed | — | **27.72 GB** |

**Artifact Registry's reported repository size still reads ~34 GB. That figure
is recomputed asynchronously by Google and lags by hours. The contents are 19
images. Judge by the image count, not the size field, until it catches up.**

---

## 2. THE THING THE BUILD DOCUMENT GOT WRONG, AND WHY IT MATTERED

§3.2 as written would have freed **0.85 GB of 35.4**, not the "under 5 GB" it
predicted. His own safety instruction is what caught it.

**Every Cloud Run revision pins an image digest.** There were 82 revisions
pinning **81 of the 83 images**. Only 2 images were referenced by nothing. A
cleanup policy that spares anything a revision points at therefore had almost
nothing to delete.

**The unlock was deleting old revisions first.** Nothing prunes Cloud Run
revisions — Artifact Registry's cleanup policy runs on its own, revisions do
not. Once 63 revisions were deleted, 65 images became genuinely unreferenced
and 27.72 GB became reclaimable.

**Two further contradictions inside §3.1 and §3.2, both now resolved:**

1. §3.1 tags every image by commit SHA. §3.2 says *keep every tagged image*.
   Together they would never delete anything again and the problem returns in a
   month. **The policy now keys on count and age, never on tagged-versus-untagged.**
2. §3.2's "expect under 5 GB" was right about the destination but silent about
   the revision prune that makes it reachable.

---

## 3. WHAT WAS BUILT

### 3.1 Stop making the waste — DONE

- **`cloudbuild.yaml` machine type `E2_HIGHCPU_8` → `E2_STANDARD_2`.** The
  2,500 free build-minutes a month apply **only** to `e2-standard-2` in the
  default pool; every other machine bills from the first minute. At ~1,450
  build-minutes a month that was **$22.62–$31.67 ≈ ₹1,968–2,755 every month
  since 4 September**, against **₹0** on the default machine. Sources:
  [pricing](https://cloud.google.com/build/pricing),
  [pricing update](https://cloud.google.com/build/pricing-update).
- **Documents-only merges no longer build.** `ignoredFiles` added to the
  `swayam-main-deploy` trigger: `docs/**`, `**/*.md`, `.claude/**`, `CHANGELOG.md`.
  Verified by reading the trigger back.
- **Images now carry their commit.** The trigger passes `_TAG=$SHORT_SHA`, so
  every build tags the SHA and `latest`, and the deploy uses the SHA image.
  A rollback stops being a guess.

### 3.2 Clear what piled up — DONE

- 63 revisions deleted by hand, then 65 unreferenced images.
- **Cleanup policy live on both `swayam` repositories** (`asia-southeast1` and
  `asia-south1`), read back to confirm it is not in dry-run mode:
  - `keep-newest-20` — KEEP, `mostRecentVersions.keepCount: 20`
  - `delete-older-than-2-days` — DELETE, `olderThan: 172800s`
- **A standing prune step now runs inside every deploy** (`cloudbuild.yaml`
  step 4). It holds revisions at twenty for ever. Three properties, all
  deliberate:
  - **It never fails the build.** Every path ends `exit 0`. A deploy that
    succeeded must never show red because tidying afterwards hit a problem.
  - **It refuses to touch whatever serves traffic**, by name, whatever its age.
  - **It prints every name it deletes** into the build log, not a count.
  - If it cannot read what is serving, it prunes **nothing** and says so.
- **Permission checked before merge, not on the first deploy.** The trigger
  runs as `535273918813-compute@developer.gserviceaccount.com`, which holds
  `roles/editor`, `roles/iam.serviceAccountUser` and **`roles/run.admin`**.
  That role's 97 permissions include `run.revisions.delete`, `run.revisions.list`
  and `run.services.get`. **No grant is needed.**

### 3.3 The two dead services — ALREADY GONE

`asia-east1` has no Cloud Run services at all; `asia-south1` has only
`swayam-recorder`. Both dead `swayam-dashboard` copies were removed before this
session reached them. The domain maps to `asia-southeast1` only, confirmed.

**⚠️ ONE PIECE REMAINS AND IT NEEDS HIS HAND — see section 6.**

### 3.4 The recorder writes one file — DONE

Flat write removed from `cloud/recorder/fyers_recorder.py`. The nested path is
authoritative. **The six existing flat objects were deliberately NOT deleted.**
The authoritative-path note is written into
`docs/builds/BUILD_05_CLOUD_HYGIENE.md` under §3.4, with the overlap dates.

The reason was never storage — it was that a backtest walking the bucket by
prefix would find the same trading day under two names and count it twice.

### 3.5 The nightly backup — HALF DONE, AND THE HALF THAT WAS URGENT

**A backup was taken by hand before any infrastructure was touched**, because
his record had been unprotected since 7 September with an open trade in it.

```
gs://swayam-backups/supabase/2026-09-11T13-18-31Z/
19 tables · 883 rows · 21 objects, verified in the bucket
```

Confirmed inside it: the open condor `7cd4d017-2c92-445a-a348-28f395c03db8`,
`status: open`, `closed_at: None`, opened 2026-09-10.

**NOT BUILT: the Cloud Scheduler job, the thirty-night vault copy, and Home's
last-backup age.** That is the remaining chunk of this build.

### 3.6 The lifecycle rule — WRITTEN, DELIBERATELY NOT APPLIED

The build document says to show him the rule in plain English before applying
it, because a wrong lifecycle rule deletes his only copy. **So it is committed
but not applied. See section 6.**

### 3.7 The SIGABRT — SOLVED AND FIXED

```
09:22:29  last normal activity
          ...25 seconds of nothing...
09:22:54  Could not read the FYERS token from Secret Manager
          (504 Deadline Exceeded); using the token the container
          started with, which may be stale.
09:22:55  [CRITICAL] WORKER TIMEOUT (pid:2)
09:22:56  Uncaught signal: 6
09:23:08  Booting worker with pid: 88
```

`src/swayam/services/fyers_token.py` called `access_secret_version` with **no
timeout**. A slow Secret Manager held the worker past gunicorn's 60-second
limit and it aborted. The stale-token fallback was already correct and simply
never ran in time. Fixed with `timeout=5.0`, far under the worker timeout, so
the fallback now wins the race. Obvious and small, exactly what §3.7 permits.

---

## 4. VERIFICATION, BY INVOKING

| Claim | Proof |
|---|---|
| Worktree is isolated | `import swayam` resolves to `.claude/worktrees/swayam-cloud-hygiene-052/src/swayam/__init__.py` through that worktree's own interpreter |
| Live site unharmed | `https://swayam.abhisheksikka.com` → **HTTP 302** (IAP challenge) before and after every destructive step |
| Revisions pruned | 83 → 20, counted from `gcloud run revisions list` |
| Images cleared | 84 → 19, counted from `gcloud artifacts docker images list` |
| Nothing deleted that a revision pins | Exclusion list of 19 digests built from live revisions, each mapped to its revision by name, printed before deletion. 63 revision deletions and 65 image deletions, **0 failures** |
| Backup real | 21 objects listed in the bucket; open condor found inside the file |
| Tests | **705 passed, 1 failed** — identical to the baseline before any change |
| Vault untouched | Journal folder: **1 note before, 1 note after**, both runs |

---

## 5. ⚠️ A FAILURE ON `main` THAT IS NOT THIS BUILD'S

`tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`
fails on `main` today.

**Round 1b (#74) changed `build_spread_from_request` to return three values and
updated all four real call sites, but left a stale two-value mock in that test.**

Proven, not assumed: stashing this branch's only source change and re-running
produces the identical failure.

**It is a stale test, not a live bug.** `strategy.py:38` declares a 3-tuple,
`strategy.py:122` returns three, and `execution.py:826`, `execution.py:1334`,
`execution.py:1718` and `validation.py:94` all unpack three. His money path is
sound. **Left untouched deliberately — it belongs to the polish chat.**

---

## 6. ⚠️ WHAT ABHISHEK MUST DO HIMSELF

**a) Delete the leftover `asia-south1/swayam` repository (1.68 GB).**
Attempted and **blocked by a safety guardrail** — deleting a whole repository
needs his hand. Verified safe first: the recorder runs from `gcf-artifacts`,
not this repo, and this repo holds only dead 4-September dashboard images.
**`asia-south1/gcf-artifacts` belongs to the recorder. Leave it.**

```
gcloud artifacts repositories delete swayam --location=asia-south1 --project=swayam-capital
```

**b) Approve the lifecycle rule, then apply it.** In plain English, the new
rule says: **everything in the backup bucket is kept for one year, then
deleted.** Nothing else.

Why it replaces a tiered rule: the whole bucket is **2.7 MB**, and a year of
nightly backups is well under a gigabyte. Tiering would add machinery to save
nothing. And GCS lifecycle cannot express "keep one a month" without object
versioning, so keeping everything for a year is both simpler and *more*
history than the original intent.

What was wrong before: three `Delete` rules all sat on prefix `db/` at 30, 365
and 1825 days. **The 30-day rule fires first and deletes everything, so the
other two could never act.** Worse, the real backups live under `supabase/`,
which **no rule matched at all** — they were governed by nothing.

```
gcloud storage buckets update gs://swayam-backups --lifecycle-file=gcs_lifecycle_backups.json
```

**c) Watch the first build after merge.** The machine type changed. Per his
instruction: **if it comes in under about fifteen minutes it stays. If it goes
far beyond that, or fails for a reason the machine caused, put it back** —
one line in `cloudbuild.yaml`, `E2_STANDARD_2` → `E2_HIGHCPU_8`. The previous
average was **4m52s** on 8 vCPU.

---

## 7. FOR THE MAIN CHAT SPECIFICALLY

1. **§3.5 is the outstanding half of this build** — the Cloud Scheduler nightly
   job, the thirty-night vault copy, and Home's last-backup age. The manual
   backup closed the urgent gap; the standing one is not built. Decide whether
   it extends this build or becomes its own.
2. **The builders' README is wrong about worktrees** on both `main` and the
   051 branch: *"never a git worktree, work in the primary folder."* The real
   rule, as he stated it tonight, is **never a worktree that shares the primary
   folder's venv**, because that venv is an editable install pointing at the
   primary tree and a builder would silently test the wrong source. A worktree
   **with its own venv** is how Build B and Build C were both done.
3. **The stale test in §5 needs an owner.** It is round 1b's.
4. **One rollback edge case, named rather than engineered around**, on his
   instruction: a cleanup policy cannot name a digest. Keeping the newest
   twenty covers the live image in practice, because the live revision is
   normally the newest deployed. **The exception is a rollback left live for
   weeks, whose serving digest would slowly age out of the newest twenty.** The
   prune step refuses to delete whatever serves traffic, which protects the
   revision; the image behind it is the residual risk. No machinery was built
   for this, deliberately.
5. **Watch the image count over the next week**, not the size field. Expect it
   to sit at or under 20, and revisions at 20, with no further intervention.
