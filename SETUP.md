# Swayam Capital — Setup Guide 🛠️

This guide takes you from a clean machine to a fully verified Swayam Capital development environment.

---

## 1. Prerequisites

- **Operating System:** Windows 10/11
- **Python:** Python 3.11 or higher (verified with Python 3.13)
- **Node.js:** v18 or higher (for frontend development in BUILD-3)
- **Git:** Installed and authenticated with GitHub

---

## 2. Python Virtual Environment Setup

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd "D:\Claude\POS\Trading-Platform\Swayam Capital"
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

---

## 3. Environment Variables Configuration

1. Copy the example environment file:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` in your editor and provide the required credentials:
   - **FYERS API:** `FYERS_CLIENT_ID`, `FYERS_APP_ID`, `FYERS_SECRET_KEY`, `FYERS_REDIRECT_URI`.
   - **Supabase:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
   - **Vault Paths:** Verify that `VAULT_PATH` points to your Google Drive Obsidian folder (`G:\My Drive\Second Brain`).

---

## 4. Supabase Database Initialization

1. Create a new project in [Supabase](https://supabase.com) named `swayam-capital`.
2. Copy the Project URL and API keys into `.env`.
3. Apply the initial schema migration:
   ```powershell
   python scripts/apply_migration.py 001
   ```
   *(Alternatively, copy and run `migrations/001_initial_schema.sql` directly inside Supabase's SQL Editor).*

---

## 5. FYERS API Token Generation

1. Run the token generation helper:
   ```powershell
   python scripts/generate_fyers_token.py
   ```
2. Log in with your FYERS credentials in the browser window that opens.
3. The script will save the generated `FYERS_ACCESS_TOKEN` into your `.env` file automatically.

---

## 6. Run System Health Verification (Smoketest)

Verify that all subsystems (Environment, Obsidian Vault, Rules Engine, Supabase, FYERS API, and DuckDB) are communicating properly:

```powershell
python -m swayam.smoketest
```

When all 7 checks display green checkmarks (`[✅]`), the foundation is ready for BUILD-2!
