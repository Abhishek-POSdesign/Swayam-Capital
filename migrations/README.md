# Database Migrations (Supabase)

All database schema evolutions for Swayam Capital are managed through sequential, **additive-only** SQL files in this directory.

---

## 📜 Migration Rules

1. **Additive Only:** Once a migration has been applied or shipped, it must **never** be edited or deleted.
2. **Sequential Numbering:** Migrations are prefixed with a 3-digit number (e.g., `001_initial_schema.sql`, `002_add_trade_tags.sql`).
3. **Applying Migrations:**
   Run the migration runner:
   ```powershell
   python scripts/apply_migration.py 001
   ```
   Or execute the SQL script directly in the Supabase SQL Editor dashboard.
