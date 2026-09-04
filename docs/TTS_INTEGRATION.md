# Text-to-Speech (TTS) Integration — Swayam Capital (BUILD-9-FIXES-B)

## Overview

Swayam Capital integrates **Google Cloud Text-to-Speech** natively in Python via Cloud Run Application Default Credentials (ADC).

---

## 1. Authentication & IAM

- **Zero JSON Keys:** No API keys or service account keys are stored on disk.
- **Identity:** Cloud Run runs under the service account `swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com`.
- **Role Required:** `roles/texttospeech.editor`
  ```bash
  gcloud projects add-iam-policy-binding swayam-capital \
    --member="serviceAccount:swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com" \
    --role="roles/texttospeech.editor"
  ```

---

## 2. Voice Profiles

All voice profiles use Neural2 high-fidelity Indian English voices:
- `swayam_calm` (Default): `en-IN-Neural2-B` (Male, calm, focused delivery)
- `swayam_warm`: `en-IN-Neural2-A` (Female, clear, supportive delivery)

---

## 3. API Endpoint

`POST /api/tts/speak`
- **Request Payload:**
  ```json
  {
    "text": "India VIX is at 12.85 confirming low-volatility...",
    "voice": "swayam_calm",
    "speaking_rate": 0.90
  }
  ```
- **Response:**
  - Raw `audio/mpeg` stream.
  - Header `X-Voice-Truncated: true` if input exceeded 3,000 characters and was truncated at the last sentence boundary.

---

## 4. Frontend Player Component (`tts-player.js`)

- **Single Stream Playback:** Only one message speaks at a time; triggering playback on a new card automatically pauses any currently active audio.
- **In-Memory Caching:** Synthesized MP3s are cached by content hash in browser memory so repeated plays are instantaneous with zero API calls.
- **Settings Controls:** Voice profile and speaking rate slider (0.5x – 2.0x, step 0.05) configured via AI Settings Drawer.
