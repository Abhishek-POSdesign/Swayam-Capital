# THE PROMPT TO PASTE INTO A NEW CHAT

> Rewritten 2026-09-09 evening, by the session that watched him take his first
> three real paper trades. Written at his explicit request, so he never has to
> spend an hour explaining the same things again.
>
> **Copy everything inside the fence and paste it as the first message.**
> Nothing else needs to be said.

---

```
Swayam Capital. My NIFTY options paper-trading terminal, and the instrument I
intend to restart trading real money through. Read before you act. There is no
hurry and I would rather you take twenty minutes reading than give me a fast
answer built on a guess.

THIS IS THE MAIN CHAT: the terminal itself, the desk, the ticket, positions,
the journal, the recorder, live testing. I KEEP ONE CHAT PER PURPOSE. If we
drift into the backtester or into designing the AI partner, stop me and say so.
docs/CHAT_PROMPTS.md lists every chat and the prompt that belongs to it.

TWO THINGS I CORRECTED ON 2026-09-10 NIGHT, so no session repeats an old plan.
My own past trades are NOT backtesting material; they were not structured well
enough, and my history is for reflection and knowledge only. And any data work
starts from 2022, not 2018, because the market before and after Corona are
different markets. docs/PLAN.md 2.16.0 and 2.16.2.

MY OWN TRADING ARCHIVE, which nobody had written down before, is at
E:\Project E\Trading\Bazaar. Everything I ever saved, including the swing
journal spreadsheet and four strategies I wrote with rules. My own word for it
is broken: some current, some years old, some spreadsheets lost.

WHO I AM AND HOW TO WORK WITH ME
I am Abhishek. I am not a developer. Write plain English, never hand me code to
approve, and when something is a judgement call give me your recommendation
rather than a menu. English, not Hinglish. I speak my prompts, so an odd word is
transcription and not intent. I mostly take swing and positional trades.

MY HOURS. GET THIS RIGHT OR YOUR PLAN IS USELESS.
I work a night shift. I wake around 1 pm IST and I am at the screen by about
2 pm. I trade between 1 and 2:30 pm. My live-market window is 60 to 90 minutes,
once a day. Never plan anything for 09:15. Never write "tomorrow morning" to me.
Anything that needs my hands has to fit in that window in priority order, and
anything you can read from logs afterwards must not use up any of it.

MY TWO RULES. I will not repeat them.
1. No fake data. Every number on my screen is real from FYERS or the database,
   or it says unavailable and gives the reason. Never a placeholder shown as
   real, never a fallback constant. This has been broken repeatedly and it is
   what I care about most.
2. Never tell me something is done, live or passing unless you checked it on the
   running system that day and can show me the proof. An honest gap is welcome.
   An overstatement is not. I have burned days and real money on false status.

HOW WE WORK
Plan before you build: plain English, six parts, in the chat, and I approve it
before any code. Hand off after you build: five parts, files as clickable links,
any manual step flagged in bold up front. Never work on main. Feature branch,
pull request, I click Merge, because the pull request is my only revert button.
Merge one pull request, wait for the green tick, then merge the next.

Only one session may write to the working folder at a time. If two are needed at
once, one takes a separate clone. Ask me which.

WHERE EVERYTHING LIVES. Do not ask me any of this.
- Code: D:\Claude\POS\Trading-Platform\Swayam Capital
- Python: .\.venv\Scripts\python.exe  (editable install; work in the primary
  folder, NEVER a git worktree)
- GitHub: Abhishek-POSdesign/Swayam-Capital, gh is authenticated
- My vault, the Second Brain: G:\My Drive\Second Brain
  An Obsidian vault in Google Drive. It holds my daily life through my Atlas app
  and four years of my own trading history. IMPORTANT: D:\Second Brain is an
  EMPTY, STALE folder from when I first installed Obsidian. Never read it, never
  write to it.
- Database: Supabase wxijlrwoiaeaupaaqecc, ap-south-1, shared with two other
  apps, so scope everything to swayam_*
- Cloud: GCP swayam-capital. Live site is Cloud Run swayam-dashboard in
  asia-southeast1, mapped to swayam.abhisheksikka.com, behind Google sign-in.
- There is NO staging database. Everything runs against live. The test suite is
  caged by tests/db_guard.py for the database and by conftest.cage_the_vault for
  my vault. Do not weaken or remove either guard.

READ THESE, IN THIS ORDER, ALL THE WAY THROUGH
0. docs/ROADMAP.md             — PLAN STARTS HERE. My end goal and the four
                                 horizons with their gates, in my words. Edit
                                 it only with my explicit approval.
1. docs/SWAYAM_START_HERE.md   — where everything is, what is verified true, and
                                 what is not done. Section 3 is the live status.
2. docs/PLAN.md                — THE ONE PLAN. Section 0 is my hours. Section
                                 2.12 is your job. Section 2.12.0 is the audit
                                 of my first three real trades.
3. CLAUDE.md                   — how to work here, and what I actually trade.
4. G:\My Drive\Second Brain\00 - Developer Logs\SESSION_LOG_2026-09-09.md
                               — what the last two sessions found and fixed, and
                                 why the code looks the way it does.

DO NOT re-audit the codebase, do not write a new plan document, and do not
propose an architecture. All of that is done and written down. Update
docs/PLAN.md as work lands; every superseded plan was deleted for exactly this
reason.

WHERE THINGS STAND, 9 September 2026, night
I have taken three real paper trades. The live market test is PASSED and is no
longer the gate. Everything is merged and deployed; the repository has one
branch, main, and no open pull requests. On the evening of 9 September the
execution ticket (PR #49), a retry fix (#50), the Home strip move (#51) and
realistic fills at the bid and ask (#52) were built, merged and deployed. The
first send through the ticket with a live market has NOT happened yet; it is
scheduled for my window on 10 September, docs/PLAN.md 2.12.4. Read the vault
session log 00 - Developer Logs/SESSION_LOG_2026-09-09_evening.md too.

REAL-MONEY ORDERS. I asked, it was researched, the answer is in docs/PLAN.md
2.14. For now orders go through the FYERS terminal and everything else lives
here. The next thing after the position area is the READ-ONLY bridge that
mirrors my real positions and fills from FYERS into this terminal. Sending
real orders from this app is a later, separate plan. Do not start it.

All three of my trades made a GROSS PROFIT and all three LOST MONEY. Gross +195,
charges 585, net -390. Charges were 300% of gross. That is my last financial
year in miniature and it is the most useful thing this terminal has ever shown
me. Do not let anyone weaken the charge engine.

What those trades exposed is now the whole next job. My words: immature
execution, immature exit, immature monitoring. Taking a position is more immature
than buying a soda bottle.

WHAT I WANT YOU TO BUILD. docs/PLAN.md section 2.12. In this order.
(Items 1, 2 and 4 were built on 9 September as PRs #49 to #52. If PR #52 is
merged, start at item 3 and read what 2.12.2 records for PRs 1 and 2 first.
If it is not, ask me.)
1. The execution ticket. I press Execute and I see what is about to be sent
   before it goes: every leg, market or limit with a switch, an editable price
   with a proper reset button, editable lots, the margin needed, my four rules,
   control over which leg goes first, and a choice of sending all legs together
   or one at a time. No bid-ask ladder. No market depth.
2. Realistic fills. I buy at the ask and sell at the bid, and a limit fills at
   my price or better, as on Kite or FYERS. My results will look worse and be
   truer. My trades from before this were filled at the traded price and are
   marked as not comparable.
3. The position area on the Strategy Desk, full width, BELOW the payoff graph.
   Open now, closed today, earlier. Big bold numbers, colour from the money.
   Exit one leg, reverse one leg, add a leg, exit everything. A real dustbin and
   a real reset button. I must feel good while managing it.
4. Home shows, Home does not manage. Move the open-positions strip below my
   daily check-in and above Your money, make it refresh without a reload, and
   take the Exit button off it.
5. The option chain already adds legs and has never been used with a live
   market. Test it and fix what it gets wrong rather than rebuilding it.

MY DECISIONS ARE RECORDED IN 2.12.1 WORD FOR WORD. Do not relitigate them.
Three more were taken on 9 September evening and are recorded there too: every
exit, one leg or all, goes through the same ticket with market or limit per
leg; one by one is a real add-a-leg on the same trade; the single-leg rule is
gone. The journey I approved is a clickable prototype linked from 2.12.1.

THE OPEN DECISION I HAVE MADE, section 2.13. The live site cannot see my vault,
so my daily check-in returns an error there and the AI reads a frozen copy of my
Method files. The Drive API is enabled and the libraries are installed; the only
blocker is Google's consent screen and I cannot date it. Build the bridge that
does not wait for Google: mirror the few files the app needs into the database.

AFTER THAT, in order: the read-only broker bridge (2.14), the recorder's
twelve zero columns (2.10), scheduled backups (2.6), the kill switch (2.5),
then calendars (section 3) when I say so, then the AI chapter.

THINGS THAT WILL BITE YOU, ALL LEARNED THE HARD WAY
- A path nobody has ever run has never been tested, whatever the tests say.
  Three audits and a green suite all missed that closing a trade was impossible,
  because nobody had ever closed one.
- Check that the columns you write actually exist. tests/test_written_columns_exist.py
  does this; keep it passing.
- A note is not a trade, at both ends. A vault write that can fail goes to the
  outbox and my action still succeeds.
- Fix a rule where the rule lives, not where the symptom showed.
- node --check is not verification. Load the real page in a real browser, in
  both themes.
- git fetch and check whether the branch's pull request is already merged before
  pushing more work. I merge mid-session to review.

Ask me when you are unsure. I have said so explicitly and mid-build is fine.
```

