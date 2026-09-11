# BUILD 05 — CLOUD HYGIENE. Cut the waste, keep the capability. "BUILD C"

> Written 2026-09-11 evening by the main chat, from his cost chat's audit and
> from a fresh reading of the live Google Cloud project on the same evening.
> **Every figure in section 2 was read from the project today with the command
> that is named beside it.** Nothing here is quoted from the audit summary
> without being checked again.
>
> **His rule for this build, in his own words, 2026-09-11:** "whenever money is
> required, do not hold if the money provides real value. Otherwise, we'll cut
> it. I care about the quality." So this document separates waste from
> capability and never asks him to approve a saving that costs him something.
> His reason for urgency: the real bill has not arrived yet. The backtesting
> and the AI work are what will bring it, and he wants the waste gone before
> it does.
>
> **The prompt he pastes into the builder chat is in the fence below.**

---

## 0. BEFORE ANY BUILD: TWO COPIES OF HIS TERMINAL ARE OPEN TO THE INTERNET

**This is not a cost item and it is not a build. It is his decision tonight,
and it is two commands.**

Found while reading the project on 2026-09-11 evening. There are **three**
Cloud Run services called `swayam-dashboard`, not one:

| Region | Revision | Sign-in | What it is |
|---|---|---|---|
| `asia-southeast1` | `swayam-dashboard-00080-8rk` | **IAP enabled** | The live site, mapped to swayam.abhisheksikka.com. Correct |
| `asia-south1` | `swayam-dashboard-00004-2r2` | **NONE** | A 4 September build, last deployed 2026-09-04 17:23 |
| `asia-east1` | `swayam-dashboard-00002-9ll` | **NONE** | A 4 September build, created 2026-09-04 13:35 |

The two dead ones carry `allUsers` in `roles/run.invoker` with ingress `all`
and **no Identity-Aware Proxy**. The live one carries `allUsers` too, but it is
fronted by IAP, which is why that binding is correct there and dangerous here.

**And they hold his real secrets.** Read from the `asia-east1` service:
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, **`SUPABASE_SERVICE_ROLE_KEY`**,
`FYERS_ACCESS_TOKEN`, `FYERS_CLIENT_ID`, `FYERS_APP_ID`, `FYERS_SECRET_KEY`,
every one from Secret Manager at `latest`.

**So anyone with the URL gets a no-sign-in copy of his trading terminal, on a
4 September build, wired to his live database and his live FYERS session.**
There is no order-placement code anywhere in the repository, which is the only
reason this is not worse. It can still read and write his trade record.

**The immediate fix, which closes the door without deleting anything:**

```
gcloud run services remove-iam-policy-binding swayam-dashboard --region=asia-east1 --member=allUsers --role=roles/run.invoker --project=swayam-capital
gcloud run services remove-iam-policy-binding swayam-dashboard --region=asia-south1 --member=allUsers --role=roles/run.invoker --project=swayam-capital
```

Reversible in one command each. **Deleting the two services outright is
section 3.3 of this build**, and the safer order is: close them tonight, delete
them in the build. **The live service in `asia-southeast1` must not be
touched.**

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds exactly ONE thing: Build C, cloud hygiene. It cuts what my Google
Cloud project is wasting and it gives me the one capability I am missing,
a backup. The main chat planned it and will review it. You do not re-plan
it, you do not widen it, and you do not start anything else.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER.
1. docs/builds/README.md                  how a build works and the rules
2. docs/builds/BUILD_05_CLOUD_HYGIENE.md  THIS BUILD, the whole spec. Its
                                          section 0 is not yours: it is a
                                          decision I take myself
3. docs/PLAN.md 2.6 (the backup), 2.12.8 and 2.12.10
4. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
5. cloudbuild.yaml, gcs_lifecycle_backups.json, scripts/backup_supabase.py

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve,
a recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: awake around 1 pm IST, at the screen by
2 pm, I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data, ever, or unavailable with the reason. Never
say done, live or passing unless you checked it on the running system that
day and can show me the proof. A number you read from a billing page is
not proof that a deletion worked.

MY RULE FOR THIS BUILD. Do not hold back money that buys real value. Cut
everything that does not. If you are about to save me a rupee at the cost
of something I can do today, stop and ask me instead.

