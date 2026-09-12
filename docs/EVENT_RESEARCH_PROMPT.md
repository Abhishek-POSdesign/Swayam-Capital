# THE EVENT RESEARCH PROMPT, two passes

> Written 2026-09-12 late night by the AI partner chat, the mentor, from his
> instruction of the same night: "I will not have any of my personal list of
> the event, at least not for the first year, or never. It will always be
> market-driven: what the market fears or enjoys, which events impact VIX, the
> volatility index. That has to go through research, and that has to be listed
> as high-impact. Others are not less impacted."
>
> This is `docs/PLAN.md` §2.17.14, THE DESK. It exists so the partner's
> day-before warning needs no fresh judgement: the list is researched once,
> stored in the terminal in advance, and read.
>
> **His rule: research is done TWICE, by two tools, before anything is built.**
> Pass one is Antigravity, which has Google grounding. Pass two is Perplexity,
> run independently — do not show it Antigravity's answer. The mentor
> reconciles the two into `PLAN.md`, exactly as was done for the Library.
>
> Both passes get the SAME brief. Only the wrapper differs.
>
> Paste copy for pass one lives in his vault at
> `00 - Developer Logs/ANTIGRAVITY_PROMPT - Event Research.md`.

---

## PASS ONE — paste this into Antigravity

