#!/usr/bin/env python3
"""
Phase 2.1 — Build the raw label table from two sources, ready for Vision
re-verification.

Sources:
  - ~/.gst-ingest-state.json (Photos Library, Sonnet-tagged, noisy)
  - ~/projects/crane-rental-directory/data/manifest/*.json (manufacturer/dealer-tagged, clean)

Output:
  outputs/raw_labels.csv  (image_path, brand, model, source, needs_vision)

Where:
  - source='manifest' rows are clean, needs_vision=False
  - source='photos' rows go to Vision re-verification (needs_vision=True)
  - Long-tail models (<30 samples after pooling) get model=None, kept as brand-only

The 38-model class list is computed from the pooled distribution, not hard-coded,
so it stays accurate if the corpus shifts.
"""

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

MANIFEST_DIR = Path.home() / "projects/crane-rental-directory/data/manifest"
INGEST_STATE = Path.home() / ".gst-ingest-state.json"
PHOTOS_ROOT = Path.home() / "Pictures/Photos Library.photoslibrary/originals"
OUT_DIR = Path(__file__).parent.parent / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_PER_CLASS = 30  # Roboflow training threshold from PLAN.md


def canon_brand(b):
    """Map free-form brand string → canonical class."""
    if not b:
        return None
    x = b.lower()
    if "liebherr" in x:
        return "Liebherr"
    if "tadano" in x or "faun" in x:
        return "Tadano"
    if "grove" in x:
        return "Grove"
    if "demag" in x or "terex" in x:
        return "Terex-Demag"
    if "sany" in x:
        return "Other"  # Tail — too few samples for own class
    if "kobelco" in x or "manitowoc" in x or "krupp" in x or "kato" in x or "sennebogen" in x or "xcmg" in x:
        return "Other"
    return None


def normalize_model(model: str | None) -> str | None:
    """Collapse whitespace/case variants. 'GMK 5150L' === 'GMK5150L'."""
    if not model:
        return None
    m = model.strip().upper()
    if not m or m == "UNKNOWN":
        return None
    # Compact internal whitespace for the discriminator part
    # "GMK 5150L" → "GMK 5150L" stays (single space)
    m = re.sub(r"\s+", " ", m)
    return m


def brand_from_model(m):
    """Infer brand from model prefix when brand tag is missing/wrong."""
    if not m:
        return None
    M = m.upper()
    if re.match(r"^LT[MRCFGR]", M) or re.match(r"^L[GR]\s", M) or M.startswith("LG "):
        return "Liebherr"
    if re.match(r"^ATF", M) or re.match(r"^GR ", M) or re.match(r"^AR ", M):
        return "Tadano"
    if re.match(r"^GMK", M) or re.match(r"^RT ", M):
        return "Grove"
    if re.match(r"^AC\s*\d", M) or re.match(r"^CC\s*\d", M) or re.match(r"^TC\s*\d", M):
        return "Terex-Demag"
    return None


def file_hash(path):
    """Same hash scheme used by gst-ingest to key by file path."""
    return hashlib.sha256(str(path).encode()).hexdigest()[:24]


def load_manifest():
    """All manifest URLs with their human-tagged brand+model."""
    rows = []
    for f in ["liebherr", "tadano", "grove", "terex-demag", "hadel", "kranliste"]:
        path = MANIFEST_DIR / f"{f}.json"
        if not path.exists():
            continue
        for entry in json.loads(path.read_text()):
            m = normalize_model(entry.get("model"))
            if not m:
                continue
            b = canon_brand(entry.get("brand_canonical") or entry.get("brand")) or brand_from_model(m)
            if not b:
                continue
            urls = entry.get("image_urls") or ([entry["image_url"]] if entry.get("image_url") else [])
            for u in urls:
                if not isinstance(u, str):
                    continue
                rows.append({
                    "image_path": u,
                    "brand": b,
                    "model": m,
                    "source": "manifest",
                    "needs_vision": False,
                })
    return rows


def load_photos_library():
    """Photos Library cranes from ingest state, joined to filesystem paths."""
    if not INGEST_STATE.exists():
        print(f"[!] No ingest state at {INGEST_STATE}", file=sys.stderr)
        return []
    state = json.loads(INGEST_STATE.read_text())

    # Walk Photos Library and build {hash: path} map
    valid_ext = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
    hashmap = {}
    print(f"[*] Walking {PHOTOS_ROOT}...", file=sys.stderr)
    for p in PHOTOS_ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in valid_ext:
            hashmap[file_hash(p)] = p
    print(f"[*] Indexed {len(hashmap)} Photos Library files", file=sys.stderr)

    rows = []
    missing = 0
    for h, rec in state["processed"].items():
        if rec.get("result") != "crane":
            continue
        path = hashmap.get(h)
        if not path:
            missing += 1
            continue
        b = canon_brand(rec.get("brand"))
        m = normalize_model(rec.get("model"))
        if not b:
            b = brand_from_model(m) if m else None
        if not b:
            continue
        rows.append({
            "image_path": str(path),
            "brand": b,
            "model": m,
            "source": "photos",
            "needs_vision": True,  # All Photos Library rows need Vision re-verification
        })
    print(f"[*] Photos Library: {len(rows)} resolved, {missing} hash-missing", file=sys.stderr)
    return rows


def main():
    manifest = load_manifest()
    photos = load_photos_library()
    rows = manifest + photos

    # Show distribution
    by_brand_model = Counter((r["brand"], r["model"]) for r in rows if r["model"])
    by_brand = Counter(r["brand"] for r in rows)
    classes_gte_min = sum(1 for c in by_brand_model.values() if c >= MIN_PER_CLASS)

    print(f"\n=== Raw label distribution ===")
    print(f"Total rows: {len(rows)}  (manifest: {len(manifest)}, photos: {len(photos)})")
    print(f"By brand:")
    for b, c in by_brand.most_common():
        print(f"  {b:<15} {c}")
    print(f"\nUnique brand+model pairs: {len(by_brand_model)}")
    print(f"Classes with ≥{MIN_PER_CLASS} samples: {classes_gte_min}")

    # Write the raw labels CSV
    import csv
    out_path = OUT_DIR / "raw_labels.csv"
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image_path", "brand", "model", "source", "needs_vision"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n[*] Wrote {len(rows)} rows to {out_path}")

    # Identify the 38-class target list for Phase 2 filtering
    target_classes = sorted(
        [(b, m) for (b, m), c in by_brand_model.items() if c >= MIN_PER_CLASS],
        key=lambda x: -by_brand_model[x],
    )
    print(f"\n=== Target classes for Vision re-verification ({len(target_classes)}) ===")
    target_out = OUT_DIR / "target_classes.json"
    with target_out.open("w") as f:
        json.dump([{"brand": b, "model": m, "raw_count": by_brand_model[(b, m)]} for b, m in target_classes], f, indent=2)
    print(f"[*] Wrote target classes to {target_out}")
    for b, m in target_classes[:15]:
        print(f"  {by_brand_model[(b, m)]:>4}  {b} {m}")
    print(f"  ... ({len(target_classes) - 15} more)")


if __name__ == "__main__":
    main()
