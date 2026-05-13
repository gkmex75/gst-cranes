#!/usr/bin/env python3
"""
Scrape metric crane specs from freecranespecs.com for our 59 trained classes.

Output: outputs/crane_specs.json — {class_slug: {brand, model, capacity_t,
axles, boom_main_m, boom_extension_m, fly_jib_m, max_lifting_height_m,
max_working_radius_m, weight_t, source_pdf}}

Strategy:
1. URL pattern: https://freecranespecs.com/{Brand}/{ModelSlug}
   where ModelSlug replaces dots/spaces with dashes.
2. The page lists multiple PDFs — prefer ones without "USA SPEC" in name
   (those are metric).
3. pdftotext to extract, regex to parse known patterns.

Usable for cascade post-processing (e.g., reject prediction if axle count
on photo doesn't match class spec) and label sanity-check.
"""

import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
import urllib.request

ROOT = Path(__file__).parent.parent
OUT = ROOT / "outputs/crane_specs.json"
PDF_CACHE = ROOT / "outputs/spec_pdfs"
PDF_CACHE.mkdir(parents=True, exist_ok=True)

# Brand → freecranespecs URL slug
BRAND_SLUG = {
    "liebherr": "Liebherr",
    "tadano": "Tadano",
    "grove": "Grove",
    "terex_demag": "Terex-Demag",
    "other": None,
}


def derive_url(brand_key: str, model: str) -> str | None:
    """Map our class slug → freecranespecs URL.

    Examples:
      liebherr + 'LTM 1130-5.1' → /Liebherr/LTM-1130-5-1
      tadano + 'ATF 220G-5'     → /Tadano/ATF-220G-5
      terex_demag + 'AC 130-5'  → /Terex-Demag/AC-130-5
    """
    brand_slug = BRAND_SLUG.get(brand_key)
    if not brand_slug:
        return None
    # Replace . and space with dash
    model_slug = re.sub(r"[\s.]+", "-", model).strip("-")
    return f"https://freecranespecs.com/{brand_slug}/{model_slug}"


def fetch_page(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GST-Crane-AI/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  fetch fail {url}: {e}", file=sys.stderr)
        return None


def extract_pdf_urls(html: str) -> list[str]:
    """Pull all cranenetwork.com PDF URLs from page, dedupe."""
    urls = re.findall(r"https://cranenetwork\.com/uploads/specs/[^'\"]+\.pdf", html)
    return list(dict.fromkeys(urls))


def pick_metric_pdf(urls: list[str]) -> str | None:
    """Prefer non-USA-SPEC PDF (the metric one). Reject obviously imperial files."""
    # Score each: lower = better (more likely metric)
    def score(u):
        u_l = u.lower()
        s = 0
        if "usa" in u_l: s += 100
        if "imperial" in u_l: s += 100
        if " usa " in u_l: s += 100
        # Prefer Liebherr-branded sales brochure-looking ones (longer hash, no model-network suffix)
        if "all_terrain" in u_l: s += 1
        return s
    sorted_urls = sorted(urls, key=score)
    return sorted_urls[0] if sorted_urls else None


def download(url: str, dest: Path) -> bool:
    try:
        urllib.request.urlretrieve(url, dest)
        return dest.stat().st_size > 1000
    except Exception as e:
        print(f"  dl fail {url}: {e}", file=sys.stderr)
        return False


def pdftotext(pdf: Path) -> str:
    try:
        r = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=30)
        return r.stdout
    except Exception:
        return ""


METRIC_RE = {
    "capacity_t": [
        r"Max\.? lifting capacity[:\s]+([\d.,]+)\s*t",
        r"max(?:imum)? capacity[:\s]+([\d.,]+)\s*t(?:onnes?)?",
        r"capacity[:\s]+([\d.,]+)\s*t\b",
    ],
    "max_lifting_height_m": [
        r"Max\.? lifting height[:\s]+([\d.,]+)\s*m",
    ],
    "max_working_radius_m": [
        r"Max\.? working radius[:\s]+([\d.,]+)\s*m",
    ],
    "boom_main_m": [
        r"(\d+)[-\s]m telescopic boom\b",
        r"telescopic boom[:\s]+(\d+(?:\.\d+)?)\s*m",
        r"main boom[:\s]+\d+(?:\.\d+)?\s*[-–]\s*(\d+(?:\.\d+)?)\s*m",
    ],
    "boom_extension_m": [
        r"(\d+)\s*m telescopic boom extension",
        r"boom extension[:\s]+(\d+(?:\.\d+)?)\s*m",
    ],
    "fly_jib_m": [
        r"(\d+)[-\s]m folding fly jib",
        r"fly jib[:\s]+(\d+(?:\.\d+)?)\s*m",
    ],
    "weight_t": [
        r"(\d+(?:\.\d+)?)[-\s]?t overall weight",
    ],
}


