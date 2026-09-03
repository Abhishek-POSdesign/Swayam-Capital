# ☁️ Google Cloud Platform Setup Walkthrough

This document outlines the one-time configuration performed to set up the dedicated Google Cloud environment for Swayam Capital.

---

## 1. Project & Identity Configuration

- **GCP Project ID:** `swayam-capital`
- **Project Number:** `535273918813`
- **Region:** `asia-south1` (Mumbai)
- **Billing Account:** `010610-56A8FD-B55A28`
- **Parent Organization:** `abhisheksikka99-99-org` (`513385672487`)
- **Authentication Model:** Pure Application Default Credentials (ADC) + Service Account Identity (zero stored JSON private keys).

---

## 2. One-Time Setup Commands Executed

### Step 1: Create the Project
```bash
gcloud projects create swayam-capital --name="Swayam Capital" --set-as-default
```

### Step 2: Link Billing Account
```bash
gcloud billing projects link swayam-capital --billing-account=010610-56A8FD-B55A28
```

### Step 3: Enable Required Services (10 APIs)
```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  eventarc.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  --project=swayam-capital
```

### Step 4: Create Cloud Storage Bucket
```bash
gcloud storage buckets create gs://swayam-capital-options-data \
  --project=swayam-capital \
  --location=asia-south1 \
  --uniform-bucket-level-access
```

### Step 5: Create Dedicated Service Account
```bash
gcloud iam service-accounts create swayam-recorder \
  --display-name="Swayam Options Recorder" \
  --project=swayam-capital
```

### Step 6: Grant IAM Permissions
```bash
# Bucket permissions for writing Parquet files
gcloud storage buckets add-iam-policy-binding gs://swayam-capital-options-data \
  --member="serviceAccount:swayam-recorder@swayam-capital.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Logging permissions
gcloud projects add-iam-policy-binding swayam-capital \
  --member="serviceAccount:swayam-recorder@swayam-capital.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# Vertex AI permission for Abhishek (for BUILD-6 AI Trading Partner)
gcloud projects add-iam-policy-binding swayam-capital \
  --member="user:abhisheksikka99.99@gmail.com" \
  --role="roles/aiplatform.user"
```

### Step 7: Create Secret Manager Slot for FYERS Token
```bash
gcloud secrets create fyers-access-token \
  --replication-policy=automatic \
  --project=swayam-capital

gcloud secrets add-iam-policy-binding fyers-access-token \
  --member="serviceAccount:swayam-recorder@swayam-capital.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=swayam-capital
```

---

## 3. Daily Operations

### Morning Token Sync (08:45–09:00 IST)
Whenever FYERS expires (daily), run:
```powershell
python scripts/refresh_fyers_token.py
```
This updates both your local `.env` and pushes the active token directly into Google Secret Manager (`fyers-access-token`), ensuring the Cloud Function recorder has valid credentials when the market opens at 09:15 IST.

### Nightly Data Sync (22:30 IST)
```powershell
python scripts/ingest_gcs_to_duckdb.py
```
Downloads that day's recorded Parquet file from `gs://swayam-capital-options-data` and updates your local DuckDB `options_history` table.

---

## 4. AI Trading Partner Verification (BUILD-6)

The AI Trading Partner connects directly to Vertex AI Gemini models using your local Application Default Credentials:

1. **Verify your local session is authenticated:**
   ```powershell
   gcloud auth application-default login
   ```
2. **Apply Database Migration 002 (adds AI chat tables):**
   ```powershell
   python scripts/apply_migration.py 002
   ```
3. **Verify AI Reachability via Smoketest:**
   ```powershell
   python -m swayam.smoketest --skip-web
   ```
   Look for: `[OK] AI Provider — Vertex AI Gemini reachable, project: swayam-capital, model: gemini-3.1-pro-preview`