THE ONE THING THAT MUST NOT HAPPEN. The live site is Cloud Run
swayam-dashboard in asia-southeast1, behind Google sign-in, mapped to
swayam.abhisheksikka.com. Nothing in this build may take it down, change
who can reach it, or change what it runs. Every destructive command in
this build names its region, and you show me the command before you run
it. I have an open trade in the record and five days of trades that have
never been backed up.

HOW WE WORK. Plan first in plain English, six parts; I approve before any
code. Branch feature/swayam-build-c-cloud-hygiene-0NN off main, never
main. git fetch before every push and check whether my pull request has
already been merged. Hand off in five parts, files as clickable links,
manual steps in bold up front, one bold line saying what exists and what
does not.

DO NOT TOUCH: the live service's configuration beyond what section 3 says,
docs/ROADMAP.md, the recorder's maths, src/swayam/research/, the AI, the
Trade Journal page, the vault cage, the database guard, my trade record.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. Why does my image store grow by about four gigabytes a day, and which
   two lines of cloudbuild.yaml cause it?
2. What happens today when I merge a pull request that changes only
   documents, and what should happen?
3. When was my database last backed up, and what of mine is not in that
   backup?
4. Which Cloud Run service is the live site, and how will you prove you
   have not touched it?
5. What does the lifecycle rule on gs://swayam-backups actually do today,
   and what did it intend to do?
```

---

## 1. What this build is for

His billing is compounding and he has seen it. The cause is not the app: it is
the build pipeline keeping every image it has ever made, a deploy firing on
merges that changed nothing but words, two abandoned copies of the service, and
a recorder writing every file twice. Meanwhile the one thing that would
actually protect him, a nightly backup of his record, has run once by hand and
is four days stale.

**This build stops the waste at its source, clears what has piled up, and turns
the backup on.** It is a small build with a large bill attached to it.

---

## 2. What exists today. Every figure read from the live project, 2026-09-11 evening.

### 2.1 The image store, and why it grows

| | Read today |
|---|---|
| `asia-southeast1/swayam` | **33.1 GB** |
| `asia-south1/swayam` | 1.68 GB |
| `asia-south1/gcf-artifacts` (the recorder's) | 0.45 GB |
| **Total** | **about 35.3 GB** |
| Dashboard images in the live repository | **84**, of which **exactly one carries a tag** (`latest`). The other 83 are untagged and nothing deletes them |
| First and last | 2026-09-04 17:29 and 2026-09-11 11:26 IST, so about **11 images a day** |
| Each image | about **394 MB** |

**The cause is two lines in `cloudbuild.yaml`.** Every build tags the image
`:$_TAG` and `:latest`, and `_TAG` defaults to `latest`, so every build pushes
the same tag to a new digest. The previous digest loses its tag, becomes
untagged, and stays for ever. Nothing has a cleanup policy.

**What it costs.** Artifact Registry is $0.10 per GB per month above a 0.5 GB
free allowance. Today that is about **₹300 a month**. At 4.3 GB a day of new
images and nothing deleted, next month is about **₹1,200**, the month after
about **₹2,300**, and it keeps climbing, because the store never shrinks. That
compounding is what he is seeing.

### 2.2 Documents-only merges build and deploy the whole app

One Cloud Build trigger, `swayam-main-deploy`, on `push` to `^main$`, with
**no `ignoredFiles`**. So every merge builds a 394 MB image and deploys it.

**Verified by timestamps, not assumed:** pull request #70 on 2026-09-11 changed
only files under `docs/`, and an image was pushed at 10:16 IST, minutes after
it merged. The same is true of #73 this evening.

Roughly a third of recent merges are documents.

### 2.3 Three services where there should be one

Section 0 above. Two are dead, public, and hold his secrets.

### 2.4 The recorder writes every file twice

```
gs://swayam-capital-options-data/2026-09-09/nifty_chain.parquet
gs://swayam-capital-options-data/2026/09/09/nifty_chain.parquet
```

Three trading days, six objects, one flat path and one nested. By design, and
the design is wrong: one copy is enough. About 1.3 MB a day, so the money is
nothing. **The reason to fix it is not money. It is that a backtest reading the
bucket can read the same day twice**, and nothing on the screen would say so.

### 2.5 The recorder's schedule runs outside market hours

`swayam-recorder-schedule`, `*/1 9-15 * * 1-5`, Asia/Kolkata. That is every
minute from 09:00 to 15:59, weekdays: **420 invocations a trading day**, of
which about 44 fall before the open or after the close, and all of them fall on
exchange holidays, which the recorder's own gate then rejects.

**Measure before cutting.** Cloud Run's free allowance may already absorb this.
The builder reports the actual cost of the recorder for one month before
proposing any change, and if it is free he says so and changes nothing but the
out-of-hours minutes.

### 2.6 ⚠️ HIS RECORD HAS NOT BEEN BACKED UP SINCE 7 SEPTEMBER

The newest full backup in `gs://swayam-backups` is
`supabase/2026-09-07T17-12-15Z/`. **Nothing since.**

