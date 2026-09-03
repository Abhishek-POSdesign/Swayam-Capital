"""
FYERS API v3 OAuth Access Token Generator for Swayam Capital.

Walks Abhishek through the one-time interactive OAuth login to generate
a valid FYERS API access token and save it into `.env`.

Usage:
    python scripts/generate_fyers_token.py
"""

from pathlib import Path
import webbrowser
from fyers_apiv3 import fyersModel
from swayam.config import settings


def generate_token() -> None:
    """Guides the user through FYERS OAuth authentication and token persistence."""
    print("=" * 60)
    print("Swayam Capital — FYERS Authentication Helper")
    print("=" * 60)

    client_id = settings.fyers_client_id or input("Enter your FYERS Client ID (e.g., YA38914): ").strip()
    app_id = settings.fyers_app_id or input("Enter your FYERS App ID (e.g., ABC123-100): ").strip()
    secret_key = settings.fyers_secret_key or input("Enter your FYERS Secret Key: ").strip()
    redirect_uri = settings.fyers_redirect_uri

    if not app_id or not secret_key:
        print("[❌] Error: App ID and Secret Key are required to authenticate.")
        return

    session = fyersModel.SessionModel(
        client_id=app_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )

    auth_url = session.generate_authcode()
    print("\n[1] Opening your browser to log in to FYERS:")
    print(f"    URL: {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("[2] Log in and authorize the app.")
    print("[3] After authorization, your browser will redirect to a URL like:")
    print(f"    {redirect_uri}?s=ok&code=YOUR_AUTH_CODE&...\n")

    auth_code = input("Paste the 'code' parameter from the redirect URL here: ").strip()
    if not auth_code:
        print("[❌] Error: No auth code provided. Aborting.")
        return

    session.set_token(auth_code)
    response = session.generate_token()

    if response.get("s") == "ok" and "access_token" in response:
        token = response["access_token"]
        print(f"\n[✅] Authentication Successful! Access Token acquired.")

        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            if "FYERS_ACCESS_TOKEN=" in content:
                import re
                new_content = re.sub(r"FYERS_ACCESS_TOKEN=.*", f"FYERS_ACCESS_TOKEN={token}", content)
                env_path.write_text(new_content, encoding="utf-8")
                print(f"[✅] Successfully updated FYERS_ACCESS_TOKEN in {env_path}")
            else:
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write(f"\nFYERS_ACCESS_TOKEN={token}\n")
                print(f"[✅] Appended FYERS_ACCESS_TOKEN to {env_path}")
        else:
            print(f"[ℹ] Save this token into your `.env` file as FYERS_ACCESS_TOKEN={token}")
    else:
        print(f"[❌] Failed to generate token: {response}")


if __name__ == "__main__":
    generate_token()
