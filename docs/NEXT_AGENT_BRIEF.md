# NEXT-AGENT BRIEF — Swayam Capital (paste this to start a fresh chat)

You are picking up **Swayam Capital**, Abhishek's personal NIFTY options paper-trading terminal (FastAPI backend + vanilla-JS/Vite frontend + Supabase + FYERS broker API + Vertex AI). Read this whole brief before touching anything.

## READ THESE FIRST, IN ORDER (do not skip)
1. **`docs/Independent reports/SWAYAM_FINAL_MASTER_AUDIT_2026-09-07.md`** ← THE master audit + fix plan. Everything you need to fix is here (P0/P1/P2, data sources, plan). Vault mirror: `G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM_FINAL_MASTER_AUDIT_2026-09-07.md`.
2. The three source audits (repo `docs/Independent reports/`): `CODEX_INDEPENDENT_AUDIT_2026-09-07.md`, `SWAYAM_ROUND2_AUDIT_20260907_112114.md` (Hermes), and Claude's `SWAYAM_REALITY_VERDICT.md` / `SWAYAM_LIVE_DATA_REPORT_AND_PLAN.md` / `SWAYAM_DATA_AUDIT_AND_OBSERVATIONS.md` (vault `00 - Developer Logs/`).
3. `G:\My Drive\Second Brain\00 - Developer Logs\_CURRENT STATE - START HERE.md` (running state) and `02 - Projects/Trading/WHERE EVERYTHING LIVES.md` (map of code/DB/cloud — but treat its "LIVE" claims skeptically; several are wrong).
4. Claude's memory file `MEMORY.md` (auto-loads) — esp. `feedback_verify-data-source-before-certifying-real`.

## WHERE THINGS LIVE
- **App code:** `D:\Claude\POS\Trading-Platform\Swayam Capital\` (repo `Abhishek-POSdesign/Swayam-Capital`). Python `src/swayam/`, frontend `web/src/`, migrations `migrations/`.
- **Canonical vault:** `G:\My Drive\Second Brain` (NOT `D:\Second Brain`, which is an empty stale vault to be deleted). Planning/logs live in the vault.
- **DB:** Supabase project `wxijlrwoiaeaupaaqecc`, tables `swayam_*`. **Cloud:** GCP `swayam-capital`. **Broker:** FYERS API v3 (his account; token in `.env`, expires daily — regenerate near trading time via `.\.venv\Scripts\python.exe scripts\refresh_fyers_token.py`).
- **Run Python with the project venv:** `.\.venv\Scripts\python.exe` (NOT system/hermes python).

## WHY ABHISHEK IS FRUSTRATED (read carefully)
- He is **not a developer**. He spent **3 days and thousands of rupees in tokens** and still has a terminal he cannot trade on. Every session he opened, he found NEW fake/broken data after being told "it's fixed."
- His hard rule, stated many times: **NO FAKE DATA anywhere.** Every number must be real (from FYERS/DB) or say "unavailable/—". Never a hardcoded placeholder shown as real.
- He needs it **LIVE** (prices moving), not a 15-minute cached snapshot. He cannot trade off frozen data.

## PROBLEMS HE HIT (what "everything I touch is a bug" meant)
Frozen dashboard (loads once, 15-min cache, no polling); fake NIFTY spot 24,864 vs real ~23,776; fake VIX/FII-DII/breadth/morning-routine/rollover; a dead WebSocket; strikes far-OTM because spot fell back to a fake number; risk gate blocking valid trades (0.3% readiness throttle) with a 62%-should-be-0.62% display bug; his **capital not pulled from FYERS** (static ₹8.5L config); AI can't see the "So Far Today" summary he pays to generate; TTS pause restarts. Full list + priority in the master audit.

## MISTAKES CLAUDE (the previous agent) MADE — do NOT repeat
1. **Claimed things were "fixed / all real / behind IAP" without verifying against live data or the actual config.** The app is actually deployed `--allow-unauthenticated` with CORS `*` and no login — likely PUBLIC, not IAP. Verify posture; never assert it.
2. **Fixed reactively, only where he pointed** → every session surfaced more. Independent audits (Codex, Hermes) then found serious things Claude missed: readiness gate **fails OPEN**, backups **falsely report success**, **restore doesn't restore**, **no kill switch**, **float money math**, rollover still fake, expiry dates invented.
3. **Pushed commits to a PR that was already being merged** (didn't re-check PR state). Always `git fetch` + confirm the PR is OPEN before pushing; if merged, branch off `main`.
4. Audited *fake numbers* but under-audited **safety / security / reliability / DR**. Audit the whole surface.

## HOW TO WORK (the contract)
- **Verdict is: the app is FIXABLE, not garbage — do NOT rebuild.** Real FYERS data, options math, DB, rule engine, ~400 tests. Finish the wiring + fix the defects.
- **Fix in phases from the master audit: Phase A (safe & honest, P0) first.** Do NOT enable real-money trading (it's code-blocked; keep it so).
- **Plan in plain English and get his approval BEFORE writing code** (he is non-technical; never hand him code to approve). **Every finished build → structured handoff.** (His `/layman-plan` and `/handoff` skills enforce the shape.)
- **Verify every fix against live FYERS data and SHOW him the real number as proof** — never "I fixed it" alone.
- **Never work on `main`.** Feature branch + PR; he clicks Merge. Test (`npx vitest run` in `web/`, `pytest` in root) before claiming done.
- **Biggest unlock:** FYERS (his broker) gives — free — funds/capital, live positions+P&L, market depth, option chain, and streaming WebSockets. Most is unwired. Wiring FYERS properly makes it a live terminal without a rebuild.

Start by reading the master audit, confirm the P0 security/safety posture yourself, then propose the Phase-A plan in plain English and wait for his go.
