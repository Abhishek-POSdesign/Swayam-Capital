# CLAUDE.md — Swayam Capital (Claude Code's operating brief)

> This is Claude's counterpart to `GEMINI.md`. It auto-loads whenever Claude Code opens this repo. Its job: get me oriented and current in one read so I never re-derive context or relitigate settled decisions. **Keep it honest — update it at the end of any session that changes state, PR count, locked decisions, or file locations.**
>
> **Last updated:** 2026-09-06 (late) by Claude — after inspecting Antigravity's PR #10–#14 work.

---

## 0. First actions in any Swayam session (read in this order)

The **vault** (`G:\My Drive\Second Brain\02 - Projects\Trading\` + `00 - Developer Logs\`) is the source of truth for *thinking*; this repo is the *code*. Before touching code, read:

1. `G:\My Drive\Second Brain\00 - Developer Logs\SESSION_STATE_<latest>.md` — where things stand right now.
2. `G:\My Drive\Second Brain\02 - Projects\Trading\WHERE EVERYTHING LIVES.md` — the map (locations, repos, secrets, buckets, authority).
3. `06 - Platform Plan\Platform Overview.md`, `Home Page v2 Plan.md`, `AI Trading Partner Chapter.md` — design + AI + memory.
4. The Method files in `01 - Method\` before writing any trade-entry logic.

Abhishek is **non-technical**. Write to him in plain English, never hand him code to approve, give a recommendation not a menu. **Plan first in plain English (6-part), build, then hand off structured (5-part)** — per his global `CLAUDE.md` and the `/layman-plan` + `/handoff` skills.

---

## 1. What Swayam Capital is

Abhishek's own NIFTY F&O trading platform ("my terms, my rules"). A rule-enforcing terminal + journal + (future) backtester for **positional/swing** options trades — NOT a scanner, NOT a signal service, NOT autonomous. He is an **afternoon trader** (arrives desk 1–2 PM IST), ~1–2 swing trades/week. **Paper trading starts Monday 2026-09-08.** Real capital is rules-proven, not date-driven (post-Diwali earliest).

- **Live:** https://swayam.abhisheksikka.com (Cloud Run `asia-southeast1`, behind IAP, single user)
- **Stack:** Python 3.11 FastAPI backend (`src/`), Vite vanilla-ESM + Plotly frontend (`web/`), Supabase (`swayam_*` tables), Vertex AI Gemini (3.1 Pro Preview → 2.5 Pro → 2.5 Flash-Lite), FYERS API v3 (broker, Phase 2).

## 2. ⚠️ TWO SEPARATE GitHub repos — never confuse PR numbers

- **App code (this repo):** `Abhishek-POSdesign/Swayam-Capital` — PR-based workflow. **All PR numbers ("PR #13") refer ONLY to this repo.**
- **Second Brain vault:** `Abhishek-POSdesign/Obsidian-second-brain-` — a plain nightly **encrypted backup**, **zero pull requests**.

If a "PR #N" link opens the vault repo, it's the wrong repo. This mix-up cost real confusion on 2026-09-06. **Always give the full PR URL and name the repo** in any handoff.

## 3. Current state (verified 2026-09-06 late)

- `main` = `e6ec371`. **PRs #10, #11, #12, #13, #14 all merged.** #10 = Home Page v2 (BUILDs 11.6–11.12); #11 = typography/mobile/real macro; #12 = app icons/mobile polish; #13 = strategy mobile stacking, emerald chat, sector strip; #14 = docs refresh.
- **Tests:** 327 backend pytest (via `pytest --collect-only`) + ~102 frontend vitest. A "51 backend / 153 total" figure floating in some notes was a **partial slice**, not a regression. Full green-run not yet re-confirmed — see §7 (live-DB caution).
- **Gated on Abhishek's manual secrets** (none block Monday): Telegram token/chat-id, Firebase VAPID + FCM key, Trading Economics API key, Gmail app password + sender. Backup pipeline + macro ingest are code-shipped.
- **Next session:** **Strategy Builder page 2 redesign**, built directly by Claude Code (Antigravity's weekly budget spent ~4 days; refreshes ~2026-09-10). Then Trade Journal page 3.

## 4. Queued fixes (do on a branch → PR for his 1-click)

1. **Sector-rotation silent fallback** — `src/swayam/services/nifty_snapshot.py` shows hardcoded constants (BANK +0.42%, IT −0.65%, …) under a "PREVIOUS SESSION" badge when the market is closed. Fake data under a real-looking badge. Fetch genuine prior-session values or badge as explicit placeholder.
2. **`GEMINI.md` test scorecard** — fix the internal contradiction (says "258 backend" and "51 backend"); state the real 327. Update the vault mirror of GEMINI.md in the same pass.
3. **Add two rules to `GEMINI.md`:** (a) report the FULL test suite, never a partial as "all passing"; (b) never ship hardcoded market values behind a LIVE/CALCULATED/PREVIOUS SESSION badge.
4. **Design debts:** macro card text contrast (`web/src/components/macro-events-card.js`); purple side rail (`web/src/pages/strategy.js`, `web/src/styles.css`) — the side rail is absorbed into the Strategy Builder redesign.
5. **Park local `main`** back to origin (repo is often left on a feature branch after Antigravity sessions).

## 5. Locked decisions — do NOT relitigate

- **Afternoon-trader design:** hero is "So Far Today", not a morning brief. No 09:15 engagement assumptions.
- **Cost gate:** every AI-heavy feature is manual-button + 60-min cache + daily cap. **Never auto-fire on page load.** The only scheduled Gemini call is the *weekly* Sunday macro curation.
- **Freshness badges** (LIVE / CALCULATED / PREVIOUS SESSION / STALE) mandatory per data point. Never present static/fake data under a live-looking badge.
- **FII/DII:** cash and F&O always separate rows, never one "bias" number.
- **NIFTY weekly expiry = Tuesday** (SEBI change), read from FYERS contract master — never hardcode weekday.
- **AI persona hardcoded** (direct, evidence-first, no cheerleading); persona change only via a joint brainstorm, never unilateral.
- **Sanskrit स्वयं / स्वस्तिक branding** is decided — never raise Western/Nazi concerns.
- **Vault↔repo sync:** vault authoritative + repo mirror; weekly cron drift-alert (BUILD-11.14), NOT live bidirectional sync.
- **AI tuning:** one variable at a time, written hypothesis, human-approved. `learned_parameters` tunable; Method files are constitution (hand-edited only). No auto-apply, no autonomous execution — ever.

## 6. Rules that gate ANY trade-entry code (from `01 - Method/`)

- **1% realistic risk cap AND 3% blast-radius fuse** — both must pass (two-tier model).
- **1:2 R:R floor / 1:2.5 target.** No trade below 1:2.
- **No single-leg trades ever** — spread or hedged structure only.
- **One new entry per trading day.**
- **2% overnight-gap hedge cap** on any position held overnight.
- **Limit orders 99%; no stop-widening after entry; margin-safe (BUY legs before SELL); overnight-naked lockout after 15:20 IST.**
- Historical edge: directional-bearish + theta (Bear Put Spread specifically).
- Wake Alerts (BUILD-11.13) will attach per-trade criteria *from inside the Strategy Builder at trade open* — leave a home for it.

## 7. Verification discipline (non-negotiable)

- `node --check` is NOT sufficient — it has passed files the browser then rejected. Load real modules in a real browser before claiming something works.
- **The dev env points at the LIVE Supabase DB.** Do not run the full backend suite or click around signed-in unless you mean to write real data. Use a safe test config or collect-only when just counting.
- Never tell Abhishek something is done/pushed/live unless actually confirmed.
- **Never work directly on `main`** — feature branch + PR; he clicks Merge (that's his one-click Revert safety net). Delete only fully-merged branches you created.
- When Abhishek pastes an Antigravity "done" report: **inspect the real repo/DB/vault** (`/inspect-agy`), don't trust the summary. Grep for silent fallbacks; verify doc claims against real paths; check new tables against the vault sync scripts.

## 8. Update rule

If a session changes state, PR count, file/bucket/secret locations, locked decisions, or the queued list — update this file AND the vault `WHERE EVERYTHING LIVES.md` before closing. Keep the two honest and consistent.
