# Adobe Firefly Services API — Setup Guide

## Prerequisites

- An Adobe account (free tier works for developer access)
- A credit card may be required for API access (pay-per-use billing)

## Step-by-Step Setup

### 1. Go to Adobe Developer Console

Open: https://developer.adobe.com/console

Sign in with your Adobe account.

### 2. Create a New Project

- Click **"Create new project"** (top right)
- Give it a name: `GST Cranes Image Processing`

### 3. Add Firefly Services API

- In your new project, click **"Add API"**
- Search for **"Firefly Services"**
- Select it and click **"Next"**

### 4. Configure Authentication

- Choose **"OAuth Server-to-Server"** credential type
- This gives you machine-to-machine access (no user login needed)
- Click **"Save configured API"**

### 5. Copy Credentials

On the credential details page you will see:

- **Client ID** (also called API Key)
- **Client Secret** (click "Retrieve client secret" to reveal)

### 6. Add to .env

Open `~/gst-cranes/.env` and add:

```
ADOBE_CLIENT_ID=your_client_id_here
ADOBE_CLIENT_SECRET=your_client_secret_here
```

### 7. Verify

Run:

```bash
cd ~/gst-cranes
source .venv/bin/activate
python scripts/gorsel-hazirla.py --check-auth
```

This will authenticate and confirm your credentials work.

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `https://ims-na1.adobelogin.com/ims/token/v3` | OAuth token exchange |
| `https://firefly-api.adobe.io/v2/images/generate-remove` | Generative Remove (text/logo removal) |
| `https://image.adobe.io/upload` | Image upload to Adobe storage |

## Pricing Notes

- Firefly Services uses **generative credits**
- Generative Remove costs ~1 credit per image
- Free tier includes a limited number of credits
- Check current pricing at: https://developer.adobe.com/firefly-services/pricing/

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check Client ID and Secret are correct. Regenerate secret if needed. |
| 403 Forbidden | Ensure Firefly Services API is added to your project. |
| Token expired | The script caches tokens and refreshes automatically. Delete `.adobe-token-cache.json` to force refresh. |
| Rate limit (429) | Script has built-in retry with backoff. Wait a minute and retry. |
