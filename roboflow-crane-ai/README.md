# Roboflow Crane AI — `roboflow-crane-ai/`

Crane recognition system for gstcranes.com — user uploads a photo, system returns brand + model + confidence. Powered by a Roboflow-hosted DINOv3 image classifier trained on 9.5K curated crane photos across 59 brand+model classes.

## Architecture

```
                  ┌────────────────────────────────┐
                  │ gstcranes.com/tools/            │
   (1) upload     │   crane-identifier              │
   ──────────────▶│   (Hercules-deployed page)      │
                  └──────────────┬─────────────────┘
                                 │ POST /api/identify-crane
                                 ▼
                  ┌─────────────────────────────────┐
                  │ Hercules backend proxy          │
                  └──────────────┬──────────────────┘
                                 │ proxy to Worker
                                 ▼
                  ┌─────────────────────────────────┐
                  │ Cloudflare Worker               │
                  │ (worker/src/index.ts)           │
                  │  · base64 image                 │
                  │  · spec-aware post-process      │
                  └──────────────┬──────────────────┘
                                 │ POST inference
                                 ▼
                  ┌─────────────────────────────────┐
                  │ Roboflow Hosted Inference       │
                  │ serverless.roboflow.com/{model} │
                  └─────────────────────────────────┘
```

## Pipeline (one-time training)

| Phase | Script | Output |
|---|---|---|
| 0 — Discovery | (manual + `extract_labels.py`) | `DISCOVERY.md` |
| 1 — Plan | (manual) | `PLAN.md` |
| 2 — Annotation | `scripts/extract_labels.py` then `scripts/clean_labels.py` | `outputs/cleaned_labels.csv` (13,377 rows) |
| 3 — Upload | `scripts/roboflow_upload.py` | Roboflow project `crane-recognition-v1-idh46` (9.5K images, 59 classes, 70/20/10 split) |
| 4 — Training | `scripts/roboflow_train.py` + direct API for DINOv3 | Hosted model + `outputs/training_metrics.json` |
| Spec table | `scripts/scrape_specs.py` | `outputs/crane_specs_full.json` (53/54 cap, 44/54 axles, 52/54 boom_main_m) |
| 5 — Inference | `worker/src/index.ts` | Cloudflare Worker proxy |
| 6 — Site integration | `outputs/crane-identifier.html` + `outputs/hercules-backend-prompt.md` | Hercules page mount |
| 7 — Active learning | `scripts/active_learning_weekly.py` | Weekly review queue + monthly retrain |

## Quickstart (running already-built system)

```bash
# 0. One-time deps
cd ~/gst-cranes && source .venv/bin/activate
pip install anthropic roboflow

# 1. Inspect current state
python3 roboflow-crane-ai/scripts/extract_labels.py     # rebuild label index
cat roboflow-crane-ai/outputs/crane_specs_full.json     # spec table

# 2. Deploy worker (one-time)
cd roboflow-crane-ai/worker
npm install
wrangler login
wrangler secret put ROBOFLOW_API_KEY     # paste key from gst-cranes/.env
wrangler deploy

# 3. Hand off frontend to Hercules
cat outputs/hercules-backend-prompt.md   # copy-paste into Hercules

# 4. Set up active learning cron
crontab -e
# Add:
#   0 9 * * 1   cd ~/gst-cranes && .venv/bin/python roboflow-crane-ai/scripts/active_learning_weekly.py weekly >> roboflow-crane-ai/state/cron.log 2>&1
#   0 6 1 * *   cd ~/gst-cranes && .venv/bin/python roboflow-crane-ai/scripts/active_learning_weekly.py retrain >> roboflow-crane-ai/state/cron.log 2>&1
```

## Operational metrics

- **Training set:** 9,454 annotated images, 59 classes, train/valid/test = 6,607/1,890/957
- **Augmentation:** horizontal flip, ±20% brightness, ±12° rotate, blur ≤1px, 3 outputs/example
- **Preprocessing:** static-crop top 65% (boom-focused), resize 640×640
- **Model architectures tried:**
  - `resnet50` (v1) — top-1 accuracy ~0.68
  - `vit_base_patch16_dinov3.lvd1689m` (v2, current) — TBD after training
- **Inference cost:** ~$0.0024 per call (after free $60/mo Public plan credit)
- **Confidence thresholds:**
  - `top-1 ≥ 0.75` → autofill brand+model
  - `0.40 ≤ top-1 < 0.75` → show user top-3 to pick
  - `top-1 < 0.40` → flag `needs_review` (active learning queue)

## Files

```
roboflow-crane-ai/
├── README.md                                  # this file
├── DISCOVERY.md                               # Phase 0 corpus discovery
├── PLAN.md                                    # Phase 1 plan (approved)
├── RUNBOOK.md                                 # incident response
├── scripts/
│   ├── extract_labels.py                      # raw label aggregator
│   ├── clean_labels.py                        # Sonnet Vision re-annotation
│   ├── roboflow_upload.py                     # batched upload with split distribution
│   ├── roboflow_train.py                      # SDK train trigger
│   ├── scrape_specs.py                        # freecranespecs PDF parser
│   └── active_learning_weekly.py              # weekly review + monthly retrain cron
├── worker/
│   ├── wrangler.toml
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts                           # Worker code
│       └── crane_specs.json                   # bundled spec table (read-only)
├── outputs/
│   ├── raw_labels.csv                         # initial brand+model labels
│   ├── cleaned_labels.csv                     # Vision-verified, 13,377 rows
│   ├── needs_review.csv                       # decal-conflict samples
│   ├── target_classes.json                    # 73 classes ≥30 samples
│   ├── crane_specs_full.json                  # spec table (capacity/axles/boom)
│   ├── crane_specs.json                       # raw scrape (partial)
│   ├── training_metrics.json                  # v1 ResNet50 metrics
│   ├── training_metrics_v2_dinov3.json        # v2 DINOv3 metrics (after train completes)
│   ├── crane-identifier.html                  # frontend page
│   ├── hercules-backend-prompt.md             # paste-into-Hercules deploy spec
│   └── spec_pdfs/                             # downloaded PDFs (cache)
└── state/
    ├── vision_progress.json                   # Phase 2 resume state
    ├── upload_progress.json                   # Phase 3 resume state
    ├── training_state.json                    # Phase 4 model + version
    └── cron.log                               # active learning runs
```

## Cost ledger (this project)

| Item | One-time | Recurring |
|---|---|---|
| Vision re-annotation (Phase 2) | $19 | — |
| Roboflow Public plan | $0 | $0/mo (within $60/mo free credit) |
| Roboflow Hosted Training (v1+v2) | ~credit used | per retrain (~$0-10 each within free credits) |
| Roboflow Hosted Inference | — | $0.0024/call (~$3-10/mo at marketplace volume) |
| Cloudflare Worker | $0 | $0 (within free tier) |
| Anthropic Vision (active learning re-annotation, optional) | — | ~$0-5/mo |
| **TOTAL** | **~$19** | **~$5-15/mo** |

vs Nyckel Starter at $149/mo → **net savings ~$130/mo**.
