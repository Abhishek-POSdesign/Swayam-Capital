# BUILD 07, THE AI PANEL — HANDOFF TO THE MAIN CHAT

> Written 2026-09-12 by the Build 07 builder chat. Everything below was checked
> on the running system today, in a real browser, in both themes, against the
> real backend. Where something was NOT checked, it says so.

**Branch** `feature/swayam-ai-panel-057` · **Pull request**
[#86](https://github.com/Abhishek-POSdesign/Swayam-Capital/pull/86) · cut off
`main` at `4faf6ae`, which already contained #84.

---

## ⚠️ 1. ONE MANUAL STEP, AND IT IS BEFORE MERGE

**Migration 026 has NOT been applied.** He applies it, the way he applied 022
and 023.

```powershell
cd "D:\Claude\POS\Trading-Platform\Swayam Capital"
.\.venv\Scripts\python.exe scripts\apply_migration.py 026
```

The file is inlined at the end of this handoff so it can be read without
opening the branch. In one sentence, it creates one table, `swayam_daily_summary`,
with the trading day as its key, and copies the newest summary of each of his
three past days into it. **It deletes nothing and it alters no existing table.**

**To check it worked**, the terminal itself is the check: open Home. Before the
migration the "So far today" card says the table could not be read and names
it. After it, the card says nothing is saved for today yet and the Generate
button comes back to life. He does not need to run a query.

**What happens if he merges without it.** Nothing breaks and nothing is lost.
The card says, in words, which table could not be read and that migration 026
is probably why, and **Generate refuses rather than spending money it cannot
record**. That refusal is deliberate: without the row the daily cap cannot be
counted, and a cost rule that cannot be counted is not a cost rule.

**THE BUILD IS IN A WORKTREE, NOT HIS PRIMARY FOLDER.**
`D:\Claude\POS\Trading-Platform\swayam-ai-panel-057`. His primary folder was
switched to `main` by another session while this was being built, so it was
left alone. Nothing in it was touched. After merge the files land in the
primary folder at the paths below and those links start working.

---

## 2. Files changed

Nineteen files. No change to the AI's persona, its routes, its model, its cost
cap or its grounding. No change to trades, fills, charges, rules or the record.

| File | What changed, in plain English |
|---|---|
| [migrations/026_daily_summary.sql](migrations/026_daily_summary.sql) | **New.** The table that holds one market summary a day, for ever, and the copy of his three existing ones into it |
| [src/swayam/services/so_far_today.py](src/swayam/services/so_far_today.py) | The summary is saved as one row a day instead of a new row on every press. The daily cap counts presses on that row |
| [src/swayam/api/routes/home.py](src/swayam/api/routes/home.py) | Home now reads the day's saved summary however old it is, and says out loud when it cannot |
| [src/swayam/api/routes/ai.py](src/swayam/api/routes/ai.py) | Deleting a conversation now takes its pictures with it instead of leaving them in the bucket for ever |
| [web/src/components/ai-panel-frame.js](web/src/components/ai-panel-frame.js) | **New.** Everything about where the window sits: dragging, the eight handles, detach and attach, the bar, and remembering the place |
| [web/src/components/ai-chat.js](web/src/components/ai-chat.js) | The conversation itself: starter prompts deleted, Clear and Delete added, the microphone added, the old blue swapped for sage |
| [web/index.html](web/index.html) | The drawer became the floating panel, and the four canned questions that used to flash on load are gone |
| [web/src/main.js](web/src/main.js) | Opening the panel no longer does anything at all to the page behind it |
| [web/src/styles.css](web/src/styles.css) | **The 400-pixel page shift is deleted**, along with the rule that collapsed both left rails |
| [web/src/styles/swayam-tokens.css](web/src/styles/swayam-tokens.css) | The window's own look, its eight handles, and the layer that keeps it under both order tickets |
| [web/src/styles/swayam-desk.css](web/src/styles/swayam-desk.css) | The card's shape, and the attachment thumbnail's baked-in dark that followed no theme |
| [web/src/pages/home.js](web/src/pages/home.js) | The chat zone off Home, and "So far today" mounted in its own place |
| [web/src/components/so-far-today-card.js](web/src/components/so-far-today-card.js) | The card redrawn to the mockup, no longer hiding itself, and saying which model wrote it |
| [web/tests/test_ai_panel.test.js](web/tests/test_ai_panel.test.js) | **New.** 25 tests holding the rules of the window |
| [tests/test_daily_summary_and_delete.py](tests/test_daily_summary_and_delete.py) | **New.** 10 tests holding one row a day, and what Delete may and may not touch |
| [tests/test_home_snapshot.py](tests/test_home_snapshot.py) | Moved to the new storage, plus two new cases |
| [web/tests/test_home_rebuild.test.js](web/tests/test_home_rebuild.test.js) | Now asserts Home has no chat zone at all |
| [web/tests/test_home_snapshot_cards.test.js](web/tests/test_home_snapshot_cards.test.js) | The card's new wording, with the never-fires-on-load rule kept exactly as it was |
| [web/tests/test_round2_desk.test.js](web/tests/test_round2_desk.test.js) | The auto-folding test replaced by its opposite: the summary must stay |

---

## 3. Three things the browser found that the plan and the tests had not

All three were found by invoking, and none of them could have been found by
reading.

### 3.1 The mockup's header has no room for the panel's own name

Measured at the size the panel opens at: one row holding the title and all
seven controls needs **491 pixels** against 360 available. The name was
squeezed to nothing and the window had no title at all. **The mockup has the
same fault and hides it behind `overflow: hidden`**, because it was drawn
rather than measured.

**The header is now what a window's header actually is:** a title bar carrying
the name, the conversation's name and the three window buttons, and a toolbar
under it carrying New, History, Clear, Delete and the settings gear. Both rows
fit inside 360 pixels with room to spare. **It opens 280 pixels tall rather
than 250, to keep four or five lines of conversation.** That is the one
deliberate deviation from the mockup in this build, and the reason is measured.

### 3.2 A missing table read as a quiet day

Before migration 026 is applied the card said "Nothing saved for today yet.
Press Generate", which invites a paid call whose result then cannot be stored.
**A failed read is not an empty store.** It now names the table, repeats what
the database said, and says migration 026 may be why.

### 3.3 The build document was wrong in three places

Already recorded by the main chat in PLAN 2.22.3, and all three held up:
"So far today" already existed, removing Home's chat would have taken it with
it, and there was no speech-to-text anywhere in the repository.

---

## 4. What to test, in his own window

Each of these is an action he takes and a thing he sees.

**The window itself, on the Strategy Desk**

1. Press the sage button in the bottom-right corner. A small window opens with
   four or five lines. **Look at the page behind it: nothing has moved.**
2. Drag it by its title bar, the row with the green dot and the name. Put it
   somewhere you like.
3. Pull it by any edge or any corner. Try to make it bigger than half your
   screen. It will stop.
4. Press the dash. It shrinks to its bar. Press it again.
5. Press the arrows. It goes back to the corner. Press again, it comes loose.
6. Press the cross. Then reload the page. **It comes back small, in the place
   you left it.** That is the rule: it remembers where, never how big.

**The rule you said you would be angry about**

7. With the window sitting over the middle of the desk, open the exit ticket on
   your condor. **The ticket must cover the window completely.** Press Back;
   the window is still where you left it.

**The microphone**

8. Press the microphone. Chrome will ask for permission the first time. Say
   something and watch it appear in the box. **If you ever see the microphone
   missing, there will be a line of words in its place telling you what to do.**

**Home**

9. Go to Home. **The chat box is gone.** Scroll down: "So far today" is there
   in its place.
10. Press History in the floating panel. **Every conversation you have ever had
    is still there.** Nothing was deleted by removing the chat.
11. Press Generate once. The summary appears and stays. Press it again inside
    the hour and it returns the same one without charging you.

**Clear and Delete**

12. Press Clear. The pane empties and says the conversation is still in
    History. Press History and open it again: every word is there.
13. Press Delete. **It asks first**, and tells you what goes and what stays.
    Press "Keep it" if you do not mean it.

**Both themes.** Press the sun in the header and look at the panel again.

---

## 5. Next steps, and what exists

**The exact thing to do:** apply migration 026 with the command in section 1,
open Home to confirm the card comes alive, then work through section 4. When
you are happy, bring this file's path to the main chat, and merge
[#86](https://github.com/Abhishek-POSdesign/Swayam-Capital/pull/86) yourself.

**After merge:** delete the branch local and remote, pull `main` in the primary
folder, and remove the worktree with
`git worktree remove "D:\Claude\POS\Trading-Platform\swayam-ai-panel-057"`.
Two dev servers are running on ports 8010 and 5180 and can be stopped.

---

## ⚠️ WHAT EXISTS AND WHAT DOES NOT

**EXISTS, checked on the running system on 12 September 2026:** the floating
panel with all eight handles and the half-window ceiling, measured; the page
not moving, measured at 1425 pixels with the panel open, closed and reopened;
the exit ticket covering the panel, hit-tested at three points rather than read
from a stylesheet; the position remembered and the size forgotten across a
reload; no starter prompts anywhere; Clear emptying the pane with the
conversation count unchanged; the Delete question appearing and "Keep it"
sending nothing; the microphone's refusal saying what to do instead; Home with
no chat and the card in its place; the payoff graph and both sliders still
drawing; **110 conversations and 35 messages before and after, counted against
his live database.**

**DOES NOT EXIST YET, and needs him:**

- **The table.** Migration 026 is written and tested as SQL but **has not been
  applied**, so the summary being saved and read back has NOT been proven on
  the running system. It is the last thing in this build that is unproven and
  it is one command.
- **Dictation actually transcribing.** The Browser pane blocks microphone
  capture, so only the refusal path could be exercised. The words appear
  correctly in both the no-engine and the blocked cases.
- **Everything the market being shut hides.** This was verified after hours.

**Two things found and deliberately NOT fixed, because they are outside this
build.** The AI's voice-settings drawer (`ai-settings-drawer.js`) still sits at
layer 1000, above both order tickets, and still carries a blue border where the
terminal went sage. It is a different component from the panel and he has to
open it deliberately, but **the main chat should decide whether it wants the
same treatment.**

---

## THE MIGRATION, INLINE

Only the part that acts. The file carries a long comment above it explaining
why each column exists.

```sql
CREATE TABLE IF NOT EXISTS public.swayam_daily_summary (
    day              date        PRIMARY KEY,
    text             text        NOT NULL,
    sources          jsonb       NOT NULL DEFAULT '[]'::jsonb,
    search_queries   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    model            text,
    generated_at     timestamptz NOT NULL DEFAULT NOW(),
    generation_count integer     NOT NULL DEFAULT 1,
    ai_tokens_used   integer
);

CREATE INDEX IF NOT EXISTS idx_daily_summary_day
    ON public.swayam_daily_summary (day DESC);

-- The backfill. The newest summary of each past IST day, counted honestly.
-- Re-runnable: a day that already exists is left alone.
WITH src AS (
    SELECT
        (generated_at AT TIME ZONE 'Asia/Kolkata')::date AS ist_day,
        payload, generated_at, ai_tokens_used,
        ROW_NUMBER() OVER (
            PARTITION BY (generated_at AT TIME ZONE 'Asia/Kolkata')::date
            ORDER BY generated_at DESC) AS newest_first,
        COUNT(*) OVER (
            PARTITION BY (generated_at AT TIME ZONE 'Asia/Kolkata')::date) AS presses_that_day
    FROM public.swayam_home_snapshot
    WHERE snapshot_type = 'so_far_today'
      AND COALESCE(payload ->> 'text', '') <> ''
)
INSERT INTO public.swayam_daily_summary
    (day, text, sources, search_queries, model, generated_at, generation_count, ai_tokens_used)
SELECT ist_day, payload ->> 'text',
       COALESCE(payload -> 'sources', '[]'::jsonb),
       COALESCE(payload -> 'search_queries', '[]'::jsonb),
       NULL, generated_at, presses_that_day::integer, ai_tokens_used
FROM src
WHERE newest_first = 1
ON CONFLICT (day) DO NOTHING;
```

**It will create three rows**, for 6, 7 and 8 September, which are the only
days he has ever generated a summary on. Counted against his live database
today. **The model column is left empty on those three on purpose:** the old
payload never recorded which model wrote them, and inferring it from source
control would be a guess wearing the clothes of a fact.
