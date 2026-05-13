# Crane Identifier — Runbook

Incident response + common operations for the crane identifier system.

## Common operations

### Identify a crane manually (curl test)

```bash
curl -X POST https://crane-identifier.gstcranes.com/api/identify-crane \
  -F image=@~/Desktop/known-tadano-1.jpg | python3 -m json.tool
```

Or via the Worker dev URL during testing.

### Check Roboflow training status

```bash
source .venv/bin/activate
python3 -c "
import requests, os, json
from pathlib import Path
key = next(l.split('=',1)[1].strip() for l in Path.home().joinpath('gst-cranes/.env').read_text().splitlines() if l.startswith('ROBOFLOW_API_KEY='))
r = requests.get(f'https://api.roboflow.com/gokmens-workspace/crane-recognition-v1-idh46/2?api_key={key}').json()
print(json.dumps(r.get('version',{}).get('train',{}), indent=2))"
```

### Trigger a retrain

```bash
.venv/bin/python roboflow-crane-ai/scripts/active_learning_weekly.py retrain
```

### Add new training images

The Roboflow project at https://app.roboflow.com/gokmens-workspace/crane-recognition-v1-idh46 supports drag-drop in the web UI. After uploading, generate a new version + train.

For programmatic upload:
```bash
.venv/bin/python roboflow-crane-ai/scripts/roboflow_upload.py
```
This re-reads `outputs/cleaned_labels.csv` and uploads anything in there not already in the state file.

### Update spec table

Edit `outputs/crane_specs_full.json` directly. Boom lengths are curated in `scripts/scrape_specs.py` (`KNOWN_BOOM` dict). After editing, rebuild the worker bundle:
```bash
cp roboflow-crane-ai/outputs/crane_specs_full.json roboflow-crane-ai/worker/src/crane_specs.json
cd roboflow-crane-ai/worker && wrangler deploy
```

## Incident playbooks

### Inference endpoint returning 502

```bash
# 1. Check Worker health
curl https://crane-identifier.gstcranes.com/health
# Expected: "ok"

# 2. Check Roboflow upstream
curl -X POST "https://serverless.roboflow.com/$ROBOFLOW_MODEL_ID?api_key=$ROBOFLOW_API_KEY&confidence=10" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "$(base64 < ~/Desktop/known-tadano-1.jpg)"
# Expected: JSON response with predictions

# 3. Roboflow status
open https://status.roboflow.com

# 4. Worker logs (Cloudflare dashboard or:)
wrangler tail crane-identifier
```

If Roboflow is down: site falls back gracefully (user sees error message + retry option).

### Confidence is consistently low on real uploads

Cause: production photos differ from training distribution. Solutions:

1. Run active learning batch immediately:
   ```bash
   .venv/bin/python roboflow-crane-ai/scripts/active_learning_weekly.py weekly
   ```
2. Manually review the queue, label correctly
3. Trigger retrain after labelling

### A specific class is misidentified consistently

Example: every Tadano ATF is being labelled Liebherr.

1. Check the class's sample count and quality:
   ```bash
   python3 -c "
   import json
   s = json.load(open('roboflow-crane-ai/outputs/crane_specs_full.json'))
   print({k: v.get('sample_count') for k, v in s.items() if 'tadano_atf' in k})"
   ```
2. If sample count < 50, the class is under-trained. Add more clean photos.
3. If sample count is high but accuracy is low, the photos may be mislabelled. Spot-check with Vision:
   ```bash
   .venv/bin/python roboflow-crane-ai/scripts/clean_labels.py
   ```
   Look at `outputs/needs_review.csv` for problematic samples.

### Roboflow credit exhausted

The Public plan has $60/mo free credits. If exhausted before month end:
- Inference stops returning predictions (Worker will see 402 from upstream)
- Worker should return a friendly error to the page
- Upgrade to Roboflow Core ($79/mo) or wait until next billing cycle

Check credit balance:
```
https://app.roboflow.com/gokmens-workspace/billing
```

### Cloudflare Worker rate-limited

Cloudflare Workers free tier: 100K requests/day. Crane identifier is well below this. If exceeded:
- Workers Paid: $5/mo for 10M requests/day. Easy upgrade.

## Monitoring

- **Inference success rate:** Worker emits no logs by default; if metrics needed, wire to Cloudflare Workers Analytics or a D1 store.
- **Top-1 confidence distribution:** monthly review during retrain. If median falls below 0.5, increase active learning frequency.
- **Roboflow training mAP / accuracy:** stored in `outputs/training_metrics*.json` after each retrain.

## Escalation

Owner: Gökmen Tanaçar (gokmen@gstcranes.com)

Vendor contacts:
- Roboflow support: support@roboflow.com or https://discuss.roboflow.com
- Cloudflare support: dashboard ticket
- Anthropic (for Vision API issues): https://support.anthropic.com
