# AI Integration Philosophy & Architecture — Swayam Capital

> *"My way of using AI is different. I give freehand to my AI. You have to make sure you have a place for the AI."*  
> — **Abhishek Sikka (2026-09-04)**

This document establishes the official AI integration principles for **Swayam Capital**, adapting the core philosophy documented in Abhishek's POS Design Bible (Chapters 19–23) to a high-stakes, rule-enforced options trading environment.

---

## 1. Core Principles (Distilled from Design Bible Chapters 19–23)

### Principle A: App Logic Owns Truth; AI Owns Interpretation (Chapter 21)
The fundamental tenet of the POS ecosystem is strict role separation:
- **Application Logic & Rules Engine:** Calculate quantitative facts, verify mathematical constraints, apply strict percentage limits with `TolerantComparator`, and manage trade execution.
- **AI Partner:** Interprets regime context, explains why a setup passed or failed, surfaces cognitive blind spots, and drafts journal reflections.
- **The Inviolable Rule:** AI is never an uncontrolled calculator or autonomous database authority. The software and the broker API determine execution truth.

### Principle B: Co-Presence, Not Interruption (Chapter 19)
The AI is a peer collaborator in the room, not an intrusive overlay that blocks market visibility.
- On the dashboard, AI commentary and prompts sit as companion cards alongside the Setup Queue and Journal.
- The interface preserves spatial permanence: the trader can glance at live market quotes while reading the AI's reasoning.

### Principle C: Hybrid Model Routing & Provider Agnostic (Chapter 20)
Abhishek operates in a fluid multi-model world. The platform must never be hardwired to a single model:
- The adapter pattern (`src/swayam/ai/`) decouples application code from underlying providers (Vertex AI, OpenRouter, Direct Anthropic/OpenAI/Gemini).
- Switching models or providers is a zero-code configuration change in `.env`.

### Principle D: Structured Personas with Strict Boundaries (Chapter 20)
Generic conversational prompts are prohibited in financial execution. The trading AI operator operates under an explicit, structured persona:
- Specific role (Risk & Discipline Officer).
- Specific domain constraints (NIFTY options, 2–14 day swing timeframe, multi-leg spreads).
- Strict negative constraints ("Never suggest naked long options; never encourage revenge trading; never recommend overriding a stop-loss").

### Principle E: Memory Compaction & Standing Facts (Chapter 22)
Continuous chat history creates token bloat and context drift. The platform uses entry-based memory:
- **Moment Pins:** Flagging a specific rule insight or setup lesson.
- **Session Summaries:** End-of-day review summaries stored compactly.
- **Memory Consolidation:** Monthly distillations of lessons learned across trading journals.

---

## 2. Adapting POS Principles to Options Trading

While productivity apps focus on task completion and habit tracking, a trading platform deals with direct financial risk and intense emotional pressure. Therefore, Swayam adapts the POS principles with heightened rigor:

| Dimension | POS Standard (Task / Finance App) | Swayam Capital Adaptation |
| :--- | :--- | :--- |
| **Authority** | AI can suggest task re-prioritization | AI can **never** authorize a trade that violates Method rules |
| **Risk Gate** | Soft warnings | Hard software block enforced by `rules_engine.py` |
| **Psychology** | Focus on productivity momentum | Focus on preventing tilt, revenge trading, and impulsive sizing |
| **Execution** | User clicks save | Two-tier gate: Rules Engine verification $\to$ Trader execution |

---

## 3. Where AI Slots In Across Swayam Components

AI in Swayam Capital is a first-class collaborator across five specific functional slots:

1. **Setup Queue Rationale & Filter Commentary:**  
   When a setup candidate is evaluated against the 6-factor regime filter, the AI generates a succinct 2-sentence rationale highlighting confluence or hidden structural risks.
2. **Risk & Sizing Explanation:**  
   When the `TolerantComparator` flags a spread as approaching the 1% risk ceiling, the AI provides plain-English commentary on margin efficiency and tail-risk exposure.
3. **Market Context & Event Synthesis:**  
   The AI digests upcoming macroeconomic events (RBI MPC, FOMC, Union Budget) and synthesizes the implied volatility regime for the current expiry week.
4. **Journal Reflection Prompts:**  
   Following Abhishek's Method rules for trade exits, the AI prompts qualitative reflection questions ("Did you follow your planned exit, or did you cut early out of anxiety?").
5. **Backtest Interpretation:**  
   Analyzing historical simulation runs to identify regime vulnerabilities (e.g., "This Bear Put Spread underperforms when India VIX drops below 12").

---

## 4. The Trust-and-Verify Flow: "AI Proposes, Method Disposes"

```
[ Market Context + Setup Candidate ]
               │
               ▼
┌──────────────────────────────┐
│       AI Collaborator        │  <--- Analyzes setup, drafts thesis,
│   (Synthesis & Explanation)  │       checks qualitative context
└──────────────┬───────────────┘
               │ Proposed Strategy Payload
               ▼
┌──────────────────────────────┐
│     Swayam Rules Engine      │  <--- Mathematically verifies 1% cap,
│     (TolerantComparator)     │       checks no-single-leg gate, ensures R:R >= 2.0
└──────────────┬───────────────┘
               │ Validated Setup
               ▼
┌──────────────────────────────┐
│       Trader Decision        │  <--- Abhishek approves or rejects
│  (Paper Trade vs Real Trade) │
└──────────────────────────────┘
```

---

## 5. Scope for BUILD-1

- **In Scope:** The abstract `AIProvider` base interface, multi-provider adapter stubs (`vertex`, `openrouter`, `direct`), factory loader, and `.env.example` configurations.
- **Explicitly Out of Scope:** Live LLM network calls, prompt templates, and active token billing. These will be wired in future component builds as specific tasks require them.
