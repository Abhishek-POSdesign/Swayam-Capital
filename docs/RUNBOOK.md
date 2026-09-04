# ??? Swayam Capital — Operational Runbook & Troubleshooting Cheatsheet

Quick diagnostic guide for common production symptoms.

---

### 1. "URL returns 403 Forbidden"
- **Cause**: User is either not logged in with the authorized Google Account, or IAM/IAP permissions are missing.
- **Solution**:
  1. Confirm you are signed in as `abhisheksikka99.99@gmail.com`.
  2. Verify IAM invoker binding:
     ```powershell
     gcloud run services get-iam-policy swayam-dashboard --project=swayam-capital --region=asia-south1
     ```
  3. Ensure `user:abhisheksikka99.99@gmail.com` is listed with `roles/run.invoker`.

---

### 2. "URL returns 500 Internal Server Error"
- **Cause**: Backend unhandled exception or missing environment variable.
- **Solution**:
  1. Inspect live application tracebacks:
     ```powershell
     gcloud run services logs read swayam-dashboard --project=swayam-capital --region=asia-south1 --limit=50
     ```
  2. Verify all 7 required secrets exist in Secret Manager:
     ```powershell
     gcloud secrets list --project=swayam-capital
     ```

---

### 3. "Frontend loads white screen or broken UI, but API works"
- **Cause**: Static assets bundle in `web/dist` was not generated or improperly served.
- **Solution**:
  1. Confirm Stage 1 of `Dockerfile` (`npm run build`) succeeded without bundling errors.
  2. Verify locally:
     ```powershell
     cd web
     npm test
     ```

---

### 4. "Vertex AI Gemini fails or returns error"
- **Cause**: Missing AI location configuration or IAM permission on the service account.
- **Solution**:
  1. Confirm `GCP_AI_LOCATION=global` is set in Cloud Run service configuration.
  2. Check that `swayam-dashboard-sa` has `roles/aiplatform.user`.

---

### 5. "Cold start takes ~5-10 seconds on first load of the day"
- **Cause**: Container instances scale down to 0 when idle (`--min-instances=0`) to ensure $0 monthly cost.
- **Solution**:
  - Once the container wakes up, it stays warm for subsequent requests.
  - If instant zero-wait startup is ever preferred, set `--min-instances=1`:
    ```powershell
    gcloud run services update swayam-dashboard --project=swayam-capital --region=asia-south1 --min-instances=1
    ```
    *(Note: Keeping 1 instance warm 24/7 costs ~?400-500/month on Google Cloud).*
