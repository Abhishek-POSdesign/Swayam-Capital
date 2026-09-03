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

Verify that all subsystems (Environment, Obsidian Vault, Rules Engine, Supabase, FYERS API, DuckDB, and Web) are communicating properly:

```powershell
python -m swayam.smoketest
```

---

## 7. Web Dashboard Setup (`web/`)

1. Ensure Node.js (`v18+`) is installed (`node -v`, `npm -v`).
2. Install frontend dependencies:
   ```powershell
   cd web
   npm install
   ```
3. Run the development server:
   ```powershell
   npm run dev
   ```
4. Start the backend in a separate terminal:
   ```powershell
   python -m uvicorn swayam.api.main:app --reload --port 8000
   ```
5. Open [**http://localhost:5173**](http://localhost:5173) in your browser.

> **Note on Supabase Project:** The default project reference is `wxijlrwoiaeaupaaqecc`. Ensure your `.env` contains `SUPABASE_URL=https://wxijlrwoiaeaupaaqecc.supabase.co` and the corresponding anon key.

---

## 8. Scheduled Task Setup (Evening Readiness Reconciler)

To automatically reconcile your 2:30 PM manual self-assessment with the fully-synced Atlas data each night at 22:00 IST:

1. Press `Win + R`, type `taskschd.msc`, and press **Enter** to open Windows Task Scheduler.
2. Click **Create Basic Task...** in the Actions panel on the right.
3. **Name:** `Swayam Capital Daily Readiness Reconciler`
4. **Trigger:** Select **Daily** and set start time to `22:00:00` (10:00 PM).
5. **Action:** Select **Start a program**:
   - **Program/script:** `D:\Claude\POS\Trading-Platform\Swayam Capital\.venv\Scripts\python.exe`
   - **Add arguments:** `scripts\run_reconciler.py`
   - **Start in:** `D:\Claude\POS\Trading-Platform\Swayam Capital`
6. Click **Finish**.
7. *(Optional Verification)*: You can test it immediately by right-clicking the new task and clicking **Run**, or running `python scripts/run_reconciler.py` in PowerShell.
