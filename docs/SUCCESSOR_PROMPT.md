# THE PROMPT TO PASTE INTO A NEW CHAT

> Written 2026-09-08 late evening, by the session that finished rounds 2 and 3,
> for whoever picks this up next. Written at his explicit request, so he never
> has to spend an hour explaining the same things again.
>
> **Copy everything inside the fence and paste it as the first message.**
> Nothing else needs to be said.

---

```
Swayam Capital. My NIFTY options paper-trading terminal, and the instrument I
intend to restart trading real money through. Read before you act. There is no
hurry and I would rather you take twenty minutes reading than give me a fast
answer built on a guess.

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

Only one session may write to the working folder at a time. I sometimes run a
second session for UI work. If both of you need to write at once, one of you
takes a separate clone. Ask me which.

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
  caged by tests/db_guard.py. Do not weaken or remove that guard.

READ THESE, IN THIS ORDER, ALL THE WAY THROUGH
Do not skim them and do not stop after the first. Between them they answer every
question you are about to ask me, and re-asking me is the thing I am most tired
of.
1. docs/SWAYAM_START_HERE.md   — where everything is, what is verified true, and
                                 what is not done. Section 3 is the live status.
2. docs/PLAN.md                — THE ONE PLAN. Section 0 is my hours. Section 1
                                 is the live market test, which is the gate, and
                                 it is already sized for my 90 minutes.
3. CLAUDE.md                   — how to work in this repository.
Only if you need them: docs/CALENDAR_BUILD_BRIEF.md for the calendar work when I
say so, docs/UI_BUILD_BRIEF_ROUND_3.md for what was just built, and
02 - Projects/Trading/MY TRADING RULES - ONE PAGE.md in my vault, which overrides
every document including this prompt.

DO NOT re-audit the codebase, do not write a new plan document, and do not
propose an architecture. All of that is done and written down. Update
docs/PLAN.md as work lands; every superseded plan was deleted for exactly this
reason.

WHERE THINGS STAND
Rounds 2 and 3 are merged, deployed and verified by image digest. The live
revision is swayam-dashboard-00045-lg2. The desk no longer exhausts the FYERS
request budget, there is a data-health strip on both pages that tells me whether
my prices are real, and the recorder is finally deployed. Nothing is waiting on
a merge.

WHAT I WANT NEXT
1. THE LIVE MARKET TEST. This is the gate to paper trading and it has never been
   run. docs/PLAN.md section 1 has the script: four things I do at the desk and
   six you read from the logs afterwards. Ask me to run my four when I am at the
   screen, around 2 pm. Nothing from rounds 2 and 3 has been seen with a live
   market, and nothing at all has been seen with a real open position, because I
   have never had one.
2. Then the Trade Journal's four faults. docs/PLAN.md section 2.2. From my first
   paper trade that page holds my record, so it is the last thing on the
   critical path.
3. Then backups, charges at execution, and a kill switch.
4. Calendars are briefed and ready but they are my decision, and it depends on
   what volatility is doing and whether an event is coming. Do not push me.
5. The AI chapter comes after the plumbing. I want it in the plan, not started.

My deadline is Friday 11 September for everything to be right. I am not fixing
the date I start paper trading; it starts when the live test passes.

Ask me when you are unsure. I have said so explicitly and mid-build is fine.
```

---

## NOTES FOR THE SESSION THAT READS THIS, not for him

Things learned by talking to him that are not obvious from the code, and that he
should not have to say again.

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
the tool and the trader, and he knows it.

**On the deeper why.** He built a Second Brain in Obsidian, fed his daily life
into it through his Atlas app, then injected four years of his own trading
history. He stopped trading for months. This terminal is how he restarts, with
his own money. That is why a fabricated number is not a cosmetic bug: it damages
the thing the Second Brain was built to be. Treat existing work as expensive and
hard-won, and read before you rewrite.
