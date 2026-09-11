# BUILD 07 — THE AI PANEL, AND HOME WITHOUT A CHAT ON IT

> Written 2026-09-11 night by the main chat, from the brief the polish chat
> assembled from his own words and from his review of the mockup the same
> night. **He approved the mockup**, with five changes, all of which are in it
> now.
>
> **The mockup, and the build must be identical to it:**
> https://claude.ai/code/artifact/f3efa90c-c57d-4dba-bd00-924b3c04ee04
> It is not a picture. Open it, drag the panel, resize it from any edge, press
> the theme switch and look at Home.
>
> **This is a FRESH chat, and it runs AFTER BUILD_06 is merged**, so it inherits
> the corrected colours instead of being built twice.
>
> **The prompt he pastes is in the fence below.**

---

## 0. WHAT HE DECIDED, AND IT IS NOT UP FOR DISCUSSION

**How it opens.** [HIS WORDS] "I don't want to squeeze the window, or I don't
want to shift the window to the left or right. I want the AI panel to open
above the window without squeezing or shifting it." The page does not reflow.
The panel floats above it. **Narrowing the page was measured and offered to him
and he rejected it. Do not re-propose it.**

**Small every time.** His correction of 11 September: it opens at about four or
five lines. **Where it opens is remembered. How big it was, is not.** Position
is muscle memory; size depends on the minute.

**Resize from anywhere.** [HIS WORDS] "I want to be able to resize the window
half vertically, like I'm chatting with you like this, or half horizontally if
I want to." Eight handles, four edges and four corners. The ceiling is **half
the window across and half the window down**, and it stops there.

**Detach, move, attach, close.** [HIS WORDS] "If I need to, I can take the panel
out, detach it, and place it on the left side. I can shorten the size or make
it longer... Whenever I want, I can attach it back to its place or close it by
putting the closing button."

**No starter prompts.** His correction of 11 September: "I don't want these
presets. It is a noise taking space. Whatever I want to ask, I can ask
directly." None, in any state, including after Clear.

**Voice is the point.** [HIS WORDS] "just to keep my writing area and use mostly
TTS and STT to communicate." The composer stays small; the microphone is a
first-class control, not an afterthought.

**⚠️ THE EXIT TICKET IS ALWAYS ON TOP.** His instruction of 11 September: "my
exit ticket will always be on top. Orders are a priority, so nothing on top of
that." The panel may cover anything else. It may never cover the exit ticket or
the execution ticket. **This is a money rule, not a layout preference:** his
window is sixty to ninety minutes and the one moment covering something costs
him is the moment he is getting out.

---

## 1. HOME LOSES ITS CHAT AND GAINS "SO FAR TODAY"

**His decision, 11 September, and it is the big change in this build.** "On the
homepage, remove this on-page chat area. It is not required now because I'm
getting a floating chat that I can move and resize."

- **Delete the AI Trading Partner chat zone from Home**, `#home-ai` in
  `web/src/pages/home.js`, mounting `web/src/components/chat-surface.js`.
- **⚠️ DELETE NO CONVERSATION.** Removing the zone removes a surface, never a
  row. Everything he has ever said stays in History and the panel opens it.
- **The floating panel now behaves the same on Home as on every other page.**
  There is no longer a special case, which is simpler than the mockup's first
  draft and is his doing.

**In its place, one card: "So far today".** One **Generate** button, and the
summary stays where it is until he presses it again.

**⚠️ IT IS SAVED, AND THAT IS THE POINT.** [HIS WORDS] "I want to save the
AI-generated summary. I'm paying for that, so I don't want to lose those
details and create a record of what's happening, a trend in the market or in
the geopolitics as well."

So it is **a row a day in the database**, not browser storage:

- A new table, one row per trading day: the day, the text, when it was
  generated, and which model wrote it. Its own migration.
- **The panel reads it**, so he can open the panel on Home and ask about the
  day and it knows what the card says.
- Regenerating the same day **replaces that day's row** and keeps the newest
  stamp. It does not pile up copies of one day.
- Yesterday's rows stay for ever. Over months they become the record of what
  happened that he is asking for.

**⚠️ IT FALLS UNDER HIS AI COST RULE, which is not negotiable.** From
`CLAUDE.md`: AI-heavy features are always **a manual button, a 60-minute cache
and a daily cap. Never on page load.** Unguarded, this class of feature was
estimated at ₹4,000 a month. Pressing Generate twice inside an hour returns the
stored row and says so, rather than paying for it twice.

---

## 2. CLEAR AND DELETE

| | What it does | Asks first? |
|---|---|---|
| **Clear** | Empties the pane only. The conversation stays in History | No |
| **Delete** | Removes the open conversation from the database for good | **Yes** |

**Delete touches exactly these, read from the schema, not assumed:**

