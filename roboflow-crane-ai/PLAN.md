# Roboflow Crane AI — Phase 1 Execution Plan

Date: 2026-05-11
Status: **AWAITING USER APPROVAL** before proceeding to Phase 2.

## Goal

Build a fine-grained crane recognition system: user uploads crane photo to `gstcranes.com/tools/crane-identifier` → API returns brand + model + confidence. System self-improves via active learning.

## Class structure decision

Photos Library labels yield **38 brand+model classes with ≥30 samples** (training threshold). Below that, 1,174 long-tail models would dilute training.

Strategy:

- **Tier 1: 38 model classes** (≥30 samples). Top-1 trainable target.
- **Tier 2: 4 brand-only fallback classes** (Liebherr, Tadano, Grove, Terex-Demag) for photos whose specific model can't be reliably tagged.
- **"Other"** class for non-major brands (Sany/Kobelco/Manitowoc/etc., ~233 samples consolidated).

Total: **38 + 4 + 1 = 43 classes**.

Optionally we could collapse very-similar models (e.g., LTM 1090-4.1 and LTM 1090-4.2 → LTM 1090) to boost per-class sample count. Decision deferred to Phase 2 after re-annotation pass reveals real class counts.

## Annotation strategy (Phase 2)

The Photos Library labels are noisy (~10-15% wrong brand at minimum). The manifest URLs are clean. Approach:

1. **Folder/filename pre-pass** (`scripts/extract_labels.py`): does not apply — Photos Library is hash-named, not folder-organised. We rely on `~/.gst-ingest-state.json` instead.
2. **Manifest pass**: import 5,403 manifest URLs with their human-tagged brand+model directly. No re-verification needed. These become the high-confidence training core.
3. **Photos Library cleanup pass**: load `~/.gst-ingest-state.json`, normalise brand strings, drop labels where model isn't in our 38-class target. For the surviving ~7,500-8,000 samples, run a Claude Sonnet 4.6 Vision re-verification batch.

   Vision re-verification approach:
   - Batch 5 photos per call (saves tokens, Sonnet handles this fine).
   - Prompt: "For each image, return BRAND (one of: Liebherr/Tadano/Grove/Terex-Demag/Other) and MODEL if visible on a decal. Confidence 0-1. Return ONLY where decal text supports the brand."
   - Output: `{"brand": "...", "model": "..."|null, "confidence": 0.0-1.0, "decal_text": "..."}`
   - Confidence ≥ 0.7 AND decal_text contains brand → keep label.
   - Confidence < 0.7 → flag `needs_review`, exclude from training (later → active learning queue).
   - Disagreement with existing label → keep Vision's call (Vision sees the decal now, with our hardened prompt).

4. **Class consolidation**: after re-verification, any class with <30 verified samples is folded into its brand-only label.

5. **Auto QC**: 50 random samples re-verified a second time. If <90% agreement, tune prompt + retry batch. Log decisions, no user intervention.

Output: `outputs/annotations.csv` (image_path, brand, model, confidence, source). Image paths are local filesystem paths to Photos Library originals OR URLs from manifest.

## Phase 2 cost (Vision re-verification)

- Photos to re-verify: ~7,500 (drop the obvious wrong-brand outliers first, ~3,000 less)
- Sonnet 4.6 Vision pricing: $3/M input + $15/M output. At 5 photos/batch (~3K input tokens per batch, ~150 output), each batch ~$0.011. 1,500 batches ≈ **$17**.
- One-shot, under $50 trigger. No approval needed.

## Train/val/test split

Roboflow default 70/20/10. Stratified by class to keep tiny classes represented in val/test. Generation handled by Roboflow during dataset creation.

## Phase 3 (Roboflow upload)

- Roboflow SDK, project type = Classification, single-label
- 100-image batches, retry with exp-backoff on 5xx
- State file at `state/upload_progress.json` for crash-resume
- Annotations attached during upload (Roboflow Single-Label classification: one tag per image)
- Tags = our normalised `brand_model` string (e.g., `liebherr_ltm_1500-8_1`)

Estimate: 11K images × ~50KB each × 100-image batches with rate-limit pace ≈ 2-4 hours sustained upload. Resumable.

## Phase 4 (Training)

Roboflow Hosted Training:
- Model: **Roboflow 3.0 Classification (Accurate)**
- Epochs: 100
- Augmentations: horizontal flip, ±15° rotation, brightness ±20%, blur 0-2.0px, mosaic. (NO vertical flip — cranes are gravity-oriented. NO heavy crop — we want full-machine signal.)
- Cost: 1 free hour included in Starter; additional $5/hr. Estimate 1-2 hours for 43-class on 11K images.

**Gate at training completion**:
- If **mAP < 0.75**: log problematic classes, write `outputs/training_metrics.json`, **STOP** and report. (User decides next step.)
- If **mAP ≥ 0.75**: continue to Phase 5.

