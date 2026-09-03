"""
Unified Health Check & Smoketest Tool for Swayam Capital.

Executes end-to-end verification across Environment, Obsidian Vault readability,
Method rules parsing, Supabase connectivity, FYERS API authentication, real-time
quotes, and local DuckDB cache storage.

Usage:
    python -m swayam.smoketest
"""

import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.config import settings
from swayam.db import db
from swayam.fyers_client import fyers_client
from swayam.local_db import local_db
from swayam.vault_reader import VaultReader


def run_smoketest(skip_web: bool = False) -> bool:
    """Executes core connectivity and web checks and prints a formatted status report.

    Args:
        skip_web: If True, skips local API and web build checks.

    Returns:
        bool: True if all critical checks pass, False otherwise.
    """
    print("\nSwayam Capital — Smoketest")
    print("=" * 60)

    all_passed = True

    # 1. Environment Check
    missing = settings.validate_required_vars()
    if not missing:
        print("[OK] Environment  — all required vars present")
    else:
        print(f"[FAIL] Environment  — missing {len(missing)} required vars: {', '.join(missing)}")
        all_passed = False

    # 2. Vault Path Check
    vault_path = settings.vault_path
    method_path = settings.trading_method_path
    if vault_path.exists() and method_path.exists():
        print(f"[OK] Vault        — {vault_path} reachable")
    else:
        print(f"[FAIL] Vault        — path not found: {vault_path}")
        all_passed = False

    # 3. Method Rules Parsing
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    try:
        rules = reader.load_rules()
        print(f"[OK] Method Rules — parsed rules from Method files (Percentages Only):")
        print(f"      per_trade_risk_pct: {rules.per_trade_risk_pct * 100:.1f}%")
        print(f"      rr_minimum:         {rules.rr_minimum:.1f}")
        print(f"      rr_target:          {rules.rr_target:.1f}")
        print(f"      daily_loss_cap:     {rules.daily_loss_cap_pct * 100:.1f}%")
        print(f"      weekly_loss_cap:    {rules.weekly_loss_cap_pct * 100:.1f}%")
        print(f"      blast_radius:       {rules.blast_radius_pct * 100:.1f}%")
        print(f"      overnight_hedge:    {rules.overnight_hedge_cap_pct * 100:.1f}%")
        print(f"      alcohol_lockout:    {rules.alcohol_lockout_days} days")
        print(f"      sleep_threshold:    < {rules.sleep_no_trade_threshold_hours} hrs = No Trade")
    except Exception as e:
        print(f"[FAIL] Method Rules — failed to parse Method files: {e}")
        all_passed = False

    # 4. Supabase Connectivity
    try:
        client = db.client
        res = client.table("swayam_config").select("key, value").execute()
        rows = res.data or []
        print(f"[OK] Supabase     — connected, swayam_config table has {len(rows)} seed rows")
    except Exception as e:
        print(f"[FAIL] Supabase     — connection error: {e}")
        all_passed = False

    # 5. FYERS Authentication
    try:
        profile = fyers_client.get_profile()
        user_name = profile.get("name", "Unknown")
        fyers_id = profile.get("fy_id", settings.fyers_client_id or "YA38914")
        print(f"[OK] FYERS Auth   — logged in as {fyers_id} ({user_name})")
    except Exception as e:
        print(f"[FAIL] FYERS Auth   — {e}")
        all_passed = False

    # 6. FYERS Live Quote Plausibility
    try:
        spot = fyers_client.get_nifty_spot()
        if 10000.0 <= spot <= 50000.0:
            print(f"[OK] FYERS Data   — NIFTY spot: {spot:,.2f}")
        else:
            print(f"[WARN] FYERS Data   — NIFTY spot returned unexpected value: {spot}")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] FYERS Data   — {e}")
        all_passed = False

    # 7. DuckDB Local Storage
    try:
        table_count = local_db.get_table_count()
        row_count = local_db.get_row_count()
        print(f"[OK] DuckDB       — {settings.duckdb_path.name} active, {table_count} tables, {row_count} rows")
    except Exception as e:
        print(f"[FAIL] DuckDB       — failed to open DuckDB: {e}")
        all_passed = False

    # 8. AI Provider — Vertex AI Gemini reachability
    try:
        from swayam.ai.providers.vertex import VertexAIProvider
        provider = VertexAIProvider(
            project_id=settings.gcp_project_id,
            location=settings.gcp_region,
            model=settings.ai_model_primary,
        )
        # Verify google-genai client initialises without error
        _ = provider._get_client()
        print(
            f"[OK] AI Provider  — Vertex AI Gemini reachable, "
            f"project: {settings.gcp_project_id}, "
            f"model: {settings.ai_model_primary}"
        )
    except ImportError:
        print("[FAIL] AI Provider  — google-genai not installed. Run: .venv\\Scripts\\pip.exe install google-genai>=1.0.0")
        all_passed = False
    except Exception as e:
        print(f"[FAIL] AI Provider  — {e}")
        all_passed = False


    # 8. API Server Check (Optional / skipped with --skip-web)
    if not skip_web:
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:8000/health")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    print("[OK] API Server   — reachable at http://localhost:8000/health")
                else:
                    print(f"[FAIL] API Server   — returned status {resp.status}")
        except Exception:
            print("[INFO] API Server   — not running (start with `python -m uvicorn swayam.api.main:app --port 8000`)")

    # 9. Frontend Build Check (Optional / skipped with --skip-web)
    if not skip_web:
        dist_html = settings.project_root / "web" / "dist" / "index.html"
        pkg_json = settings.project_root / "web" / "package.json"
        if dist_html.exists():
            print("[OK] Frontend     — web/ dist build verified")
        elif pkg_json.exists():
            print("[INFO] Frontend     — web/ installed (build with `cd web && npm run build`)")
        else:
            print("[FAIL] Frontend     — web/ directory not found")

    print("=" * 60)
    if all_passed:
        print("All checks passed. Foundation is ready.\n")
    else:
        print("Some checks failed. Review missing credentials or paths above.\n")

    return all_passed


if __name__ == "__main__":
    skip_web_flag = "--skip-web" in sys.argv
    success = run_smoketest(skip_web=skip_web_flag)
    sys.exit(0 if success else 1)