```
You are doing DEEP RESEARCH for one person, Abhishek Sikka, who trades NIFTY
index options and is building a trading terminal with an AI partner inside it.
This task is research and a written list. You change nothing in his terminal
and you write exactly ONE file at the end. Read the whole brief before you
search.

=== WHY THIS RESEARCH EXISTS ===

He has one rule about events, in his own words:

  "We will not keep any position open on the day the event is happening.
  Either we will close the position one day before the high-impact event,
  like RBI, US Fed, or anything which has a very high impact on the market,
  or budget, or I am available on the system, on the computer, to manage
  manually. If I am not available, I will square off the trade one day
  before and enter into the new trade after it, after a discussion about
  what is really there in the data, in the announcement, in the event, and
  how we can create a strategy around it."

For his terminal to warn him the day before, it has to already know which
events count. That list must be in the terminal in advance. This research
produces the evidence for that list.

=== THE RULE THAT SHAPES YOUR ANSWER, and it is not the usual one ===

He was explicit that the list is NOT his personal opinion and NOT a list of
famous events:

  "It will always be market-driven: what the market fears or enjoys, which
  events impact VIX, the volatility index. That has to go through research,
  and that has to be listed as high-impact. Others are not less impacted."

Three consequences, and you are judged on all three:

1. An event earns a place ONLY on MEASURED MOVEMENT in NIFTY or India VIX,
   documented in a source you name. Fame is not evidence. "Everyone knows the
   Budget moves the market" is not evidence. A study, an exchange publication,
   or a dated table of actual moves is evidence.
2. You NEVER write "low impact" about anything. The two classes you may use
   are HIGH IMPACT (MEASURED) and NOT ESTABLISHED AS HIGH IMPACT. The second
   means the evidence was not found, not that the event is unimportant.
3. If you cannot find a measured magnitude for an event, you write
   "unavailable" and say exactly what you searched. You do not estimate, you
   do not round a remembered figure, and you do not carry a number from your
   own training. Every number in your file carries its source and the period
   it was measured over. This is his hardest rule and the one he checks.

=== WHO HE IS, so you judge relevance ===

NIFTY index options, multi-leg structures: iron condors, bull call spreads,
bear put spreads, calendars. Swing and positional, held days to weeks, rarely
intraday. Part-time on a night shift: at the screen about 2 pm IST, trading
roughly 1 to 2:30 pm, sixty to ninety minutes a day. So an event that prints
after 15:30 IST does not hit the session he is watching — it hits the NEXT
morning's open, which is exactly the overnight risk his rule is about. Getting
the TIME right therefore matters as much as getting the event right.

His data window is 2022 onward, because he considers the market before and
after Covid to be different markets. Prefer evidence from 2022 onward. Older
evidence may be included if it is the best that exists, clearly marked with
its period.

=== THE JOB ===

Establish, from evidence, which recurring event TYPES and which kinds of
unscheduled shock have actually moved NIFTY and India VIX.

Cover at least these candidates, and ADD any the evidence supports that are
not listed. Do not treat this list as the answer; it is a starting point and
several items on it may turn out to be NOT ESTABLISHED.

  India, scheduled: RBI monetary policy decision; the Union Budget and any
  interim budget; India CPI; India WPI; India GDP; India IIP; India PMI;
  general election results day; state election results; RBI MPC minutes;
  monthly and weekly NIFTY expiry itself; quarterly earnings season for the
  index heavyweights.

  Global, scheduled: US Federal Reserve FOMC decision; the FOMC minutes and
  Jackson Hole; US CPI; US non-farm payrolls; US GDP; US PCE; ECB decision;
  Bank of Japan decision; China GDP and PMI; OPEC decisions; MSCI index
  rebalances; US tariff announcement dates where scheduled.

  Unscheduled: war or border escalation involving India; a broader
  geopolitical or war shock elsewhere; a major tariff or sanctions
  announcement; a bank, NBFC or broker failure in India or abroad; a surprise
  RBI action between meetings; a SEBI or exchange circular that changes F&O
  rules, margins, lot sizes or expiry days; a large single-stock accounting
  or fraud event in an index heavyweight; a global risk-off shock with no
  Indian cause.

=== WHAT YOU WRITE FOR EACH EVENT TYPE, all twelve fields ===

 1. Event name, and the body that publishes it.
 2. SCHEDULED or UNSCHEDULED.
 3. Frequency, and the URL of the OFFICIAL calendar where its next date can be
    looked up. Prefer a page that is stable and machine-readable. Say if none
    exists.
 4. Release time in IST, and where you read that time. If the source time is
    in another timezone, name that timezone, give the source time, and state
    whether it shifts with daylight saving. An IST time you derived yourself
    must say so.
 5. Where it lands against NSE hours (09:15 to 15:30 IST): INSIDE SESSION,
    AFTER CLOSE SAME DAY, or BEFORE OPEN / OVERNIGHT. For anything not inside
    the session, say which trading session actually absorbs it.
 6. Measured effect on NIFTY. What is documented: average absolute move on the
    event day, gap size at the next open, event-day range against a normal
    day, whichever the source gives. Name the source, the sample period and
    the number of observations.
 7. Measured effect on India VIX. The run-up before and the crush after, if
    documented. Same sourcing standard. (NSE publishes an India VIX white
    paper; he already holds it.)
 8. IMPACT CLASS: HIGH IMPACT (MEASURED) or NOT ESTABLISHED AS HIGH IMPACT.
    One sentence saying which measurement decided it.
 9. EVIDENCE QUALITY: academic study / exchange or regulator publication /
    broker or asset-manager research / news reporting. Give the publication
    date. Broker research is allowed and must be labelled.
10. For UNSCHEDULED types only: at least two DATED real instances since 2022,
    each with the actual NIFTY move and India VIX move on the day, sourced.
    If you can find only one, say so. If none, say so.
11. LEAD WARNING: how many days in advance the date is knowable. Some are
    known months ahead; some are announced days ahead; unscheduled ones are
    knowable only as a state of the world.
12. WHAT IS UNKNOWN about this event, in one or two lines.

=== SOURCES TO PREFER, in this order ===

NSE (nseindia.com, nsearchives, NSE Market Pulse), NSE Clearing, SEBI, RBI,
MoSPI, the Income Tax Department for anything on charges; for US events the
BLS, BEA and the Federal Reserve's own release calendars; peer-reviewed or
working-paper event studies on Indian index behaviour and on India VIX;
then reputable broker and asset-manager research, labelled as such. Avoid
promotional trading sites entirely. If an NSE page refuses an automated
reader, say "needs his browser" and give the URL rather than substituting a
third-party mirror.

=== WHAT YOU MUST NOT DO ===

- Do not download or attach files. This is research and a list.
- Do not write anything into his trading project folders.
- Do not recommend a trade, a strategy or a position size anywhere.
- Do not call anything low impact.
- Do not state a number without its source and period.
- Do not present a well-known belief as a measurement.

=== THE ONE FILE YOU WRITE ===

Path: G:\My Drive\Second Brain\00 - Developer Logs\EVENT_RESEARCH_<today's
date as YYYY-MM-DD> by Antigravity.md

Shape:
  - A header: what you were asked, the date, the model you used, and the
    number of grounded searches and pages fetched. He tracks AI cost as a
    trading expense, so this count is not optional.
  - A summary table: event, scheduled or unscheduled, IST time, where it
    lands against NSE hours, impact class.
  - Then one section per event type with the twelve fields.
  - Then a section "WHAT I COULD NOT ESTABLISH", listing every event where a
    magnitude was unavailable and what you searched for it.
  - Then a section "EVENTS I ADDED that were not in the brief", with why.
  - Then a section "SOURCES", every URL with what it gave you.

Write nothing else, anywhere.
```