- `swayam_ai_conversations` — the row goes
- `swayam_ai_messages` — its messages go with it, `ON DELETE CASCADE`
- `swayam_ai_notebook` — **survives**, `source_message_id` set to NULL
- `swayam_ai_pinned_decisions` — **survives**, `source_message_id` set to NULL
- `swayam_ai_usage_daily` — untouched, it is a daily aggregate
- **Any image attached to the conversation, in storage, goes too.** His decision
  of 11 September. The existing endpoint `DELETE /api/ai/conversations/{id}`
  leaves them orphaned today. Fix that here, and say in the handoff that you
  did.

**Delete removes only the conversation he has open.** He said "that
conversation", singular. **There is no delete-everything button.**

---

## 3. What to build

1. **The panel itself**, floating, `position: fixed`, above the page and never
   reflowing it. The option chain's floating panel is the proven pattern in
   this codebase: dragged by its header, Escape closes. Resize, detach and
   attach are new on top of it.
2. **Opens small**, about four or five lines, every time.
3. **Position remembered** between sessions. Size is not.
4. **Eight resize handles**, clamped to half the window each way.
5. **Detach and attach**, one control.
6. **Shrink to the bar**, the tiny state, so it can stay up while he works.
7. **No starter prompts anywhere.**
8. **Clear and Delete** as section 2 says.
9. **Home**: the chat zone out, "So far today" in, with its table, its
   migration, its manual button, its hour cache and its daily cap.
10. **The panel reads the day's summary.**
11. **The exit ticket and the execution ticket sit above the panel**, always.
    Prove it by opening the exit ticket with the panel dragged over it.

---

## 4. What is NOT in this build

- The AI's persona, its routes, its model, its cost cap, its grounding. **"Touch
  nothing else of the AI."** This build changes where the conversation happens
  and nothing about what it says.
- The colours. **BUILD_06 lands first** and this build inherits them.
- The Trade Journal page, `PLAN.md` §2.18.
- Any change to trades, fills, charges, rules or the record.

---

## 5. How it is verified

**By invoking, in a real browser, against the real backend, in both themes.**

| Claim | Proof |
|---|---|
| The page never reflows | A screenshot of the desk with the panel open and closed, and the column widths measured identical |
| It opens small and in the same place | Reload and it returns to where it was, at the small size |
| It resizes from all eight | Each handle exercised, and the half-window ceiling hit and held |
| The exit ticket is on top | The panel dragged over it, then the exit ticket opened |
| Home has no chat and no conversation was lost | The zone gone, and the count of rows in `swayam_ai_conversations` identical before and after |
| The summary is saved | The row read back from the database, and the page reopened showing the same text |
| The cost rule holds | Generate pressed twice inside an hour, and the log showing one model call |
| Delete | A test conversation created, deleted, and every table in section 2 checked |
| Nothing else moved | Both suites at the counts in `SWAYAM_START_HERE.md` |

**His journal folder holds one note and a Terminal tests subfolder. Check before
and after every run. The open condor `7cd4d017` is untouched.**

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds exactly ONE thing: Build 07, the floating AI panel, and Home losing its
on-page chat in favour of a saved daily summary. The main chat planned it,
drew the mockup and will review it. You do not re-plan it or widen it.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER.
1. docs/builds/README.md              how a build works and the rules
2. docs/builds/BUILD_07_AI_PANEL.md   THIS BUILD, the whole spec
3. docs/PLAN.md 2.20, and 2.12.10 for where everything stands
4. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
5. THE MOCKUP, which is interactive and which I approved:
   https://claude.ai/code/artifact/f3efa90c-c57d-4dba-bd00-924b3c04ee04
   Open it. Drag the panel. Resize it from every edge. Press the theme
   switch. Look at Home. THE BUILD MUST BE IDENTICAL TO IT.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: awake around 1 pm IST, at the screen by 2 pm,
I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data, ever, or unavailable with the reason. Never say
done, live or passing unless you checked it on the running system that day and
can show me the proof.

THE THREE THINGS I WILL BE ANGRY ABOUT IF THEY GO WRONG.
- The panel must NEVER cover my exit ticket or my execution ticket. Orders are
  the priority and nothing sits on top of them.
- Removing the chat from Home must DELETE NO CONVERSATION. Every word I have
  said stays in History.
- The daily summary is SAVED in the database, because I am paying for it and I
  want the record of what happened. It is also an AI feature, so it obeys my
  standing rule: a manual button, an hour's cache, a daily cap, NEVER on page
  load.

HOW WE WORK. Plan first in plain English, six parts; I approve before any code.
Branch feature/swayam-ai-panel-0NN off main, never main, never a worktree.
git fetch before every push and check whether my pull request is already
merged. Hand off in five parts, files as clickable links, manual steps in bold
up front, one bold line saying what exists and what does not.

DO NOT TOUCH: the AI's persona, routes, model or cost cap. The colours, which
BUILD_06 has already changed. The Trade Journal page. The vault cage, the
database guard, my trade record. Trade 7cd4d017 is open on purpose.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. What happens to the page behind the panel when it opens, and what did I
   reject?
2. What size does it open at, and what does it remember?
3. What is replacing the chat on my Home page, where is it stored, and why
   does that matter to me?
4. Which tables does Delete touch, and which two survive?
5. What may the panel never cover, and why is that a money rule?
```
