"""
Scheduled task runner for end-of-day readiness reconciliation in Swayam Capital.

Executes daily at ~22:00 IST via Windows Task Scheduler to compare Abhishek's
pre-trade manual readiness self-assessment against the fully-synced Atlas data.
"""

from datetime import date
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project src to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.readiness.reconciler import reconcile_readiness_for_date


def main() -> None:
    today = date.today()
    print("=" * 60)
    print(f"Swayam Capital — Evening Readiness Reconciler ({today})")
    print("=" * 60)

    try:
        reconciliation = reconcile_readiness_for_date(today)
        print(f"Reconciled at: {reconciliation.reconciled_at}")
        if reconciliation.has_discrepancies:
            print(f"[!] {len(reconciliation.discrepancies)} discrepancy/discrepancies noted:")
            for d in reconciliation.discrepancies:
                print(f"    - {d.field}: manual={d.manual}, atlas={d.atlas} ({d.note or ''})")
        else:
            print("[OK] All subjective assertions matched synced Atlas data perfectly.")
    except Exception as e:
        print(f"[ERROR] Reconciliation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
