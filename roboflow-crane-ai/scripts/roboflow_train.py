#!/usr/bin/env python3
"""
Phase 4 — Generate a dataset version in Roboflow + trigger Hosted Training.

Workflow:
1. Project must already exist with uploaded images (Phase 3).
2. Generate a new version with the augmentation settings from PLAN.md.
3. Start training (Roboflow 3.0 Classification — Accurate).
4. Poll for completion (this can take 30-120 minutes).
5. Read metrics; if mAP < 0.75 → stop, report. If ≥0.75 → continue to Phase 5.

Required env: ROBOFLOW_API_KEY
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "state/training_state.json"
STATE.parent.mkdir(parents=True, exist_ok=True)
METRICS_OUT = ROOT / "outputs/training_metrics.json"

WORKSPACE = "gokmens-workspace"
PROJECT = "crane-recognition-v1-tl531"

# Augmentation/preprocess settings per PLAN.md
GENERATION_SETTINGS = {
    "preprocessing": {
        "auto-orient": True,
        "resize": {"width": 640, "height": 640, "format": "Fit (white edges) in"},
    },
    "augmentation": {
        # Horizontal flip ON (cranes don't have left/right asymmetry meaningful for ID)
        # Vertical flip OFF (cranes are gravity-oriented)
        "flip": {"horizontal": True, "vertical": False},
        # Brightness ±20%
        "brightness": {"brighten": True, "darken": True, "percent": 20},
        # Rotation ±15°
        "rotate": {"degrees": 15},
        # Blur 0-2 pixels
        "blur": {"pixels": 2},
        # 3 augmented copies per source image
        "outputs_per_training_example": 3,
    },
}


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


def main():
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        env = (Path.home() / "gst-cranes/.env").read_text()
        for line in env.splitlines():
            if line.startswith("ROBOFLOW_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
                break

    from roboflow import Roboflow

    rf = Roboflow(api_key=key)
    workspace = rf.workspace(WORKSPACE)
    project = workspace.project(PROJECT)
    print(f"[*] Project: {WORKSPACE}/{PROJECT}")

    state = load_state()
    version_num = state.get("version")

    if not version_num:
        print(f"[*] Generating dataset version with settings:")
        print(f"    preprocess: resize 640x640 fit")
        print(f"    augment: hflip + brightness±20% + rotate±15° + blur≤2px, 3 outputs/example")
        # The SDK's generate_version may take a few minutes
        try:
            version_num = project.generate_version(GENERATION_SETTINGS)
        except Exception as e:
            print(f"[!] generate_version error: {e}", file=sys.stderr)
            # Some Roboflow SDK versions return version directly; some need polling
            raise
        state["version"] = version_num
        save_state(state)
        print(f"[*] Generated version {version_num}")
    else:
        print(f"[*] Reusing existing version {version_num}")

    version = project.version(version_num)

    # Trigger training
    if not state.get("training_started"):
        print(f"\n[*] Starting training — Roboflow 3.0 Classification (Accurate), 100 epochs")
        # Classification requires explicit model_type; ResNet50 = balanced choice.
        # Other options (verified via API): vit-base-patch16-224-in21k,
        # resnet18/34/101, vit_base_patch16_dinov3.lvd1689m (DINOv3 Base).
        version.train(speed="accurate", model_type="resnet50")
        state["training_started"] = True
        state["training_started_at"] = time.time()
        save_state(state)
        print(f"[*] Training kicked off. Poll the Roboflow dashboard for live status:")
        print(f"    https://app.roboflow.com/{WORKSPACE}/{PROJECT}/{version_num}/train")

    # Poll for completion. Roboflow exposes metrics on the version once trained.
    print(f"\n[*] Polling for training completion (interval 60s)...")
    while True:
        try:
            v = project.version(version_num)
            model = v.model
            if model and hasattr(model, "id") and model.id:
                # Classification reports accuracy (top-1), not mAP
                metrics = {
                    "version": version_num,
                    "model_id": model.id,
                    "accuracy": getattr(model, "accuracy", None),
                    "top1": getattr(model, "top1", None),
                    "top5": getattr(model, "top5", None),
                    "mAP": getattr(model, "mAP", None),  # Roboflow sometimes uses mAP loosely
                    "precision": getattr(model, "precision", None),
                    "recall": getattr(model, "recall", None),
                }
                print(f"[*] Training complete!")
                print(f"    {metrics}")
                METRICS_OUT.write_text(json.dumps(metrics, indent=2))

                # Quality gate: prefer top-1 accuracy or mAP if either ≥0.75
                top1 = metrics.get("top1") or metrics.get("accuracy") or metrics.get("mAP")
                if top1 is not None:
                    top1_val = float(top1) / (100.0 if float(top1) > 1.0 else 1.0)  # handle 0-1 or 0-100
                    state["top1"] = top1_val
                    state["training_complete"] = True
                    save_state(state)
                    if top1_val < 0.75:
                        print(f"\n[!] top-1 accuracy {top1_val:.3f} < 0.75 gate. STOPPING.")
                        sys.exit(3)
                    print(f"\n[*] top-1 accuracy {top1_val:.3f} ≥ 0.75 gate passed. Ready for Phase 5.")
                    break
                else:
                    print(f"[!] No top1/accuracy/mAP field — check dashboard URL above")
                    break
        except Exception as e:
            print(f"[!] poll error: {e}", file=sys.stderr)
        time.sleep(60)


if __name__ == "__main__":
    main()
