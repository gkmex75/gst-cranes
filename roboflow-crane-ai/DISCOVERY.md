# Roboflow Crane AI — Phase 0 Discovery

Date: 2026-05-11
Author: Claude Code (autonomous discovery)

## TL;DR

The premise in the user's prompt — "11,500 crane images at `~/gst-cranes/`" — is **partially wrong**. `~/gst-cranes/` is the GST social-media automation project (LinkedIn/Meta ads, content generation) and contains only ~97 images.

The actual crane image corpus lives in two locations:

1. **Photos Library** — 10,820 crane photos labelled in `~/.gst-ingest-state.json` (originals at `~/Pictures/Photos Library.photoslibrary/originals/`). Labels were produced by Claude Sonnet during the icloud-crane-ingest pass.
2. **Manifest scrape** — 5,403 URLs at `~/projects/crane-rental-directory/data/manifest/{liebherr,tadano,grove,terex-demag,hadel,kranliste}.json`. These are human-tagged (manufacturer press shots + dealer/forum metadata).

Net usable corpus: ~16,000 images (Photos Library + manifest URLs, with some overlap). The prompt's "11,500" likely refers to the subset previously uploaded to Nyckel during prior sessions.

## What's at `~/gst-cranes/`

```
~/gst-cranes/
├── .env                    # Adobe, fal.ai, Meta, LinkedIn keys; NO Roboflow, NO Anthropic
├── linkedin-ads.py
├── mail-blast.py
├── scripts/
│   └── icerik-uretici.py   # Content generator (uses fal.ai, not vision ML)
├── yeni-vinc/              # 8 photos in 6 brand-model folders (template inputs)
├── processed/              # 20 photos, processed for posting
├── output/                 # 22 generated outputs
├── sablonlar/              # 3 templates
└── logs/screenshots/       # 42 misc screenshots
```

Total images: **97**, organised in brand-model folder structure but tiny scale. Suitable as test fixtures, not training data.

## Where the real corpus is

### Photos Library (10,820 cranes)

`~/.gst-ingest-state.json` stores per-photo metadata from prior Sonnet vision ingest:

- Total processed entries with `result == 'crane'`: **10,820**
- Unique brand+model labels: **1,212**
- Brand distribution:
  - Liebherr 6,214 (57%)
  - Tadano 2,791 (26%)
  - Grove 750 (7%)
  - Terex-Demag 566 (5%)
  - Sany/Kobelco/Manitowoc/Krupp/Kato/Sennebogen/XCMG (tail): ~233
  - "Other"/unlabelled: 266

Photo files are present at the path hashes recorded in state. Walk of Photos Library originals returns 30,427 total image files; the crane subset is referenced by hash.

### Manifest scrape (5,403 URLs)

Cleaner data — human-tagged, manufacturer/dealer press photos:

| Source | Entries | URLs | Unique models |
|---|---|---|---|
| hadel.de | 174 | 4,062 | 167 |
| kranliste.dk | 103 | 1,043 | 103 |
| liebherr.com | 56 | 181 | 56 |
| tadano.com | 22 | 45 | 22 |
| grove.com | 19 | 37 | 19 |
| terex-demag.com | 10 | 35 | 10 |
| **Total** | **384** | **5,403** | **377** |

## Class distribution from Photos Library labels

**38 brand+model classes have ≥30 samples** (Roboflow training threshold from prompt):

```
1109  Liebherr LTM 1500-8.1        184  ...
 584  Tadano ATF 220G-5             86  Liebherr LR 1600/2
 391  Liebherr LTM 1100-5.2         85  Liebherr LR 1750
 311  Liebherr LTM 1130-5.1         79  Grove GMK 5130-2
 251  Liebherr LTM 1100-4.2         76  Liebherr LTM 1060-3.1
 217  Liebherr LTM 1300-6.2         ...
 173  Liebherr LTM 1750-9.1         32  Liebherr LTM 1400-7.1
 167  Liebherr LTM 1200-5.1         31  Tadano CC 2800
 128  Tadano AC 500-2 *             31  Grove GMK5150L *
 104  Terex-Demag AC 500-2 *        ...
 103  Liebherr LR 1300              [38 total ≥30]
```

(* = label noise — see below)

**1,174 long-tail models** (<30 samples each, ~2,915 photos total) — must be consolidated to brand-only labels or dropped.

## Label noise problems (critical for Roboflow)

The Photos Library labels were produced by Sonnet during ingest, before the decal guard was added. They contain systematic errors:

1. **Wrong brand attribution.** Demag AC 500-2 is labelled as Liebherr (66), Tadano (128), AND Terex-Demag (104) for the SAME crane model. Tadano LTM 1500-8.1 is impossible (LTM is Liebherr only) but appears in the labels.
2. **Whitespace/case variants.** "GMK 5150L" (52) and "GMK5150L" (31) — same model, two classes.
3. **Series-vs-variant confusion.** "Tadano CC 2800-1" (40), "Tadano CC 2800" (31) — could be same crane, different label conventions.
4. **Brand acquisition lineage.** Faun → Tadano-Faun → Tadano (and later Demag → Terex-Demag → Tadano) creates label drift over photo dates.

Estimate: ~10-15% of Photos Library labels are wrong at brand level. This is exactly the corpus poisoning issue we hit with Nyckel. **Feeding raw to Roboflow would replicate the same problem.**

The manifest URLs do not have this problem — they're human-tagged at source. ~5,400 URLs of higher-quality data is available.