---

## NOTES FOR THE SESSION THAT READS THIS, not for him

Things learned by talking to him that are not obvious from the code, and that he
should not have to say again.

**On what he saw the day he first traded, 2026-09-09.** He took three paper
trades and every one exposed something. Read `docs/PLAN.md` §2.12.0 before
touching the desk, because it lists what those trades did on the backend that he
could not see. The short version: all three made a gross profit and all three
lost money to charges, his daily check-in returns 500 on the live site, rule 4
can never be tested because margin used is never stored, and the spot at entry
is never saved.

**On how he judges a screen.** He does not say "there is a bug". He says
"immature", "cheap", "I must feel good while managing it". Those are real
requirements to him, not decoration. A cross where a dustbin belongs and a small
round icon where a button belongs are both things he has named. Build controls
that look like controls.

**On what stopped him trading, twice in one afternoon.** The execution key was
minted once per browser and never released, so his first trade worked and every
later one was refused. He could not tell that from the screen and had no way out.
When something refuses him, the message must say what he can DO, not only what
went wrong.

**On the charge engine, and why it must not be weakened.** It is the only
correct money maths in the repository: per leg, per side, versioned by date, in
exact decimals. It showed him in one afternoon what took a year and ₹86,299 to
learn last time. If a future change makes charges an estimate again, it has
undone the most valuable thing the terminal does.

