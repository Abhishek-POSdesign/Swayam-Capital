# AI Trading Partner — Swayam Capital

## What is it?

The Trading Partner is a purpose-built Vertex AI Gemini integration inside the Swayam Capital dashboard. It is NOT a generic chatbot. It's a specialist colleague that:

- Knows Abhishek's full Method (rules, risk limits, R:R targets)
- Has read his entire trading history (FY 2025-26 charges disaster, 2022-23 profitable swing period)
- Knows his current open positions, readiness verdict, and margin base at every turn
- Enforces 6 non-negotiable behavioral constraints — it will NEVER suggest naked longs, encourage revenge trades, advise stop widening, override RED verdicts, claim directional certainty, or allow cap exceptions

## Architecture

```
Dashboard (AI Chat Panel)
    │
    │  POST /api/ai/conversations/{id}/messages
    │  SSE streaming response
    ▼
FastAPI (src/swayam/api/routes/ai.py)
    │
    │  build_full_system_prompt() — persona + context
    │  ai_router.stream_main_turn() — 3-tier model routing
    ▼
AI Router (src/swayam/ai/router.py)
    │
    ├─── Tier 1: gemini-3.1-pro-preview   (primary)
    ├─── Tier 2: gemini-2.5-pro           (fallback on RateLimit/Permission/NotFound)
    └─── Tier 3: gemini-2.5-flash-lite    (reserved for widgets, not used in BUILD-6)
    │
    ▼
VertexAIProvider (src/swayam/ai/providers/vertex.py)
    │  Uses google-genai SDK with enterprise=True
    │  Pure ADC — no JSON key files
    ▼
Vertex AI Gemini (GCP project: swayam-capital)
```

## Persona System Prompt

The persona is defined in `src/swayam/ai/persona/trading_partner.py` as `TRADING_PARTNER_PERSONA` — a static string versioned in git.

**6 Non-Negotiable Constraints (hardcoded in the system prompt):**
1. Never recommend a naked long call or long put
2. Never encourage a revenge trade
3. Never suggest widening a stop (references Trade-07, Dec 27 2022: -₹21,000)
4. Never override a RED readiness verdict
5. Never claim directional certainty — only probabilities and R:R
6. Never allow exceptions to the 1% per-trade cap

**Tone:** Direct, colleague-to-colleague. No "great question", no sycophancy.

## Dynamic Context Assembly

Every user turn triggers `assemble_context()` which builds a live context block:

| Section | Source | Failure behaviour |
|---------|--------|------------------|
| Method Rules | VaultReader → Risk Management Rules.md | Non-fatal: notes "unavailable" |
| Margin Base | Supabase `swayam_config.margin_base_inr` | Non-fatal: notes "unavailable" |
| NIFTY Spot | FYERS API | Non-fatal: notes "market closed" |
| Readiness Verdict | Supabase `swayam_readiness_log` | Non-fatal: notes "not logged today" |
| Open Positions | Supabase `swayam_positions` | Non-fatal: notes "unavailable" |
| Recent Journal | Vault `04 - Journal/` last 5 MD files | Non-fatal: shows empty |
| Personal Trading Brief | Vault `00 - Reference/Personal Trading Brief.md` | Non-fatal: notes "not available" |
| Historical Trade Journal | Vault `00 - Reference/Historical Trade Journal Overview.md` | Non-fatal |
| Historical Swing Trades | Vault `00 - Reference/_Swing Trades Overview.md` | Non-fatal |

**No silent fallbacks.** Every failure is noted in the context so the AI knows what data it doesn't have. It will say "I don't have that number" rather than guessing.

## 3-Tier Model Routing

| Tier | Model | Used for | Triggered by |
|------|-------|----------|-------------|
| Primary | `gemini-3.1-pro-preview` | All main conversation turns | Default |
| Fallback | `gemini-2.5-pro` | Auto-downgrade | Rate limit / permission / model-not-found |
| Lightweight | `gemini-2.5-flash-lite` | Widget summaries (future) | Reserved |

