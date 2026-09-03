"""
FYERS Token Refresher & Secret Manager Sync for Swayam Capital.

Runs interactively to authenticate with FYERS, saves the new token to `.env`,
and uploads it to Google Cloud Secret Manager (`fyers-access-token`) for the
cloud options recorder.

Usage:
    python scripts/refresh_fyers_token.py
"""

from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import webbrowser

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project src directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from fyers_apiv3 import fyersModel
from swayam.config import settings


def push_token_to_gcp_secret_manager(token: str, project_id: str = "swayam-capital", secret_id: str = "fyers-access-token") -> bool:
    """Uploads new token version to Google Secret Manager using gcloud CLI."""
    print(f"\n[GCP] Uploading token to Secret Manager (project: {project_id}, secret: {secret_id})...")
    try:
        proc = subprocess.run(
            f"gcloud secrets versions add {secret_id} --data-file=- --project={project_id}",
            input=token,
            shell=True,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            print(f"[✅] Successfully updated secret version in GCP Secret Manager!")
            return True
        else:
            print(f"[❌] Error updating GCP Secret Manager: {proc.stderr}")
            return False
    except Exception as e:
        print(f"[❌] Exception pushing to GCP Secret Manager: {e}")
        return False


def refresh_token() -> None:
    """Interactively authenticates with FYERS and updates both local and cloud storage."""
    print("=" * 65)
    print("Swayam Capital — FYERS Token Refresh & GCP Secret Sync")
    print("=" * 65)

    app_id = settings.fyers_app_id
    secret_key = settings.fyers_secret_key
    redirect_uri = settings.fyers_redirect_uri or "https://trade.fyers.in/api-anchor/result.html"

    if not app_id or not secret_key:
        print("[❌] Error: FYERS_APP_ID and FYERS_SECRET_KEY must be configured in .env.")
        sys.exit(1)

    session = fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )

    auth_url = session.generate_authcode()
    print("\n[1] Opening your browser to authenticate with FYERS:")
    print(f"    URL: {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("[2] Log in with your PIN and OTP in the browser.")
    print("[3] Paste the returned auth code (or entire redirect URL) below:\n")

    raw_input = input("Paste auth code or redirect URL here: ").strip()
    if not raw_input:
        print("[❌] Error: No input provided. Aborting.")
        sys.exit(1)

    # Clean parsing
    if "code=" in raw_input or "auth_code=" in raw_input:
        parsed = urllib.parse.urlparse(raw_input)
        qs = urllib.parse.parse_qs(parsed.query or parsed.path)
        if "auth_code" in qs:
            auth_code = qs["auth_code"][0]
        elif "code" in qs:
            auth_code = qs["code"][0]
        else:
            m = re.search(r"(?:auth_code|code)=([^&\s]+)", raw_input)
            auth_code = m.group(1) if m else raw_input
    elif ":" in raw_input and ("auth_code" in raw_input or "code" in raw_input):
        auth_code = raw_input.split(":")[-1].strip()
    else:
        auth_code = raw_input

    session.set_token(auth_code)
    response = session.generate_token()

    if response.get("s") == "ok" and "access_token" in response:
        token = response["access_token"]
        print(f"\n[✅] Authentication Successful! New Access Token acquired.")

        # 1. Update local .env
        env_path = ROOT_DIR / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            if "FYERS_ACCESS_TOKEN=" in content:
                new_content = re.sub(r"FYERS_ACCESS_TOKEN=.*", f"FYERS_ACCESS_TOKEN={token}", content)
                env_path.write_text(new_content, encoding="utf-8")
                print(f"[✅] Successfully updated FYERS_ACCESS_TOKEN in {env_path}")
            else:
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write(f"\nFYERS_ACCESS_TOKEN={token}\n")
                print(f"[✅] Appended FYERS_ACCESS_TOKEN to {env_path}")

        # 2. Push to GCP Secret Manager
        project_id = settings.gcp_project_id or "swayam-capital"
        push_token_to_gcp_secret_manager(token, project_id=project_id)
        print("\nAll systems refreshed and ready for trading and recording.")
    else:
        print(f"[❌] Failed to generate token: {response}")
        sys.exit(1)


if __name__ == "__main__":
    refresh_token()
