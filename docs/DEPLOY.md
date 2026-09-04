# ?? Swayam Capital — Cloud Deployment Runbook (Cloud Run + Custom Subdomain)

## 1. Architecture Overview

```
Browser -> https://swayam.abhisheksikka.com
    | Google-managed SSL certificate (auto-issued, auto-renewing)
    v Google Identity-Aware Proxy (IAP) / Cloud Run IAM
Cloud Run service "swayam-dashboard"
    +-- FastAPI backend at /api/* (Uvicorn ASGI workers managed by Gunicorn)
    +-- Vite-built frontend at /* (static files from web/dist, SPA fallback)
    |
    +-- Supabase (via env vars injected from Google Secret Manager)
    +-- FYERS API (daily access token & client credentials from Secret Manager)
    +-- Vertex AI Gemini (global location, service account ADC)
    +-- Google Cloud Storage (options bhavcopy bucket)
```

## 2. One-Time Setup Summary (Completed)

1. **Dedicated Service Account**:
   - `swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com`
   - Roles granted:
     - `roles/secretmanager.secretAccessor`
     - `roles/aiplatform.user`
     - `roles/storage.objectViewer`

2. **Artifact Registry**:
   - Repository: `swayam` (Docker format, `asia-south1`)
   - Container Image: `asia-south1-docker.pkg.dev/swayam-capital/swayam/dashboard:latest`

3. **Google Secret Manager**:
   - `swayam-supabase-url`
   - `swayam-supabase-anon-key`
   - `swayam-supabase-service-role-key`
   - `fyers-access-token`
   - `fyers-client-id`
   - `fyers-app-id`
   - `fyers-secret-key`

4. **Security & Access Policy**:
   - Only `abhisheksikka99.99@gmail.com` has `roles/run.invoker` and `roles/iap.httpsResourceAccessor`.

## 3. How to Redeploy Manually

Whenever you make code updates and want to deploy a new revision:

```powershell
$sha = (git rev-parse --short HEAD)
gcloud builds submit --project=swayam-capital --config=cloudbuild.yaml --substitutions=_TAG=$sha
```

## 4. How to Check Live Logs

```powershell
# View recent server requests and application logs
gcloud run services logs read swayam-dashboard --project=swayam-capital --region=asia-south1 --limit=50
```

## 5. Revisions and Rollbacks

```powershell
# View currently active revision
gcloud run services describe swayam-dashboard --project=swayam-capital --region=asia-south1 --format="value(status.latestReadyRevisionName)"

# Roll back 100% of traffic to a previous known-good revision
gcloud run services update-traffic swayam-dashboard --project=swayam-capital --region=asia-south1 --to-revisions=<REVISION_NAME>=100
```

## 6. Daily FYERS Token Refresh

Each morning before market open (around 8:45 AM IST), update the FYERS token in Secret Manager:

```powershell
echo -n "<NEW_FYERS_ACCESS_TOKEN>" | gcloud secrets versions add fyers-access-token --project=swayam-capital --data-file=-
```

Cloud Run automatically picks up new secret versions on subsequent requests without requiring a rebuild.