If both primary and fallback fail, the API returns a clear error: "Trading Partner offline. Underlying error: X." with a Retry button. **Never** a silent failure or fake response.

## Supabase Schema (Migration 002)

Four tables added:

- **`swayam_ai_conversations`** — conversation sessions with title, timestamps, archived flag
- **`swayam_ai_messages`** — message history with role, content, context_snapshot JSONB, provider (tier used), token counts, latency
- **`swayam_rule_evolution_log`** — audit trail for when rules change (future: Rules Workshop UI)
- **`swayam_ai_usage_daily`** — daily cost aggregate by model tier

Apply with: `python scripts/apply_migration.py 002`

## Cost Tracking

Displayed in the AI panel footer: "Today's AI spend: ₹4.20 (12 requests)"

Pricing (Sept 2026 Vertex AI, Gemini 2.5 Pro, prompts ≤200k tokens):
- Input: \$1.25 per 1M tokens → \$0.00125/1k tokens
- Output: \$10 per 1M tokens → \$0.005/1k tokens
- Multiply by 83 for INR

Configurable in `.env`:
```
AI_INPUT_COST_PER_1K_USD=0.00125
AI_OUTPUT_COST_PER_1K_USD=0.005
USD_TO_INR_RATE=83.0
```

**September 29, 2026 decision point:** When Abhishek's \$300 credit expires, review actual usage data in `swayam_ai_usage_daily` (aggregated by model) and decide: keep 3.1 Preview if stable, downgrade to 2.5 Pro, or evaluate alternatives. The `.env` multi-model config makes this a one-line change.

## How to Tune the Persona

The persona lives in `src/swayam/ai/persona/trading_partner.py` as `TRADING_PARTNER_PERSONA`. To modify:

1. Edit the string in code
2. Commit with `build(ai): update persona — [reason]`
3. No migration needed — persona is in code, not DB

The 6 behavioral constraints in the `# Non-negotiable behaviors` section should only be changed after careful review. They are what makes this a trading discipline tool, not just a chatbot.

## How to Switch Providers

Change in `.env`:
```
AI_PROVIDER=vertex           # or 'openrouter', 'direct'
AI_MODEL_PRIMARY=gemini-3.1-pro-preview
AI_MODEL_REASONING_FALLBACK=gemini-2.5-pro
AI_MODEL_LIGHTWEIGHT=gemini-2.5-flash-lite
```

The factory (`src/swayam/ai/factory.py`) and router (`src/swayam/ai/router.py`) pick up the new values on next restart. No code changes needed to switch models.

## Conversation Persistence

Conversation history is stored in Supabase (`swayam_ai_messages`). On dashboard load, the most-recently-active conversation is resumed automatically. Past conversations are accessible via the History button.

The AI is **READ-ONLY**: it cannot write to journal files, insert positions, or modify Method rules. It can only read context and generate text responses.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/conversations` | POST | Create new conversation |
| `/api/ai/conversations` | GET | List recent 20 non-archived |
| `/api/ai/conversations/{id}/messages` | GET | Full message history |
| `/api/ai/conversations/{id}/messages` | POST | Send message (SSE stream) |
| `/api/ai/conversations/{id}/archive` | POST | Soft-delete |
| `/api/ai/conversations/{id}` | DELETE | Hard-delete |
| `/api/ai/usage/today` | GET | Today's cost aggregate |

## SSE Streaming Format

```
data: {"delta": "Bear"}\n\n
data: {"delta": " Put"}\n\n
data: {"delta": " Spread..."}\n\n
data: [DONE]\n\n
```

Error format (mid-stream):
```
data: {"error": "Trading Partner offline: Vertex AI quota exceeded. Retry in ~60 seconds."}\n\n
data: [DONE]\n\n
```
