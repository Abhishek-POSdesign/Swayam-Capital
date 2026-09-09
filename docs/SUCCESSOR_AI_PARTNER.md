# THE PROMPT FOR THE AI PARTNER CHAT

> Written 2026-09-10 at his request, when he decided to split the work into two
> chats: `SUCCESSOR_BACKTESTER.md` for the backtester, and this one for the AI.
>
> **Copy everything inside the fence and paste it as the first message of a new
> chat.** Nothing else needs saying.

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS FOR DESIGNING THE AI
TRADING PARTNER AND NOTHING ELSE. The backtester is a separate chat; if we drift
into building it, stop me and say so.

READ THESE FIRST, ALL THE WAY THROUGH. Do not ask me where anything is.
1. docs/PLAN.md section 2.17.  THE JOB DESCRIPTION FOR THE AI, in my own words.
                               This is the specification. Start here.
2. docs/ROADMAP.md             The direction, and section 0 is my end goal.
                               You may not edit it without my approval.
3. docs/SWAYAM_START_HERE.md   Where everything lives and what is verified true.
4. CLAUDE.md                   How to work here, and what I actually trade.
5. In my vault, 02 - Projects/Trading/06 - Platform Plan/
   Self-Improving Agent Integration.md, which already carries the tuning
   discipline this must follow.

WHO I AM. I am Abhishek, I am not a developer, and I speak my prompts rather
than typing them, so an odd word is transcription and not intent. Ask me if
something reads wrong. Plain English, never code for me to approve, and give me
a recommendation rather than a menu.

MY HOURS. Night shift. I wake around 1 pm IST and I am at the screen by 2 pm. I
trade roughly 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data: every number is real or says unavailable with the
reason. This matters MORE for the AI than for anything else, because prose hides
a made-up figure far better than a screen does. And never tell me something is
done, live or passing unless you checked it that day and can show me the proof.

WHAT I WANT, AND WHAT I DO NOT.

I do NOT want an AI that prints strategies and tells me to use them. I would
have no way to tell a good one from a confident one. Do not build a signal
service and do not put a recommended trade anywhere on my screen.

I DO want a trading partner who sits with me and does the backtesting, who tells
me to my face when my logic does not hold, who I can correct when it is wrong
about how humans actually behave, and who replaces the books so I am not reading
articles to understand a structure or a definition during my 90 minutes. A
colleague, a mentor, a buddy. Then together we name the structures of what we
find. The naming is part of the work.

THE LINE THAT KEEPS IT HONEST, which I agreed to: the AI never scores its own
idea. It proposes, explains, argues and objects. The measuring is done by the
engine on real data and the number comes back from something neither of us
chose. My vault already says the equivalent for tuning: one variable at a time,
a written hypothesis, human approved, never auto-applied.

WHAT IT HAS TO KNOW, in three layers that must not be mixed:
  1. General market knowledge, which you mostly have already.
  2. My own record, which is in my vault and is what makes it mine: 21 swing
     trades from 2022-23, my intraday year of 2025-26, my charges, my rules.
  3. The findings we agree together, named and written down. THIS LAYER DOES
     NOT EXIST YET and it is the real product of the partnership.

WHAT MUST NOT CHANGE.
- AI-heavy work is a manual button, a 60-minute cache and a daily cap. Never on
  page load. Unguarded this was estimated at ₹4,000 a month.
- Method files are constitution. Hand-edited only, never auto-applied.
- No autonomous execution, ever, at this stage. I am in the loop for every
  decision about money, always. ROADMAP section 0.

WHY THIS MATTERS MORE THAN IT LOOKS. I built a Second Brain in Obsidian so I
would not have to keep explaining myself to every agent who helps me. It is not
structured well enough for that yet. The AI partner is the interface to it, and
its first job is to know my story so I never have to tell it again.

TWO THINGS I SETTLED ON 2026-09-10, SO YOU DO NOT REPEAT AN OLD ASSUMPTION.

My backtesting starts from a clean slate: new strategies out of my own head, not
copied from my past. My old trades are not the material and not the test. But
they are NOT off limits either. Use my history whenever it is genuinely useful,
and say every time that it is flawed data. Use every source we have: my history,
my broker, the market, the API, the WebSocket, the recorder, the NSE files.
docs/PLAN.md 2.16.0.

And any data work starts from 2022, not 2018, because the market before and
after Corona are different markets.

I keep ONE CHAT PER PURPOSE. docs/CHAT_PROMPTS.md lists them all, and the other
prompts are docs/SUCCESSOR_PROMPT.md for the main chat and
docs/SUCCESSOR_BACKTESTER.md for the backtester.

WHAT I EXPECT FROM THIS CHAT. Talk with me. I will talk a great deal and you
structure what I say and read it back. Do not answer a half-formed thought with
a build plan. We are designing what this thing is before anything is built.

QUESTIONS I EXPECT YOU TO PUT TO ME.
- What should it refuse to answer, and what should it say when it refuses?
- How does it hold a conversation across days without me repeating myself?
- What does it read from my vault, and what should it never read?
- How do I correct it, and where does that correction get stored so it sticks?
- What does it cost me a month, and what is the cap?
```

---

## NOTES FOR THE SESSION THAT READS THIS, not for him

**PLAN.md §2.17 is the specification and it is quoted from him directly.** Read
it before responding to anything. He asked for it to be written down precisely so
he would not have to say it again, and repeating the question back to him is the
failure mode he is trying to prevent.

**The strongest thing he said, and the thing to protect:** he does not want a
shortcut. He wants to stop needing books. Those are different products and it
would be easy to build the first while believing you built the second.

**He wants correction to run both ways.** He is explicit that when the AI is
wrong about human behaviour he will say so, and he expects that to stick. Where
that correction is stored, and how it survives a new chat, is a real design
question and probably the hardest one in this chat.

**Do not build in this chat.** He split the work precisely so design and
construction do not contaminate each other. If a build is agreed, it is a
separate branch and probably a separate session.

**Context on him that he should not have to repeat:** he stopped drinking about
a year ago, has had no craving for more than a hundred days, and attributes his
losing intraday year to that rather than to his method. He is rebuilding
deliberately and is not in a hurry. His words: "I'm looking for a long-term
career."
