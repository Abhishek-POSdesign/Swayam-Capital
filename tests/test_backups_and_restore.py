"""Backup and restore tests.

⚠️ THIS FILE IS DELIBERATELY ALMOST EMPTY, AND THAT IS A FINDING, NOT AN
OVERSIGHT. Read this before adding anything to it.

WHAT USED TO BE HERE, AND WHY IT WENT
-------------------------------------
Five tests, all of them covering two modules deleted on 2026-09-12:

- `swayam/services/backup_service.py` — recorded a table it could not read as
  an EMPTY table and still reported success. A Supabase hiccup on
  `swayam_positions` would have produced a "successful" backup containing no
  positions. Its only callers were three Cloud Functions that had never been
  deployed, deleted the same day.
- `scripts/restore_from_backup.py` — worse than dead. It counted INSERT lines,
  checked connectivity and returned success. **It never restored anything.**
  A recovery path that reports success without recovering would have told him
  he was fine in the worst hour he ever had. It also only read `.sql.gz`,
  which nothing writes any more.

Their tests passed. That is the whole problem: green tests standing over a
module that lies are worse than no tests, because they buy the lie credibility.

WHAT IS ACTUALLY LIVE NOW
-------------------------
- `swayam/services/record_backup.py` — the real backup. A table it cannot read
  FAILS the job; an upload it cannot verify FAILS the job. Runs nightly as the
  Cloud Run job `swayam-nightly-backup`.
- `scripts/restore_drill.py` — the real proof of recovery. Rebuilds the schema
  into an isolated `swayam_restore_drill` schema, reloads every row, and
  compares what landed against the manifest, row count and content.

⚠️ THE GAP THIS FILE NOW NAMES
------------------------------
**`scripts/restore_drill.py` HAS NO AUTOMATED TEST ANYWHERE IN THIS REPOSITORY.**
Confirmed by search on 2026-09-12: nothing under `tests/` references it.

The script that proves his record can be recovered is itself unproven by the
suite. It has been run by hand and passed, which is more than the deleted code
ever managed, but a hand-run drill is not a regression test.

This file is kept, rather than deleted, so that gap has somewhere to live and
is not discovered again from scratch. **Anyone adding backup coverage should
start here, and should cover `restore_drill.py` first.**

Testing the drill properly needs a live database, because rebuilding a schema
and reloading rows is the entire point and mocking it would test nothing. That
is why it does not already exist, and it is the reason to be deliberate about
it rather than quick.
"""