**On the vault, twice bitten.** Tests wrote 26 fabricated trades into his real
journal folder on 2026-09-08. The live site wrote a real trade note into a
container folder and reported success on 2026-09-09. Both are now caged and both
cages have tests. Never remove either, and never let a vault write "succeed"
into somewhere that is not his vault.

**On asking him.** He answers fast and precisely when the question is real and
the options are concrete. He gets impatient with plans, explanations and
re-litigation. When he says "fix it", he means stop writing and start typing.

**On his hours.** He has corrected the morning assumption at least twice. Two
separate plans were written for a 09:15 start before it landed. The recorder is
the one thing that genuinely runs at 09:15, and that is fine precisely because it
needs nobody awake.

**On how he reviews.** He reads the running app, not the diff. He merges to
review, which is why commits pushed after a merge strand. He spots real faults
from screenshots: he found the duplicated margin ceiling, the washed-out
explanation text, the green chat bubble and the dead panel on Home, all by
looking. Take his visual observations seriously; twice they led to backend bugs
nobody had found.

**On "Today's limits".** He questioned whether it belonged on Home. The answer
settled on: the four caps stay on Home as one band inside "Your money", because
seeing them before he starts is the discipline the terminal exists for, but the
full treatment with explanations belongs on the desk where the decision is made.
Do not move it again without asking.

**On the running-loss label.** He asked why a trade he had not taken showed a
"running loss". Rule 1 is a forecast of a two-sigma day including costs, not
money already gone. His own vault names the rule "Running loss, 1% exit, no
debate", which is about exiting a live position, so the desk is reusing one name
for two jobs. Do not rename his rule. The desk's wording could be clearer.

**On the swastika and the mark.** The mark is `स्व` in sage green beside the word
Swayam. Never raise Western or Nazi associations. He has litigated it and it is
closed.

**On purple.** No purple, lilac or violet anywhere. He has complained many
times. The accent is sage.

**On cost.** AI-heavy features are always a manual button, a 60-minute cache and
a daily cap. Never on page load. Unguarded this was estimated at ₹4,000 a month.

**On what he actually trades.** Ten of his twenty-one historical trades are
calendars, and he says he uses them more than half the time and that they were
profitable. The terminal cannot execute them. That is the largest gap between
the tool and the trader, and he knows it. **His own framing of a calendar,
2026-09-08: the far expiry is the hedge and the margin benefit, the near expiry
is where the theta is earned.** He squares off before the near expiry — Monday
before the close for a Tuesday expiry, or the Friday before if already well in
profit or already in a loss.

**On how a trade is shaped, which nobody had asked him.** A trade is a campaign,
not a leg and not a fixed structure. It gets a number, legs are added and
squared off inside it while it lives, each squared-off leg adds its own result,
and it closes when every leg is closed or when he says so. His words: "In
options, you have to manage the trade... if you don't manage, you won't
survive." His historical sheet proves it — roughly a third of his trades carry
adjustments, and several were closed in pieces across different days. `CLAUDE.md`
has the full picture and the one conflict in his own documents that this
resolves.

**On the vault, and this is the one that cost him.** On 2026-09-08 his real trade
journal folder held 26 fabricated notes, 22 of which had no database row at all.
The database has been caged since that morning; the vault never was, and every
writer fell back to his live path. **He has taken no trade of his own since
31 March 2026**, which is how he told them apart, and he asked for them deleted.
The cage is now in `journal_writer._default_vault_base()` and
`conftest.cage_the_vault`. Never remove it, and check his journal folder is empty
before and after running the suite.

**On reading his vault rather than asking him.** Everything above came from
`G:\My Drive\Second Brain - Projects\Trading\`. His Method files, his 21
historical swing trades, his FY 2025-26 broker-verified record and his journey
note answer most questions a session will want to ask him. Read them first.

**On the deeper why.** He built a Second Brain in Obsidian, fed his daily life
into it through his Atlas app, then injected four years of his own trading
history. He stopped trading for months. This terminal is how he restarts, with
his own money. That is why a fabricated number is not a cosmetic bug: it damages
the thing the Second Brain was built to be. Treat existing work as expensive and
hard-won, and read before you rewrite.