**What is therefore in no backup at all:** his three trades of 9 September, his
three of 10 and 11 September, the open condor `7cd4d017`, migrations 022, 023,
024 and 025, every target he has set, and every journal row written since.

`scripts/backup_supabase.py --gcs` works and its restore drill passed on 19
tables and 600 rows. **It has run once, by hand.** This is the capability half
of the build and it is the most valuable thing in it.

### 2.7 The backup bucket's lifecycle rule deletes what it meant to keep

`gs://swayam-backups` carries three lifecycle rules. All three are
`action: Delete` on prefix `db/`, at 30, 365 and 1825 days. **The 30-day rule
fires first and deletes everything, so the other two can never do anything.**
The intent was plainly a tiered retention, and the file
`gcs_lifecycle_backups.json` in the repository has the same fault.

Worse for today: the backup script writes under `supabase/`, and **no rule
matches that prefix at all**, so the real backups are governed by nothing.

### 2.8 The SIGABRT of 10 September

One `SIGABRT` on revision 00068 at 14:52 IST on 2026-09-10, inside his trading
window, cause unknown. Not investigated. **Find the cause in the logs. Do not
guess and do not "harden" anything until you know what it was.**

---

## 3. What to build, in this order

### 3.1 Stop making the waste

1. **Tag by commit, not by `latest`.** `cloudbuild.yaml` tags `$SHORT_SHA` and
   `latest`, and deploys the `$SHORT_SHA` image. Every build then has a name
   that says which commit it is, and a rollback stops being a guess.
2. **A documents-only merge must not build.** Add `ignoredFiles` to the
   `swayam-main-deploy` trigger for `docs/**`, `**/*.md`, `.claude/**` and
   `CHANGELOG.md`. Cloud Build skips the build only when EVERY changed file
   matches, so a merge touching one line of code still deploys.
   **Prove it both ways:** a documents-only push does not build, and a push
   touching one source file does.

### 3.2 Clear what has piled up

An **Artifact Registry cleanup policy** on both `swayam` repositories:
- keep every tagged image,
- keep the **10 most recent** versions whatever their tags,
- delete untagged versions older than **14 days**.

**Run it in dry-run first and show him the list and the gigabytes it would
free, before anything is deleted.** Then apply. Expect the store to fall from
about 35 GB to under 5 GB.

#### ⚠️ WHAT WAS ACTUALLY BUILT, AND WHY IT DIFFERS. Written by the Build C builder, 2026-09-11.

**The policy above would have freed 0.85 GB of 35.4, not "under 5 GB".** Two
faults in it, both found before anything was deleted:

1. **"Keep every tagged image" becomes "keep everything" the moment §3.1
   lands.** §3.1 tags every image with its commit SHA. A policy that spares
   tagged images would then spare all of them, for ever, and the pile returns
   within a month. **The policy therefore keys on COUNT and AGE, never on
   tagged-versus-untagged.**
2. **Nothing prunes Cloud Run revisions.** Artifact Registry's cleanup policy
   runs on its own; revisions do not. Every revision pins an image digest, so
   82 revisions were holding 81 of the 83 images alive. Deleting images first
   was impossible; **deleting the revisions first is what made 27.72 GB
   genuinely unreferenced.**

**What is live now, on both `swayam` repositories:**

| Policy | Action |
|---|---|
| `keep-newest-20` | KEEP, `mostRecentVersions.keepCount: 20` |
| `delete-older-than-2-days` | DELETE, `olderThan: 172800s` |