---

## PASS TWO — paste this into Perplexity, WITHOUT showing it pass one

> Independence is the point. If Perplexity sees Antigravity's answer it will
> tend to agree with it, and the second pass stops being a second pass. He
> hands both files to the mentor, and the mentor reconciles.

```
Deep research task. Answer only from sources you can cite, and mark clearly
anything you cannot source.

CONTEXT. A part-time Indian retail trader runs multi-leg NIFTY index option
structures — iron condors, vertical spreads, calendars — held for days to
weeks. He has one rule: he will not hold a position through the day of a
high-impact event; he closes the day before, or he is at his screen to manage
it. He needs to know WHICH events those are, decided by evidence rather than
by reputation. His terminal will store the list in advance.

THE QUESTION. Which scheduled and unscheduled events have MEASURABLY moved
the NIFTY 50 index and the India VIX index, on evidence, from 2022 onward?

RULES FOR YOUR ANSWER, and they are strict:

1. An event qualifies only on measured movement in NIFTY or India VIX that
   you can cite. Reputation is not evidence.
2. Never use the phrase "low impact". Use HIGH IMPACT (MEASURED) or NOT
   ESTABLISHED AS HIGH IMPACT. The second means you could not find the
   evidence, not that the event is unimportant.
3. Every number carries its source, the period measured and the number of
   observations. If a magnitude cannot be sourced, write "unavailable" and
   say what you looked for. Do not estimate and do not use a remembered
   figure.
4. Times matter as much as events. NSE trades 09:15 to 15:30 IST. For each
   event give the release time in IST, say where that time came from, name
   the original timezone and whether it shifts with daylight saving, and say
   whether the print lands inside the session, after the close, or overnight
   before the next open.

COVER at least: RBI monetary policy; the Union Budget; India CPI, WPI, GDP,
IIP and PMI; general and state election results; NIFTY weekly and monthly
expiry itself; index-heavyweight earnings season; US FOMC decisions, minutes
and Jackson Hole; US CPI, non-farm payrolls, GDP and PCE; ECB and Bank of
Japan decisions; China GDP and PMI; OPEC decisions; MSCI rebalances; and as
unscheduled shocks — India border or war escalation, wider geopolitical war
shocks, tariff and sanctions announcements, bank or broker failures in India
and abroad, surprise inter-meeting RBI action, SEBI or exchange circulars
changing F&O rules, margins, lot sizes or expiry days, accounting or fraud
events in an index heavyweight, and global risk-off shocks with no Indian
cause. ADD any event type the evidence supports that is not on this list, and
say you added it.

FOR EACH, give: the publishing body; scheduled or unscheduled; frequency and
the official calendar URL; the IST time and its provenance; where it lands
against NSE hours; the measured NIFTY effect with source and period; the
measured India VIX effect with source and period, including any documented
run-up before and crush after; the impact class with the one measurement that
decided it; the quality and date of your evidence; and how many days ahead
the date is knowable.

FOR UNSCHEDULED TYPES, give at least two dated real instances since 2022 with
the actual NIFTY and India VIX move on the day, each sourced.

PREFER: NSE and NSE Market Pulse, SEBI, RBI, MoSPI, and for US events the
BLS, BEA and Federal Reserve release calendars; then peer-reviewed or
working-paper event studies on Indian index behaviour and on India VIX; then
labelled broker and asset-manager research. Exclude promotional trading
sites.

END WITH: a section listing every event where the magnitude was unavailable
and what you searched; a section listing events you added and why; and a full
source list with what each source gave you.
```

---

## WHAT THE MENTOR DOES WITH THE TWO FILES

Reconciles them into `docs/PLAN.md` §2.17.14 the same way the Library's two
passes were reconciled: what the second pass corrected in the first, kept so
it is not re-learned; then one agreed list with an impact class and an IST
time per event type. That list is what the build stores in the terminal.

**What the build then needs, and it is not in scope tonight.** A table of
event TYPES carrying the researched impact class, the IST release time and
the official calendar URL; `swayam_macro_events.event_time` filled, because
it is empty on every row today (§2.17.11); the weekly Gemini curation
constrained to the researched list instead of choosing three to five events
itself; and the desk and the partner reading the same table. It builds when
he says.
