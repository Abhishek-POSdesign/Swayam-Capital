# Swayam Capital — System Architecture

**Source of Truth:** The design brief for the platform lives in Abhishek's Obsidian Second Brain at:  
`G:\My Drive\Second Brain\02 - Projects\Trading\06 - Platform Plan\Platform Overview.md`

---

## 🏛️ Physical Separation of Concerns

| Domain | Physical Location | Responsibility |
| :--- | :--- | :--- |
| **Strategy & Thinking** | `G:\My Drive\Second Brain\` | Method rules, journal analysis, trading philosophy (Claude-managed) |
| **Platform Code** | `D:\Claude\POS\Trading-Platform\Swayam Capital\` | Execution engine, math models, web dashboard (Antigravity-managed) |
| **Operational State** | Supabase (`swayam-capital`) | Live positions, immutable trade history, daily readiness logs |
| **Historical Data Cache** | Local Disk (`data/`) | High-frequency 1-min options cache, DuckDB options history |
| **Market Broker** | FYERS API v3 | Live price streaming (WebSocket) and order execution (REST) |

---

## 🔄 Core Data Flow

1. **Vault $\to$ Rules Engine:** `vault_reader.py` dynamically loads trading rules from markdown files in the Second Brain.
2. **FYERS API $\to$ Dashboard & Builder:** Live ticks stream into the visual Strategy Builder.
3. **Strategy Builder $\to$ Execution Controller:** Trade ideas are checked against `rules_engine.py` with `TolerantComparator`.
4. **Execution $\to$ Supabase & Journal:** Fills are recorded in Supabase, and markdown companion files are written back to the Second Brain (`04 - Journal/`).
