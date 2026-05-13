# Hercules Deploy Prompt — Crane Identifier Backend + Frontend

Copy-paste this into Hercules to set up the crane identifier on `gstcranes.com`. Hercules will:
1. Mount the frontend page at `https://www.gstcranes.com/tools/crane-identifier`
2. Create the backend proxy at `https://www.gstcranes.com/api/identify-crane` that forwards uploads to our Cloudflare Worker

## Prerequisites (one-time)

1. Cloudflare Worker `crane-identifier` deployed at `https://crane-identifier.<your-cf-subdomain>.workers.dev` (or custom route `crane-identifier.gstcranes.com`).
2. Worker secret set: `ROBOFLOW_API_KEY=<from gst-cranes/.env>`.
3. Worker env var: `ROBOFLOW_MODEL_ID=gokmens-workspace/crane-recognition-v1-idh46/2` (or the latest version after retraining).

## Hercules prompt (paste into Hercules.app UI)

```
Create a new public page at /tools/crane-identifier on gstcranes.com with the following HTML.
The page should override window.CRANE_IDENTIFIER_ENDPOINT to "/api/identify-crane" so it
calls our same-origin proxy. Page title: "Identify a Crane — GST Cranes". Add it to the
main site nav under "Tools" if a Tools dropdown exists.

[paste contents of crane-identifier.html here, prefixed with this script tag to set the endpoint:]
<script>window.CRANE_IDENTIFIER_ENDPOINT = "/api/identify-crane";</script>

Then create a backend API route at POST /api/identify-crane that:
- Accepts multipart/form-data uploads with field name "image" (max 10 MB)
- Forwards the multipart body to https://crane-identifier.gstcranes.com/api/identify-crane
  (substitute the actual Cloudflare Worker URL if a custom domain is not configured)
- Streams back the JSON response unchanged
- Forwards CORS / Content-Type headers from upstream
- Returns 502 on upstream errors with body {"error":"upstream_failed"}

The page must be indexable (no auth required). Cache the HTML response 1 hour
(Cache-Control: public, max-age=3600). Do NOT cache the API response.

Smoke test plan after deploy:
1. Visit https://www.gstcranes.com/tools/crane-identifier — page loads, drop zone visible
2. Drag a Liebherr LTM photo onto it — should identify within 3-5 seconds
3. Confidence bar + prediction visible, "Find this crane" CTA links to gstcranes.com search
```

## After Hercules deploys

Verify by uploading these test images (you have local files):
- `~/Desktop/known-tadano-1.jpg` → expects Tadano top-1
- `~/Desktop/known-tadano-2.jpg` → expects Tadano top-1
- `~/Desktop/clip-top-match-debug.jpeg` → expects Tadano top-1
- A Liebherr LTM 1500 photo from your archive → expects Liebherr (model varies)

If accuracy is poor on a specific photo, save it for the active learning weekly review queue.

## Operational notes

- Model retrain cadence: monthly (cron in scripts/active_learning_weekly.py)
- Confidence thresholds (set in Worker env):
  - `CONF_TOP1_SHIP = 0.75` — above this, auto-fill the brand+model
  - `CONF_NEEDS_REVIEW = 0.40` — below this, flag for review queue
  - 0.40-0.75 range → show top-3 to user
- Cost: ~$0.0024 per inference call after free tier ($60/mo Public). At 1K uploads/month ≈ $2.40.