def parse_specs(text: str) -> dict:
    out = {}
    for key, patterns in METRIC_RE.items():
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                try:
                    v = float(m.group(1).replace(",", "."))
                    out[key] = v
                    break
                except ValueError:
                    continue
    # Extract axles from model name suffix (e.g., "LTM 1130-5.1" → 5; "ATF 220G-5" → 5)
    # Set in caller
    return out


def axles_from_model(model: str) -> int | None:
    """Liebherr LTM/LTC/LTR: -X.Y → X axles. Tadano ATF NNNG-X → X axles.
    Grove GMK NXXXX → first digit = axles. Demag AC NNN-X → X axles."""
    m = re.search(r"-(\d)\.?\d?$", model)
    if m:
        return int(m.group(1))
    m = re.search(r"^GMK\s*(\d)", model)
    if m:
        return int(m.group(1))
    return None


def load_classes() -> list[tuple[str, str, str, int]]:
    """Read trained class list with sample counts, sort by frequency."""
    import csv
    counts = Counter()
    with (ROOT / "outputs/cleaned_labels.csv").open() as f:
        for r in csv.DictReader(f):
            if r["model"] and float(r["confidence"] or 0) >= 0.45:
                counts[(r["brand"].lower().replace("-", "_").replace(" ", "_"), r["brand"], r["model"])] += 1
    classes = []
    for (slug_brand, brand, model), c in counts.most_common():
        if slug_brand in BRAND_SLUG:
            classes.append((slug_brand, brand, model, c))
    return classes


def main():
    classes = load_classes()
    print(f"[*] {len(classes)} classes to scrape (top 20 shown):")
    for s, b, m, c in classes[:20]:
        print(f"    {c:>4}  {b} {m}")
    print()

    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    classes = classes[:top_n]

    results = {}
    for slug_brand, brand, model, count in classes:
        class_slug = f"{slug_brand}_{re.sub(r'[^a-z0-9]+', '_', model.lower()).strip('_')}"
        print(f"[{class_slug}] {brand} {model} ({count} samples)")

        url = derive_url(slug_brand, model)
        if not url:
            print(f"  skip — no URL pattern"); continue
        print(f"  page: {url}")

        html = fetch_page(url)
        if not html:
            results[class_slug] = {"brand": brand, "model": model, "sample_count": count, "axles": axles_from_model(model), "error": "page_fetch_fail"}
            continue

        pdfs = extract_pdf_urls(html)
        if not pdfs:
            results[class_slug] = {"brand": brand, "model": model, "sample_count": count, "axles": axles_from_model(model), "error": "no_pdfs"}
            continue

        pdf_url = pick_metric_pdf(pdfs)
        print(f"  pdf: {pdf_url[:80]}...")

        pdf_path = PDF_CACHE / f"{class_slug}.pdf"
        if not pdf_path.exists():
            if not download(pdf_url, pdf_path):
                results[class_slug] = {"brand": brand, "model": model, "sample_count": count, "axles": axles_from_model(model), "error": "pdf_download_fail"}
                continue

        text = pdftotext(pdf_path)
        specs = parse_specs(text)
        specs["brand"] = brand
        specs["model"] = model
        specs["sample_count"] = count
        specs["axles"] = axles_from_model(model)
        specs["source_pdf"] = pdf_url
        results[class_slug] = specs

        print(f"  parsed: cap={specs.get('capacity_t')} boom={specs.get('boom_main_m')} h={specs.get('max_lifting_height_m')} r={specs.get('max_working_radius_m')} axles={specs.get('axles')}")
        time.sleep(0.5)

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\n[*] Wrote {len(results)} specs to {OUT}")

    # Summary
    have_boom = sum(1 for v in results.values() if v.get("boom_main_m"))
    have_cap = sum(1 for v in results.values() if v.get("capacity_t"))
    print(f"[*] Got capacity for {have_cap}/{len(results)}, boom_main for {have_boom}/{len(results)}")


if __name__ == "__main__":
    main()
