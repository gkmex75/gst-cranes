#!/usr/bin/env python3
"""
Phase 3 — Upload cleaned/verified labels to Roboflow as a classification dataset.

Input: outputs/cleaned_labels.csv (image_path, brand, model, confidence, source)
   image_path can be:
     - Local filesystem path (Photos Library)
     - HTTP/HTTPS URL (manifest)

Output: Roboflow project with images tagged by brand_model class.

Strategy:
  - Single-label classification, one tag per image
  - Class string: f"{brand}_{model}" lowercased + slugified (e.g., "liebherr_ltm_1500-8_1")
  - For long-tail (≥30 sample threshold not met after re-verification), use brand-only class
  - HTTP URLs are fetched once, downscaled, then uploaded as bytes
  - 100-image batches, resumable via state/upload_progress.json
  - Confidence < 0.5 entries are dropped (not trusted for training)

Roboflow plan: Public (free).

Required env: ROBOFLOW_API_KEY
"""

import csv
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from PIL import Image
import io

ROOT = Path(__file__).parent.parent
CLEAN_CSV = ROOT / "outputs/cleaned_labels.csv"
STATE_FILE = ROOT / "state/upload_progress.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

MIN_PER_CLASS = 30  # ≥30 → model class; <30 → brand-only fallback
MAX_DIM = 1024  # Roboflow handles resize but we save bandwidth
CONFIDENCE_FLOOR = 0.45  # Drop low-confidence labels before training

# These config values are determined by the script run (project + version),
# written to state on first successful creation.
WORKSPACE = os.environ.get("ROBOFLOW_WORKSPACE", "gokmens-workspace")
PROJECT_NAME = "crane-recognition-v1"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"uploaded": {}, "project_id": None, "stats": {}}


def save_state(s):
    STATE_FILE.write_text(json.dumps(s))


def slugify_class(brand: str, model: str | None) -> str:
    parts = [brand]
    if model:
        parts.append(model)
    s = " ".join(parts).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def fetch_image_bytes(path_or_url: str) -> bytes | None:
    """Get image bytes from local path OR remote URL. Downscale to MAX_DIM."""
    try:
        if path_or_url.startswith("http"):
            r = requests.get(
                path_or_url,
                headers={
                    "User-Agent": "GST-Cranes-Indexer/1.0 (+https://map.gstcranes.com)",
                    "Accept": "image/jpeg,image/png,image/webp,image/*",
                },
                timeout=20,
            )
            if not r.ok:
                return None
            raw = r.content
        else:
            p = Path(path_or_url)
            if not p.exists():
                return None
            raw = p.read_bytes()
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception as e:
        print(f"[!] fetch failed {path_or_url}: {e}", file=sys.stderr)
        return None


def compute_final_classes(rows: list[dict]) -> tuple[Counter, dict]:
    """Determine per-row final class label.

    - If brand+model combo has ≥MIN_PER_CLASS rows → "brand_model" class
    - Otherwise → "brand" only

    Returns (class_counts, row_to_class).
    """
    by_bm = Counter()
    for r in rows:
        if r["model"] and r["confidence"] >= CONFIDENCE_FLOOR:
            by_bm[(r["brand"], r["model"])] += 1

    row_class = {}
    for r in rows:
        if r["confidence"] < CONFIDENCE_FLOOR:
            row_class[r["image_path"]] = None  # drop
            continue
        if r["model"] and by_bm[(r["brand"], r["model"])] >= MIN_PER_CLASS:
            row_class[r["image_path"]] = slugify_class(r["brand"], r["model"])
        else:
            row_class[r["image_path"]] = slugify_class(r["brand"], None)
    final = Counter(c for c in row_class.values() if c)
    return final, row_class


def get_or_create_project(rf, project_id: str | None):
    """Find existing project by name or create one."""
    from roboflow import Roboflow  # lazy import for tests
    workspace = rf.workspace(WORKSPACE)
    try:
        # Try fetching existing
        if project_id:
            return workspace.project(project_id)
        # Look through workspace projects
        projects = workspace.projects()
        for p in projects:
            if p.endswith(PROJECT_NAME) or p == PROJECT_NAME:
                print(f"[*] Found existing project: {p}")
                return workspace.project(p.split("/")[-1])
    except Exception as e:
        print(f"[!] project lookup: {e}", file=sys.stderr)
    # Create new
    print(f"[*] Creating new project '{PROJECT_NAME}' in workspace '{WORKSPACE}'")
    proj = workspace.create_project(
        project_name=PROJECT_NAME,
        project_type="single-label-classification",
        project_license="MIT",  # Public plan requirement
        annotation="brand-model",
    )
    return proj


