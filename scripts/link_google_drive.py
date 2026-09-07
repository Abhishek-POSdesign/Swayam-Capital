"""
Links Swayam to Abhishek's Google Drive, once, so the live site can write
journal notes into his Second Brain from the cloud.

WHY THIS IS NEEDED
------------------
`G:\\My Drive\\Second Brain` is a drive letter that Google Drive for Desktop
paints onto his PC. The live site is a Linux container in Singapore with no
drive letters and no view of his machine, so a Windows path there is
meaningless. The folder must be reached over the internet, through the Drive
API.

WHY A SERVICE ACCOUNT CANNOT DO IT
----------------------------------
Every service account has had a ZERO byte Drive quota since June 2023. A file
it creates is owned by it, and an owner with no quota cannot hold a file, so
the write fails with storageQuotaExceeded. Sharing the folder grants permission
but not storage. The two standard escapes, a Shared Drive and domain-wide
delegation, both require Google Workspace; his vault is on a personal Gmail
account. This was researched and settled on 2026-09-08.

So the app acts as HIM. Files are owned by him and use his own storage.

WHY THE drive.file SCOPE
------------------------
`drive.file` is classified NON-SENSITIVE: basic verification only, no security
assessment, and the sign-in does not expire. The full `drive` scope is
RESTRICTED and would need a Google security assessment because the app stores
data on a server, which is weeks of process to write a text file.

Its one constraint, stated plainly: **the app can only touch files and folders
it created itself.** So it creates its own folder. Abhishek then drags that
folder wherever he likes inside his vault, once. Access follows the folder, not
its path, so moving it changes nothing.

WHAT THIS SCRIPT DOES
---------------------
1. Opens his browser so he can approve, once.
2. Creates a folder in his Drive named "Swayam Journal".
3. Writes a test file into it and reads it back, to prove the whole path works.
4. Saves the refresh token to Google Secret Manager, so the live site can use
   it without the token ever sitting in the repository.

Run it once:

    .\\.venv\\Scripts\\python.exe scripts\\link_google_drive.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaIoBaseUpload  # noqa: E402

# Non-sensitive. Lets the app touch only what it creates. Do not widen this to
# the full `drive` scope without reading the note above about verification.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

PROJECT_ID = "swayam-capital"
SECRET_ID = "google-drive-refresh-token"
FOLDER_NAME = "Swayam Journal"


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main() -> int:
    print()
    print("  Linking Swayam to your Google Drive")
    print("  -----------------------------------")
    print()
    print("  You should already have created a Desktop app OAuth client at")
    print("  https://console.cloud.google.com/apis/credentials?project=swayam-capital")
    print()

    client_id = ask("  Paste the Client ID: ")
    if not client_id:
        print("\n  No client ID. Nothing was changed.")
        return 1
    client_secret = ask("  Paste the Client secret: ")
    if not client_secret:
        print("\n  No client secret. Nothing was changed.")
        return 1

    # A Desktop client uses a loopback redirect, so there is no redirect URI to
    # configure by hand and nothing to get subtly wrong.
    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print()
    print("  A browser window will open. Sign in as yourself and click Allow.")
    print("  If Google warns the app is unverified, click Advanced, then")
    print("  'Go to Swayam (unsafe)'. It is your own app on your own project.")
    print()

    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    # access_type=offline and prompt=consent are what actually return a refresh
    # token. Without them Google gives only a one-hour access token and the
    # live site would stop working an hour later for no visible reason.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent", open_browser=True
    )

    if not creds.refresh_token:
        print()
        print("  Google did not return a refresh token, so the live site could")
        print("  not keep working after an hour. Revoke the app at")
        print("  https://myaccount.google.com/permissions and run this again.")
        return 1

    print()
    print("  Signed in. Proving the whole path works before saving anything...")

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # 1. The folder. Reuse it if this script has run before.
    found = service.files().list(
        q=(
            "mimeType='application/vnd.google-apps.folder' and trashed=false "
            f"and name='{FOLDER_NAME}'"
        ),
        fields="files(id,name)",
        pageSize=5,
    ).execute().get("files", [])

    if found:
        folder_id = found[0]["id"]
        print(f"  Folder already exists: {FOLDER_NAME}")
    else:
        folder = service.files().create(
            body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id,name",
        ).execute()
        folder_id = folder["id"]
        print(f"  Created folder: {FOLDER_NAME}")

    # 2. Write a real file and read it back. If this fails, nothing is saved.
    body = b"# Swayam link test\n\nIf you can read this in Obsidian, the cloud can write to your vault.\n"
    media = MediaIoBaseUpload(io.BytesIO(body), mimetype="text/markdown")
    test = service.files().create(
        body={"name": "_swayam-link-test.md", "parents": [folder_id]},
        media_body=media,
        fields="id,name,webViewLink",
    ).execute()

    back = service.files().get_media(fileId=test["id"]).execute()
    if b"Swayam link test" not in back:
        print("  The file was written but could not be read back. Nothing saved.")
        return 1

    print("  Wrote a test note and read it back. The path works.")

    # 3. Only now, once it is proved, save the token.
    payload = json.dumps(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": creds.refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": SCOPES,
            "folder_id": folder_id,
        }
    )

    import subprocess

    def gcloud(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["gcloud", *args], input=stdin, capture_output=True, text=True
        )

    exists = gcloud(["secrets", "describe", SECRET_ID, f"--project={PROJECT_ID}"])
    if exists.returncode != 0:
        gcloud([
            "secrets", "create", SECRET_ID,
            f"--project={PROJECT_ID}", "--replication-policy=automatic",
        ])

    added = gcloud(
        ["secrets", "versions", "add", SECRET_ID, f"--project={PROJECT_ID}", "--data-file=-"],
        stdin=payload,
    )
    if added.returncode != 0:
        print()
        print("  Could not save to Secret Manager:")
        print("  " + (added.stderr or "").strip()[:400])
        print()
        print("  Your Drive link works, but the live site cannot use it yet.")
        return 1

    print("  Saved to Secret Manager as", SECRET_ID)
    print()
    print("  DONE. One thing left for you, and it takes ten seconds:")
    print()
    print("   1. Open Google Drive or your G: drive.")
    print(f"   2. Find the folder '{FOLDER_NAME}' at the top level of My Drive.")
    print("   3. Drag it into  Second Brain\\02 - Projects\\Trading\\")
    print()
    print("  Moving it does not break anything. Access follows the folder, not")
    print("  its location, which is exactly why this scope was chosen.")
    print()
    print("  Delete _swayam-link-test.md whenever you like.")
    print(f"  Test note: {test.get('webViewLink', '')}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