We have no a priori guarantee mAP will hit 0.75 — that's the question this whole project answers. The user's hypothesis (Nyckel's failure was tool choice, not fundamental limit) is what we're testing. Phase 4's metric is the answer.

## Phase 5 (Inference API)

`scripts/inference_server.py` is a thin FastAPI that wraps Roboflow Hosted Inference (no GPU on our side).

```python
@app.post("/api/identify-crane")
async def identify(file: UploadFile):
    result = rf.workspace().project(PROJECT_ID).version(VERSION).model.predict(
        await file.read(), confidence=40, overlap=30
    ).json()
    top3 = sorted(result["predictions"], key=lambda x: -x["confidence"])[:3]
    return {
        "predictions": top3,
        "needs_review": top3[0]["confidence"] < 0.7,
        "model_version": "v1"
    }
```

Deployment: **Cloudflare Worker** that proxies to Roboflow Hosted Inference. No FastAPI server — Worker handles the HTTP + auth. The Python file is local-dev reference; Worker is the production deploy. Wrangler config at `roboflow-crane-ai/worker/wrangler.toml`.

Cost: free Worker quota + Roboflow Hosted Inference at $0.0024/call after their free tier. Conservative: ~$3-10/mo at marketplace volume.

## Phase 6 (gstcranes.com integration)

**6A. Backend** — `outputs/hercules-backend-prompt.md`: copy-paste prompt for Gökmen to feed into Hercules.app, instructing it to create `gstcranes.com/api/identify` that forwards multipart uploads to the Cloudflare Worker.

**6B. Frontend** — `outputs/crane-identifier.html`: standalone HTML page with:
- Drag-drop uploader (or click-to-select)
- Loading state with spinner
- Top-3 prediction cards with confidence bars
- "Bu modeli sat/al" CTA → `gstcranes.com/?search={model}`
- Branding: neutral professional (matches gstcranes.com look, not gkmex Liebherr-yellow)
- Mobile-responsive
- Single file, inline CSS+JS, ready for Hercules paste

Companion: `outputs/hercules-frontend-prompt.md` — copy-paste Hercules instructions for the page mount.

## Phase 7 (Active learning)

`scripts/active_learning_weekly.py`:
1. Query Hercules backend for last 7 days of uploads where `needs_review=true`
2. Copy those photos to `outputs/review_queue/<week>/`
3. Email Gökmen with the count + a link to a simple HTML reviewer (one screen, brand+model dropdown per photo, save to CSV)
4. Once reviewed, batch-upload to Roboflow as a new dataset version
5. Trigger Roboflow re-train monthly (1st of each month, Hosted Training)

Cron: `crontab -e` adds `0 9 * * 1 cd /Users/gokmentanacar/gst-cranes/roboflow-crane-ai && .venv/bin/python scripts/active_learning_weekly.py >> logs/active_learning.log 2>&1` (Monday 09:00 weekly).

## Required from user before Phase 2

1. `ROBOFLOW_API_KEY` — paste into `.env`. Get one at https://app.roboflow.com (Sign up + Settings → API Key).
2. `ANTHROPIC_API_KEY` — paste into `.env`. From https://console.anthropic.com (Settings → API Keys).
3. Roboflow Starter plan signup: $21/mo or $250/year — needed for 11K private images. (Free tier caps at 10K.)

These can come now or after PLAN approval; Phase 2 doesn't fire until they're in place.

## Cost summary

| Item | When | Amount |
|---|---|---|
| Roboflow Starter | recurring | $21/mo ($250/yr if annual) |
| Anthropic Vision (Phase 2 re-annotation) | one-time | ~$17 |
| Roboflow Hosted Training (Phase 4) | one-time + monthly retrain | $0-10 each |
| Roboflow Hosted Inference (production) | per call | $0.0024/call (~$3-10/mo) |

**Month 1: ~$50-60 total.** Recurring: ~$25-35/mo.
**Nyckel cancellation savings: $149/mo** (do this after Roboflow ships).
**Net change vs status quo: -$110/mo** (we save money by switching).

## Time estimate

| Phase | Hours |
|---|---|
| 2 — Annotation | 6-10 (mostly Vision API wait time + 1-2 active engineering hours) |
| 3 — Upload | 2-4 (sustained upload, can run overnight) |
| 4 — Training | 1-2 (Roboflow hosted, no local supervision) |
| 5 — Inference deploy | 1-2 |
| 6 — Site integration | 2-3 |
| 7 — Active learning | 1 |
| **Total** | **13-22 hours** wall-clock, of which ~5-8 hours active engineering. Most is waiting (uploads, training). |

## Risks (no surprises in mid-execution)

1. **Phase 4 mAP < 0.75**: classifier can't discriminate models on this corpus. Same fundamental issue we hit with Nyckel. STOP and report. (Probability: medium. The corpus quality is the constraint, not the tool, and our re-annotation pass helps but doesn't eliminate the issue.)
2. **Photos Library files don't resolve from state hashes**: walk-and-hash returns 30K files, but if Photos Library was restructured since the state was created, hashes mismatch and we lose those samples. Workaround: use manifest URLs only (5K), but smaller training set.
3. **Roboflow API rate limits during upload**: handled by 100-image batches + retry-on-429 + resumable state.
4. **Hercules deploy workflow opaque**: prompt files will be written but the user's confirmation that Hercules accepts them as expected only comes during Phase 6 site test.

## Stop gates

- **HERE (after PLAN)**: user must say "PLAN OK, devam" before Phase 2 fires.
- **Phase 4 (training)**: if mAP < 0.75 STOP.
- **Phase 6 (site mounting)**: copy-paste prompts for Hercules; user runs the actual deploy.
- **Any single-action cost ≥ $50**: STOP and ask.

Everything else: autonomous.

---

## Decision summary for user

You're being asked to approve:

1. **Class structure**: 38 model + 4 brand + 1 other = 43 classes. Long-tail <30-sample models consolidate to brand-only.
2. **Annotation re-verification of ~7,500 Photos Library photos via Claude Vision** — one-time ~$17.
3. **Roboflow Starter plan signup at $21/mo (or $250/yr).**
4. **Phase 4 gate**: STOP if mAP < 0.75, you decide next step.
5. **Nyckel cancellation** is recommended once Roboflow ships (saves $149/mo, net cost decrease of ~$110/mo vs current state).

Reply with **"PLAN OK, devam"** to proceed. If you want changes (different class threshold, different model architecture, different cost profile), say so now.