def split_for_path(path: str) -> str:
    """Deterministic 70/20/10 train/valid/test split based on path hash.

    Roboflow's API doesn't expose post-upload split rebalancing or accept
    splits in version generation — splits must be set at upload time.
    Using a stable hash means re-runs put each image in the same split.
    """
    import hashlib
    h = int(hashlib.md5(path.encode()).hexdigest()[:8], 16) % 10
    if h < 7:
        return "train"
    if h < 9:
        return "valid"
    return "test"


def upload_image(project, image_bytes: bytes, image_name: str, class_label: str, split: str = "train") -> bool:
    """Upload single image with classification class + split assignment."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        project.upload(
            image_path=tmp_path,
            annotation_path=class_label,
            split=split,
            batch_name="bulk-upload-v3-split",
            num_retry_uploads=2,
        )
        return True
    except Exception as e:
        print(f"[!] upload {image_name}: {e}", file=sys.stderr)
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def main():
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        env = (Path.home() / "gst-cranes/.env").read_text()
        for line in env.splitlines():
            if line.startswith("ROBOFLOW_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
                break
    if not key:
        print("[!] ROBOFLOW_API_KEY required", file=sys.stderr)
        sys.exit(1)

    if not CLEAN_CSV.exists():
        print(f"[!] {CLEAN_CSV} not found. Run clean_labels.py first.", file=sys.stderr)
        sys.exit(2)

    # Read and dedupe by image_path (manifest URLs can appear multiple times)
    rows_by_path = {}
    with CLEAN_CSV.open() as f:
        for r in csv.DictReader(f):
            r["confidence"] = float(r["confidence"]) if r["confidence"] else 0.0
            if r["model"] == "":
                r["model"] = None
            if r["image_path"] not in rows_by_path:
                rows_by_path[r["image_path"]] = r
    rows = list(rows_by_path.values())
    print(f"[*] {len(rows)} unique rows loaded from {CLEAN_CSV.name}")

    counts, row_class = compute_final_classes(rows)
    rows_with_class = [(r, row_class[r["image_path"]]) for r in rows if row_class[r["image_path"]]]
    print(f"[*] {len(rows_with_class)} rows pass confidence floor ({CONFIDENCE_FLOOR})")
    print(f"[*] {len(counts)} final classes")
    print("    Top 20:")
    for cls, n in counts.most_common(20):
        print(f"      {n:>5}  {cls}")

    # Roboflow SDK setup
    from roboflow import Roboflow
    rf = Roboflow(api_key=key)

    state = load_state()
    project = get_or_create_project(rf, state.get("project_id"))
    if not state.get("project_id"):
        state["project_id"] = project.id if hasattr(project, "id") else PROJECT_NAME
        save_state(state)

    print(f"\n[*] Uploading to Roboflow project: {state['project_id']}")
    print(f"[*] Already uploaded: {len(state['uploaded'])}")

    todo = [(r, c) for r, c in rows_with_class if r["image_path"] not in state["uploaded"]]
    print(f"[*] Remaining: {len(todo)}")

    start = time.time()
    ok = 0
    err = 0
    for i, (row, cls) in enumerate(todo):
        img = fetch_image_bytes(row["image_path"])
        if not img:
            state["uploaded"][row["image_path"]] = {"skip": True, "reason": "fetch_failed"}
            err += 1
            continue
        name = Path(row["image_path"]).name if not row["image_path"].startswith("http") else f"manifest_{abs(hash(row['image_path']))}.jpg"
        split = split_for_path(row["image_path"])
        success = upload_image(project, img, name, cls, split=split)
        if success:
            state["uploaded"][row["image_path"]] = {"class": cls, "ok": True}
            ok += 1
        else:
            state["uploaded"][row["image_path"]] = {"skip": True, "reason": "upload_failed"}
            err += 1

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            eta_s = (len(todo) - i - 1) / rate if rate else 0
            print(f"   [{i+1}/{len(todo)}] ok={ok} err={err}  rate={rate:.1f}/s  ETA={eta_s/60:.0f}m")
            save_state(state)

    save_state(state)
    print(f"\n[*] Done: ok={ok} err={err}")
    print(f"[*] Project URL: https://app.roboflow.com/{WORKSPACE}/{state['project_id']}")


if __name__ == "__main__":
    main()