And a **prune step inside every deploy** (`cloudbuild.yaml`) holding revisions
at twenty for ever. It never fails the build, refuses to touch whatever serves
traffic, and prints every name it deletes.

#### ⚠️ THE ONE RESIDUAL RISK, NAMED RATHER THAN ENGINEERED AROUND

**A cleanup policy cannot name a digest.** Keeping the newest twenty covers the
live image in practice, because the live revision is normally the newest one
deployed.

**The exception:** a Cloud Run **rollback left serving for weeks** would slowly
age out of the newest twenty, and its image would eventually be deleted
underneath it. The revision itself is safe — the prune step refuses to delete
whatever serves traffic — but the image behind it is not.

**If that ever happens, the recovery is one deploy from `main`.** Nothing is
lost; the site is rebuilt from the commit it should have been on anyway.

**AND THE OTHER HALF, WHICH MATTERS JUST AS MUCH: two days is the RIGHT delete
window, not an oversight.** It is precisely what stops twenty becoming eighty
again. **Do not widen it later thinking you are being careful** — a longer
window is how 35.8 GB accumulated in the first place. The rollback case above
is the known, accepted, one-deploy-to-fix cost of keeping it tight.

### 3.3 Delete the two dead services

After section 0's bindings are removed and he has said yes, delete
`swayam-dashboard` in `asia-south1` and in `asia-east1`, then delete the
`asia-south1/swayam` repository once nothing references it. **The
`asia-south1/gcf-artifacts` repository belongs to the recorder. Leave it.**

Before and after, curl the live site and show it still answers, and show the
custom domain still maps to `asia-southeast1`.

### 3.4 The recorder writes one file, not two

One path, and the nested one is the one to keep, because it sorts and prefixes
properly for a bucket that will hold years. **Do not delete the six existing
objects.** Write a short note in the build document saying which path is
authoritative from which date, so a backtest reading history knows.

#### ⚠️ WHICH PATH IS AUTHORITATIVE. Written by the Build C builder, 2026-09-11.

**Anything reading the options history must use the NESTED path.**

```
gs://swayam-capital-options-data/YYYY/MM/DD/nifty_chain.parquet     <-- read this
gs://swayam-capital-options-data/YYYY-MM-DD/nifty_chain.parquet     <-- ignore this
```

| Dates | What exists | What to read |
|---|---|---|
| **2026-09-09 to 2026-09-11** | BOTH paths, written by the recorder as identical copies of the same data | The nested path. The flat copy is a duplicate, not a second day |
| **From 2026-09-12 onward** | The nested path ONLY | The nested path |

The recorder was writing every snapshot twice, to both layouts, by design. The
flat write was removed from `cloud/recorder/fyers_recorder.py` on 2026-09-11.
**The flat objects already written were deliberately NOT deleted**, so nothing
that already points at them breaks.

**The reason this mattered is not storage — it was about 1.3 MB a day.** It is
that a backtest walking the bucket by prefix would find the same trading day
under two different names and count it twice, with nothing on any screen saying
so. Any loader that globs the bucket must therefore filter to the nested layout
for the three overlapping days above.

### 3.5 The nightly backup, and its age on the screen

**Settled with him on 2026-09-11, after he asked what a fourth backup is even
for.** GitHub holds his code and can go back; it holds not one trade. The vault
holds his notes, which are a story rather than the numbers the app runs on, and
only exist where a writer succeeded. Supabase holds his trades and **is the
thing itself, not a copy of it**, with no snapshot to roll back to on the free
plan and two other apps sharing the project. **What no part of that survives is
damage inside the database**: a migration that changes a column the wrong way, a
script that updates the wrong rows, something overwriting a result.

His decisions, in his words where he gave them:

- **Automatic, nightly, at about 02:00 IST.** Never in his window and never
  something he has to remember.
- **Two places. The bucket keeps the full history. His vault keeps the last
  THIRTY nights**, his choice of 2026-09-11, because thirty megabytes is
  nothing and the point is being able to go back further than last night. This
  is the vault copy he asked for in §2.19: "I want backup to go in my vault in
  the Second Brain."