## What this means for the plan

1. The annotation strategy must include **label cleanup** as the dominant cost. Folder structure / filename regex doesn't apply (Photos Library doesn't have those). Sonnet auto-labels are noisy and need re-verification.
2. We have a clean **manifest subset** (~5,400) that can be the gold-standard training core, augmented with verified Photos Library samples.
3. Class threshold (≥30 samples) gives 38 trainable model classes. Below that, fall back to brand-only.
4. The 4 major brands together cover 95% of the corpus. Sany/Kobelco/Manitowoc/etc. should map to "Other" bucket, not their own class (too few samples).

## Environment

- Python 3.12 venv at `.venv/`, deps: playwright, Pillow, opencv-python, dotenv, requests, rich, click
- **Missing:** `roboflow`, `anthropic` Python SDKs
- **Missing keys:** `ROBOFLOW_API_KEY`, `ANTHROPIC_API_KEY` not in `.env`
- Cloudflare wrangler is set up in `~/projects/crane-rental-directory/wrangler.toml` (for the directory app) — would re-use for inference worker

## Prior attempts

- **Nyckel** (this session and previous): 8,692 sample classifier across 50 labels in `function_sznhw9spfwhdajaf`. Brand accuracy ~50-70%, model-level autofill ~30%. Documented in `~/.claude/projects/-Users-gokmentanacar/memory/session_handoff_2026-05-11-nyckel-rebalance-final.md`.
- **Claude Sonnet 4.6 Vision** (already in `crane-rental-directory`): OCR-driven brand/model extraction with decal-evidence guard. Hallucination eliminated. Used as fallback when Nyckel low-confidence.
- **CLIP ViT-L/14 image RAG** (Cloudflare Vectorize `crane-image-embeddings-clip-768`): visual-feature nearest-neighbour index for 12,137 vectors. Currently a cross-check signal.
- **DINOv2**: attempted, abandoned (not on Replicate publicly), pivoted to CLIP.
- **Gemini Vision**: tested briefly this session, user rejected.

No prior Roboflow attempt.

## Hercules.app

The user's prompt references "Hercules.app" as the way gstcranes.com endpoints get deployed. Not yet seen first-hand in this discovery — needs spec from user. Backend deploy assumed to be via a copy-paste prompt format (mentioned in user prompt as `outputs/hercules-backend-prompt.md`).

For the directory app (`map.gstcranes.com`), the deploy target is Cloudflare Pages + Workers. That's a different surface from `gstcranes.com` (Hercules-deployed). The crane-identifier page lives on `gstcranes.com/tools/crane-identifier` per the user's prompt.

## Open items requiring user input

1. **ROBOFLOW_API_KEY** — required before Phase 3 (upload)
2. **ANTHROPIC_API_KEY** — required for Phase 2 (Vision label re-verification on the messy Photos Library subset). The `claude-rental-directory` project has one in its CF secrets but not exposed locally; user should provide directly or point to existing keychain.
3. **Hercules.app backend deploy format** — user knows the workflow; will accept the copy-paste prompt as deliverable, but it'd help to see one prior Hercules deploy as reference.

## Cost estimate (preview — full numbers in PLAN.md)

- **Roboflow Starter plan**: $21/mo (or $250/year). Needed for private classification project >1K images. Free tier caps at 10K total images. Within < $50 monthly trigger.
- **Claude Vision re-annotation** (Phase 2): conservatively ~5,000 Photos Library samples need re-verification at ~$0.003 per image (Sonnet vision) = ~$15 one-time. Within trigger.
- **Roboflow Hosted Training**: 1 hour free/month on Starter plan, additional hours $5 each. Estimate 1-2 hours for 38-class classification — likely free or $5-10.
- **Cloudflare Worker + Roboflow Hosted Inference**: zero infra cost. Roboflow inference billed at $0.0024 per call after free tier; assuming 1K uploads/month, ~$2.40/mo.

**Total month-1 cost: ~$40-60 one-time + $25/mo recurring.** Within the "<$50 trigger" cutoff for one-time and the Roboflow recurring is the only ongoing.

Compared to Nyckel ($149/mo Starter), Roboflow is ~6x cheaper monthly. Even if Roboflow's accuracy is just on par with Nyckel, the cost reduction alone is value. If Roboflow's accuracy is meaningfully better (which is the user's hypothesis), it's a clear win.

**Decision option**: cancel Nyckel Starter after Roboflow ships — saves $149/mo.

## Files to be produced (autonomous)

1. `scripts/extract_labels.py` — pull existing labels from `~/.gst-ingest-state.json` + manifest JSON, normalise to canonical brand+model, write `outputs/annotations.csv`
2. `scripts/clean_labels.py` — detect inconsistencies, batch re-verify with Vision, write cleaned labels
3. `scripts/roboflow_upload.py` — resumable batch upload with state file
4. `scripts/inference_server.py` — FastAPI inference endpoint (deploys to Cloudflare Worker)
5. `scripts/active_learning_weekly.py` — cron for weekly review queue + monthly retrain
6. `outputs/crane-identifier.html` — frontend page
7. `outputs/hercules-backend-prompt.md` — copy-paste deploy prompt for the user
8. `outputs/training_metrics.json` — post-train evaluation
9. `outputs/dashboard.html` — operations dashboard
10. `README.md` + `RUNBOOK.md` — user-runnable docs

## Next: Phase 1 PLAN

See `PLAN.md`. Stops at user approval before Phase 2 (annotation execution).
