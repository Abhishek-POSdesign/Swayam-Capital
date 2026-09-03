"""
Automated deployment script for Swayam Live Options Recorder (GCP Cloud Function + Cloud Scheduler).
"""

from pathlib import Path
import subprocess
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.config import settings

PROJECT_ID = settings.gcp_project_id or "swayam-capital"
REGION = settings.gcp_region or "asia-south1"
BUCKET = settings.gcs_options_bucket or "swayam-capital-options-data"
SERVICE_ACCOUNT = f"swayam-recorder@{PROJECT_ID}.iam.gserviceaccount.com"
FUNCTION_NAME = "swayam-recorder"
SCHEDULE_NAME = "swayam-recorder-schedule"


def run_command(cmd: str, desc: str) -> str:
    """Executes a shell command with real-time feedback and error checking."""
    print(f"\n---> {desc}")
    print(f"Command: {cmd}")
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[❌] Error during {desc}:\n{proc.stderr}")
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {proc.stderr}")
    print(f"[✅] {desc} succeeded.")
    return proc.stdout.strip()


def deploy() -> None:
    print("=" * 65)
    print(f"Swayam Capital — Deploying Live Options Recorder to GCP ({PROJECT_ID})")
    print("=" * 65)

    source_dir = ROOT_DIR / "cloud" / "recorder"
    if not source_dir.exists():
        raise RuntimeError(f"Source directory not found: {source_dir}")

    # 1. Deploy Cloud Function Gen2
    deploy_cmd = (
        f'gcloud functions deploy {FUNCTION_NAME} '
        f'--gen2 '
        f'--runtime=python311 '
        f'--region={REGION} '
        f'--source="{source_dir}" '
        f'--entry-point=record_snapshot '
        f'--trigger-http '
        f'--allow-unauthenticated=false '
        f'--service-account={SERVICE_ACCOUNT} '
        f'--memory=512MB '
        f'--timeout=60s '
        f'--min-instances=0 '
        f'--max-instances=1 '
        f'--project={PROJECT_ID} '
        f'--set-secrets=FYERS_ACCESS_TOKEN=fyers-access-token:latest '
        f'--set-env-vars=FYERS_CLIENT_ID={settings.fyers_client_id},FYERS_APP_ID={settings.fyers_app_id},GCS_OPTIONS_BUCKET={BUCKET}'
    )
    run_command(deploy_cmd, "Deploying Cloud Function Gen2")

    # 2. Retrieve Cloud Function URI
    uri_cmd = (
        f'gcloud functions describe {FUNCTION_NAME} '
        f'--gen2 '
        f'--region={REGION} '
        f'--project={PROJECT_ID} '
        f'--format="value(serviceConfig.uri)"'
    )
    function_uri = run_command(uri_cmd, "Retrieving Cloud Function URI")
    print(f"Function Endpoint URI: {function_uri}")

    # 3. Create or Update Cloud Scheduler Job
    # Check if job exists
    check_job_cmd = (
        f'gcloud scheduler jobs describe {SCHEDULE_NAME} '
        f'--location={REGION} '
        f'--project={PROJECT_ID}'
    )
    job_exists = subprocess.run(check_job_cmd, shell=True, capture_output=True).returncode == 0

    if job_exists:
        scheduler_cmd = (
            f'gcloud scheduler jobs update http {SCHEDULE_NAME} '
            f'--location={REGION} '
            f'--project={PROJECT_ID} '
            f'--schedule="*/1 9-15 * * 1-5" '
            f'--time-zone="Asia/Kolkata" '
            f'--uri="{function_uri}" '
            f'--http-method=POST '
            f'--oidc-service-account-email={SERVICE_ACCOUNT}'
        )
        run_command(scheduler_cmd, "Updating Cloud Scheduler Job")
    else:
        scheduler_cmd = (
            f'gcloud scheduler jobs create http {SCHEDULE_NAME} '
            f'--location={REGION} '
            f'--project={PROJECT_ID} '
            f'--schedule="*/1 9-15 * * 1-5" '
            f'--time-zone="Asia/Kolkata" '
            f'--uri="{function_uri}" '
            f'--http-method=POST '
            f'--oidc-service-account-email={SERVICE_ACCOUNT}'
        )
        run_command(scheduler_cmd, "Creating Cloud Scheduler Job")

    print("\n" + "=" * 65)
    print("Swayam Live Options Recorder is LIVE in Google Cloud!")
    print(f"Location:  {REGION} (Mumbai)")
    print(f"Trigger:   Every minute Mon-Fri 09:15-15:30 IST via Cloud Scheduler")
    print(f"Bucket:    gs://{BUCKET}/")
    print("=" * 65)


if __name__ == "__main__":
    deploy()
