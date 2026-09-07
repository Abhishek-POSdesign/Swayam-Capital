# MY TRADING RULES

**Abhishek Sikka · NIFTY options · Print this and put it where you can see it**
Settled 8 September 2026. If any agent or document tells you different, this sheet wins.

---

## THE FOUR NUMBERS

Everything is a percentage of my **live FYERS balance**, read fresh every session.
Never a stored figure. On 8 September 2026 that balance was **₹9,71,002**.

| # | Rule | What it means | On ₹9,71,002 |
|---|---|---|---|
| **1** | **Running loss: 1%** | If a live trade's loss passes this, I exit. No debate. | **₹9,710** |
| **2** | **Overnight gap: 2%** | Before carrying anything overnight, a gap of twice the average daily move must cost less than this | **₹19,420** |
| **3** | **Black swan: 5%** | The absolute worst case at expiry stays under this | **₹48,550** |
| **4** | **Deployable margin** | Twice my cash-equivalent holding. The broker refuses more. | **₹5,54,961** |

**The average daily move is measured from my own last 20 sessions.** On 8 September it was 80 points, so the overnight test gaps NIFTY **160 points up and down** and uses the worse.

---

## WHAT I AM FREE TO DO

**Anything, intraday.** Straddle, strangle, naked short, ratio, half-built structures. The system never blocks an entry. It cannot, because when I convert a straddle into a condor I have to exit legs and add legs, and for those two minutes the position looks terrible.

I sell the call at 2 pm, I watch it, and I hedge it before the close. That is allowed and always will be.

---

## WHAT I MUST NOT DO

**Carry an unhedged position overnight.** Not because a rule says so, but because there is nothing to measure. An uncapped position's worst case is *unlimited*, and 5% of my account cannot be compared to infinity. Hedge it into a condor or a butterfly and it becomes measurable.

**Trust a number that does not say where it came from.** Every figure on my screen must be real from FYERS or from my database, or it must say **unavailable**. Never a placeholder shown as real.

---

## THINGS I MUST NOT GET WRONG AGAIN

**The NIFTY lot is 65.** Not 75. Every rupee figure scaled by contracts was 15.4% too large until 8 September 2026.

**A short straddle is NOT risk capped.** Selling both legs at the same strike has the same unlimited loss as a strangle, and it starts losing sooner because both legs sit at the money. At one lot, a move to 25,800 costs ₹1,12,450 and it keeps going. What *is* capped is an **iron butterfly**, the same straddle with wings bought either side.

**Real margin is roughly double what the app used to claim.** One lot of NIFTY: a hedged spread costs about **₹66,836**, a naked short about **₹2,00,441**. The old figures of ₹32,000 and ₹1,15,000 were invented.

---

## MY DAILY ROUTINE

1. **After 8 am**, run `Refresh-Token.ps1` in the project folder. Never before 8 am; an early token dies by lunchtime.
2. Check the app shows a live NIFTY price. If it says no live price, the token is dead.
3. Trade the afternoon. I arrive at my desk between 1 and 2 pm.
4. **Before the close**, make sure nothing unhedged is left open.
5. Journal the trade.

**Signs the token has died:** no live price, legs showing no real price, or strikes jumping about a thousand points away from where NIFTY actually is.

---

## THE TWO RULES I GIVE EVERY AGENT

1. **No fake data.** Every number is real from FYERS or the database, or it says unavailable.
2. **Never tell me something is done, live or passing** unless you checked it on the running system that day and can show me the proof.

---

## WHAT THE READINESS FORM IS FOR

It is a journal. Sleep, alcohol, workout, mood, the five-minute meditation.

**It has zero power over my trading.** It cannot block a trade and it cannot shrink my size. I removed that on 7 September 2026, because a form I fill in myself can be lied to, and it should never stand between me and a decision about money.

---

*Real-money trading is code-blocked. This is a paper-trading terminal until I decide otherwise.*