- The vault copy is the terminal's RECORD only, a few megabytes. **The market
  history never goes into the vault**; it stays in DuckDB with the bucket as
  its copy, PLAN §2.19.

Build it as:

- `scripts/backup_supabase.py --gcs` on a **Cloud Scheduler job, nightly**, at
  a time that is nowhere near his window. **Not 09:15.** Around 02:00 IST.
- The same run writes a copy into the vault, **pruned to the newest thirty**,
  and it obeys the vault cage exactly as every other writer does.
- A **last-backup age** on Home, from the real object in the bucket, never a
  stored constant. Red when it is older than 48 hours.
- Say plainly on the screen what it protects against: damage inside the
  project, not loss of the project itself.
- **Run it once by hand first and show him the new object**, then schedule it.

#### ⚠️ THE NIGHTLY JOB DID NOT SELF-HEAL, AND WHY THAT WAS PREDICTABLE

**Written 2026-09-12 after the build for #81 failed and the job never ran.**

The scheduler and the Cloud Run job were created and enabled on 2026-09-11,
pointing at `:latest`. The image at that moment did not contain the module, so
the job failed. **That was tested and known.** What was written in the handoff
was: *"Left enabled deliberately: it self-heals on the first build after merge,
so he has nothing to remember."*

**It did not self-heal. The build after merge FAILED**, at step 0, with
`COPY failed: stat migrations/: file does not exist`. The same pull request
that added the module also added a `Dockerfile` line that `.dockerignore`
forbade, so no new image was ever produced and the job kept failing against the
old one.

**The fault in the reasoning, which is the part worth keeping:**

> "It heals on the first build after merge" assumed that build would succeed.
> **An enabled scheduler pointing at an image that does not exist yet is a
> promise resting on a build nobody had run.**

The backup code itself was proven — 19 tables, 900 rows, 21 objects verified —
but proven **on a developer's disk, where `migrations/` is simply present**.
The image was never built. It was a path nobody ran.

**Two rules follow, and they are cheap:**

1. **A change to the `Dockerfile` or `.dockerignore` is not verified until an
   image has been BUILT.** Reading either file proves nothing; they interact,
   and the interaction is where this failed.
2. **Do not enable a schedule that points at an artefact that does not exist
   yet.** Either build the artefact first, or leave the schedule disabled and
   enable it once something real is behind it. "It will heal itself" is a
   forecast, not a verification.

### 3.6 The lifecycle rule, corrected

Rewrite `gcs_lifecycle_backups.json` and apply it: match the prefix the script
actually writes, keep nightly backups 30 days, and keep one backup a month for
a year rather than deleting everything at 30 days. **Show him the rule in plain
English before applying it**, because a lifecycle rule deletes his only copy if
it is wrong, and this one has been wrong since it was written.

### 3.7 The SIGABRT

Find it in the logs for revision 00068 around 14:52 IST on 2026-09-10. Report
what it was. Fix it only if the cause is obvious and small; otherwise write it
up and leave it.

---

## 4. What is NOT in this build

- The static IP. That belongs to horizon 3 and buys nothing today.
- Moving the business apps out of the shared Supabase project. His own session.
- BigQuery billing export. Unused, and it costs nothing to leave alone.
- Any change to the live service's memory, CPU, concurrency or scaling.
- Anything touching his trade record, the vault, or the AI.

---

## 5. How it is verified

**By invoking, never by reading a status.**

| Claim | The proof required |
|---|---|
| Documents merges no longer deploy | One documents-only push that produced no build, and one code push that did, both named with their build ids |
| The image store is cleared | The repository size before and after, from the same command, and the count of remaining images |
| The dead services are gone | The service list showing one `swayam-dashboard`, plus the live site answering before and after |
| The backup runs | A new object in the bucket with tonight's date, and its table count |
| The age shows on Home | A screenshot of the real figure in both themes |
| The lifecycle is right | The rule read back from the bucket, restated in plain English |

Python and JavaScript suites both run, counts compared with
`SWAYAM_START_HERE.md`. **His journal folder holds one note and a Terminal
tests subfolder: check before and after every run.**

---

## 6. The handoff

Five parts. In the header, in bold: **what this saved a month, measured, and
what it did not touch.** A table of every destructive command that was run,
with its region. And the one bold line saying what exists and what does not.
