# Social Media Post Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Pillow-based social media post generator with HTML/CSS templates rendered via Playwright screenshot, matching gstcranes.com brand identity.

**Architecture:** Two HTML template files (post + story) with embedded CSS for dark/light themes. A rewritten `post-gorsel.py` script loads the template, injects crane data + photo as base64, opens it in headless Chromium via Playwright, and takes a screenshot. Same CLI interface as before (`--auto`, `--crane`).

**Tech Stack:** Playwright (already installed), Python f-string templating (no Jinja2 needed), Google Fonts (Oswald), base64 image embedding.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `sablonlar/post-template.html` | Create | 1200x630 post template with dark+light CSS |
| `sablonlar/story-template.html` | Create | 1080x1920 story template with dark+light CSS |
| `scripts/post-gorsel.py` | Rewrite | Load template, inject data, Playwright screenshot |

No other files change. `vinc-yayinla.py` calls `post-gorsel.py` via subprocess — CLI interface stays identical.

---

### Task 1: Create Post Template (1200x630)

**Files:**
- Create: `sablonlar/post-template.html`

- [ ] **Step 1: Create the post HTML template**

Create `sablonlar/post-template.html` with the full layout for 1200x630. The template uses Python `{variable}` placeholders that will be filled by f-string. It includes both dark and light theme CSS, switched by the `{theme_class}` placeholder on `<body>`.

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    width: 1200px;
    height: 630px;
    font-family: 'Oswald', 'Arial Black', sans-serif;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* ── Dark Theme ── */
  body.dark {
    --bg: #0A0A0A;
    --bg2: #1A1A1A;
    --accent: #C41E1E;
    --text: #FFFFFF;
    --text2: #9CA3AF;
    --border: #2A2A2A;
    --logo-gst: #FFFFFF;
  }

  /* ── Light Theme ── */
  body.light {
    --bg: #FFFFFF;
    --bg2: #F3F4F6;
    --accent: #C41E1E;
    --text: #0A0A0A;
    --text2: #6B7280;
    --border: #E5E7EB;
    --logo-gst: #0A0A0A;
  }

  body { background: var(--bg); color: var(--text); }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 24px;
    background: var(--bg2);
    border-bottom: 3px solid var(--accent);
    height: 60px;
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-logo {
    width: 40px;
    height: 40px;
    border-radius: 4px;
  }

  .header-brand {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 2px;
  }

  .header-brand .gst { color: var(--logo-gst); }
  .header-brand .cranes { color: var(--accent); }

  .badge-for-sale {
    background: var(--accent);
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
    padding: 6px 18px;
    border-radius: 4px;
    letter-spacing: 1px;
  }

  /* ── Main Content ── */
  .content {
    display: flex;
    flex: 1;
    padding: 12px 24px;
    gap: 20px;
    min-height: 0;
  }

  /* Left: photo */
  .photo-section {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .photo-section img {
    max-width: 100%;
    max-height: 100%;
    object-fit: cover;
    border-radius: 8px;
    border: 2px solid var(--border);
  }

  /* Right: info */
  .info-section {
    width: 420px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .crane-brand {
    font-size: 36px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  .crane-model {
    font-size: 28px;
    font-weight: 600;
    color: var(--accent);
  }

  .crane-type {
    font-size: 14px;
    color: var(--text2);
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  /* Spec boxes */
  .specs {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-top: 6px;
  }

  .spec-box {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    text-align: center;
  }

  .spec-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
  }

  .spec-label {
    font-size: 11px;
    color: var(--text2);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 2px;
  }

  /* Price */
  .price-box {
    background: var(--bg2);
    border: 2px solid var(--accent);
    border-radius: 6px;
    padding: 10px;
    text-align: center;
    margin-top: 4px;
  }

  .price-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
  }

  .price-sub {
    font-size: 12px;
    color: var(--text2);
    margin-top: 2px;
  }

  /* ── Footer ── */
  .footer {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 8px 24px;
    background: var(--bg2);
    border-top: 2px solid var(--accent);
    height: 44px;
    flex-shrink: 0;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  .footer-item { color: var(--text2); }
  .footer-item.website { color: var(--accent); font-weight: 700; }
</style>
</head>
<body class="{theme_class}">

  <div class="header">
    <div class="header-left">
      <img src="{logo_b64}" class="header-logo" alt="GST">
      <div class="header-brand">
        <span class="gst">GST</span> <span class="cranes">CRANES</span>
      </div>
    </div>
    <div class="badge-for-sale">FOR SALE</div>
  </div>

  <div class="content">
    <div class="photo-section">
      <img src="{photo_b64}" alt="Crane">
    </div>
    <div class="info-section">
      <div class="crane-brand">{brand}</div>
      <div class="crane-model">{model}</div>
      <div class="crane-type">{crane_type_label}</div>

      <div class="specs">
        <div class="spec-box">
          <div class="spec-value">{year}</div>
          <div class="spec-label">Year</div>
        </div>
        <div class="spec-box">
          <div class="spec-value">{capacity}t</div>
          <div class="spec-label">Capacity</div>
        </div>
        <div class="spec-box">
          <div class="spec-value">{boom}m</div>
          <div class="spec-label">Main Boom</div>
        </div>
        <div class="spec-box">
          <div class="spec-value">{hours}</div>
          <div class="spec-label">Hours</div>
        </div>
      </div>

      {extra_specs_html}

      <div class="price-box">
        <div class="price-value">EUR {price}</div>
        <div class="price-sub">Available for immediate delivery</div>
      </div>
    </div>
  </div>

  <div class="footer">
    <span class="footer-item website">www.gstcranes.com</span>
    <span class="footer-item">WhatsApp: +32 483 56 64 65</span>
    <span class="footer-item">@gstcranes</span>
    <span class="footer-item">info@gstcranes.com</span>
  </div>

</body>
</html>
```

- [ ] **Step 2: Verify the template renders in a browser**

Open `sablonlar/post-template.html` in a browser manually (replace placeholders with test values) to verify layout looks correct at 1200x630. This is a visual sanity check only.

- [ ] **Step 3: Commit**

```bash
cd ~/gst-cranes
git add sablonlar/post-template.html
git commit -m "feat: add post template HTML (1200x630) with dark/light themes"
```

---

### Task 2: Create Story Template (1080x1920)

**Files:**
- Create: `sablonlar/story-template.html`

- [ ] **Step 1: Create the story HTML template**

Create `sablonlar/story-template.html`. Same design language as post, but vertical layout — everything stacked, larger photo, more breathing room.

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    width: 1080px;
    height: 1920px;
    font-family: 'Oswald', 'Arial Black', sans-serif;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* ── Dark Theme ── */
  body.dark {
    --bg: #0A0A0A;
    --bg2: #1A1A1A;
    --accent: #C41E1E;
    --text: #FFFFFF;
    --text2: #9CA3AF;
    --border: #2A2A2A;
    --logo-gst: #FFFFFF;
  }

  /* ── Light Theme ── */
  body.light {
    --bg: #FFFFFF;
    --bg2: #F3F4F6;
    --accent: #C41E1E;
    --text: #0A0A0A;
    --text2: #6B7280;
    --border: #E5E7EB;
    --logo-gst: #0A0A0A;
  }

  body { background: var(--bg); color: var(--text); }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
    background: var(--bg2);
    border-bottom: 4px solid var(--accent);
    height: 90px;
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .header-logo {
    width: 56px;
    height: 56px;
    border-radius: 6px;
  }

  .header-brand {
    font-size: 30px;
    font-weight: 700;
    letter-spacing: 3px;
  }

  .header-brand .gst { color: var(--logo-gst); }
  .header-brand .cranes { color: var(--accent); }

  .badge-for-sale {
    background: var(--accent);
    color: #FFFFFF;
    font-size: 22px;
    font-weight: 700;
    padding: 10px 28px;
    border-radius: 6px;
    letter-spacing: 2px;
  }

  /* ── Brand / Model ── */
  .title-section {
    text-align: center;
    padding: 30px 32px 20px;
    flex-shrink: 0;
  }

  .crane-brand {
    font-size: 56px;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
  }

  .crane-model {
    font-size: 42px;
    font-weight: 600;
    color: var(--accent);
    margin-top: 4px;
  }

  .crane-type {
    font-size: 20px;
    color: var(--text2);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 8px;
  }

  /* ── Photo ── */
  .photo-section {
    flex: 1;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
  }

  .photo-section img {
    max-width: 100%;
    max-height: 100%;
    object-fit: cover;
    border-radius: 12px;
    border: 2px solid var(--border);
  }

  /* ── Specs ── */
  .specs-section {
    padding: 20px 32px;
    flex-shrink: 0;
  }

  .specs {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  .spec-box {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 8px;
    text-align: center;
  }

  .spec-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
  }

  .spec-label {
    font-size: 14px;
    color: var(--text2);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 4px;
  }

  .extra-specs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 12px;
  }

  /* ── Price ── */
  .price-section {
    padding: 0 32px 20px;
    flex-shrink: 0;
  }

  .price-box {
    background: var(--bg2);
    border: 2px solid var(--accent);
    border-radius: 10px;
    padding: 20px;
    text-align: center;
  }

  .price-value {
    font-size: 38px;
    font-weight: 700;
    color: var(--accent);
  }

  .price-sub {
    font-size: 18px;
    color: var(--text2);
    margin-top: 6px;
  }

  /* ── Footer ── */
  .footer {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 14px 32px;
    background: var(--bg2);
    border-top: 3px solid var(--accent);
    height: 65px;
    flex-shrink: 0;
    font-size: 18px;
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  .footer-item { color: var(--text2); }
  .footer-item.website { color: var(--accent); font-weight: 700; }
</style>
</head>
<body class="{theme_class}">

  <div class="header">
    <div class="header-left">
      <img src="{logo_b64}" class="header-logo" alt="GST">
      <div class="header-brand">
        <span class="gst">GST</span> <span class="cranes">CRANES</span>
      </div>
    </div>
    <div class="badge-for-sale">FOR SALE</div>
  </div>

  <div class="title-section">
    <div class="crane-brand">{brand}</div>
    <div class="crane-model">{model}</div>
    <div class="crane-type">{crane_type_label}</div>
  </div>

  <div class="photo-section">
    <img src="{photo_b64}" alt="Crane">
  </div>

  <div class="specs-section">
    <div class="specs">
      <div class="spec-box">
        <div class="spec-value">{year}</div>
        <div class="spec-label">Year</div>
      </div>
      <div class="spec-box">
        <div class="spec-value">{capacity}t</div>
        <div class="spec-label">Capacity</div>
      </div>
      <div class="spec-box">
        <div class="spec-value">{boom}m</div>
        <div class="spec-label">Main Boom</div>
      </div>
      <div class="spec-box">
        <div class="spec-value">{hours}</div>
        <div class="spec-label">Hours</div>
      </div>
    </div>
    {extra_specs_html}
  </div>

  <div class="price-section">
    <div class="price-box">
      <div class="price-value">EUR {price}</div>
      <div class="price-sub">Available for immediate delivery</div>
    </div>
  </div>

  <div class="footer">
    <span class="footer-item website">www.gstcranes.com</span>
    <span class="footer-item">WhatsApp: +32 483 56 64 65</span>
    <span class="footer-item">@gstcranes</span>
    <span class="footer-item">info@gstcranes.com</span>
  </div>

</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
cd ~/gst-cranes
git add sablonlar/story-template.html
git commit -m "feat: add story template HTML (1080x1920) with dark/light themes"
```

---

### Task 3: Rewrite post-gorsel.py

**Files:**
- Rewrite: `scripts/post-gorsel.py`

This is the core change. The script keeps the same CLI interface (`--auto`, `--crane`) but replaces all Pillow rendering with Playwright screenshot.

- [ ] **Step 1: Write the new post-gorsel.py**

Replace the entire contents of `scripts/post-gorsel.py` with:

```python
"""
post-gorsel.py — Generate social media images from HTML/CSS templates.

Uses Playwright to render HTML templates and take screenshots.
Outputs 4 files per crane: post-dark, post-light, story-dark, story-light.

Usage:
    python scripts/post-gorsel.py --auto --crane <folder>
    python scripts/post-gorsel.py --crane <folder>
"""

import base64
import re
import sys
from pathlib import Path

import click
from playwright.sync_api import sync_playwright
from rich.console import Console

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
INPUT_DIR = PROJECT_ROOT / "yeni-vinc"
PROCESSED_DIR = PROJECT_ROOT / "processed"
TEMPLATES_DIR = PROJECT_ROOT / "sablonlar"
LOGO_PATH = TEMPLATES_DIR / "logo.png"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

console = Console()


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_bilgiler(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def image_to_b64(path: Path) -> str:
    """Convert an image file to a data URI string."""
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def fmt_price(s: str) -> str:
    """Format price with dots as thousands separator: 285000 -> 285.000"""
    try:
        return f"{int(float(s)):,}".replace(",", ".")
    except ValueError:
        return s


def find_best_photo(info: dict, folder: Path) -> Path | None:
    """Find the best photo to use: prefer processed web image, fallback to raw."""
    brand = info.get("brand", "x").lower().replace(" ", "-")
    model = info.get("model", "x").lower().replace(" ", "-")
    prefix = f"{brand}-{model}-"

    # Prefer processed web images
    if PROCESSED_DIR.exists():
        web_images = sorted(
            f for f in PROCESSED_DIR.iterdir()
            if f.name.startswith(prefix) and f.name.endswith("-web.jpg")
        )
        if web_images:
            return web_images[0]

    # Fallback to raw photos
    raw = sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)
    return raw[0] if raw else None


def extract_extra_specs(info: dict) -> list[tuple[str, str]]:
    """Extract additional specs (flyjib, luffing, km) from notes."""
    specs = []
    notes = info.get("notes", "")
    for part in notes.split("."):
        pl = part.strip().lower()
        if "flyjib" in pl or "fly jib" in pl:
            m = re.search(r'(\d+)\s*m', part)
            specs.append((f"{m.group(1)}m" if m else "Yes", "Flyjib"))
        elif "luffing" in pl:
            m = re.search(r'(\d+)\s*m', part)
            specs.append((f"{m.group(1)}m" if m else "Yes", "Luffing Jib"))
        elif "superlift" in pl:
            specs.append(("Yes", "Superlift"))
    for part in notes.split("|"):
        if "km" in part.lower():
            m = re.search(r'[\d,.]+', part)
            if m:
                specs.append((m.group(), "KM"))
            break
    return specs


def build_extra_specs_html(specs: list[tuple[str, str]], template_type: str) -> str:
    """Build HTML for extra spec boxes. Returns empty string if no extras."""
    if not specs:
        return ""

    css_class = "extra-specs" if template_type == "story" else "specs"
    cols = 3 if template_type == "story" else 2
    style = f' style="grid-template-columns: repeat({cols}, 1fr); margin-top: 8px;"'

    boxes = ""
    for value, label in specs:
        boxes += f"""
        <div class="spec-box">
          <div class="spec-value">{value}</div>
          <div class="spec-label">{label}</div>
        </div>"""

    return f'<div class="{css_class}"{style}>{boxes}\n    </div>'


def fill_template(template_path: Path, info: dict, photo_b64: str, logo_b64: str, theme: str, template_type: str) -> str:
    """Read a template file and fill in all placeholders."""
    html = template_path.read_text(encoding="utf-8")

    crane_type = info.get("crane_type", "mobile")
    if crane_type == "mobile":
        crane_type_label = "All Terrain Mobile Crane"
    elif crane_type == "crawler":
        crane_type_label = "Crawler Crane"
    else:
        crane_type_label = "Mobile Crane"

    extra_specs = extract_extra_specs(info)
    extra_specs_html = build_extra_specs_html(extra_specs, template_type)

    replacements = {
        "{theme_class}": theme,
        "{logo_b64}": logo_b64,
        "{photo_b64}": photo_b64,
        "{brand}": info.get("brand", "").upper(),
        "{model}": info.get("model", ""),
        "{crane_type_label}": crane_type_label,
        "{year}": info.get("year", "—"),
        "{capacity}": info.get("capacity_tons", "—"),
        "{boom}": info.get("boom_length_m", "—"),
        "{hours}": info.get("operating_hours", "—"),
        "{price}": fmt_price(info.get("price_eur", "0")),
        "{extra_specs_html}": extra_specs_html,
    }

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


# ── Screenshot Renderer ──────────────────────────────────────────────────────

def render_screenshots(info: dict, photo_path: Path) -> list[Path]:
    """Render all 4 images (post dark/light, story dark/light). Returns output paths."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    brand = info.get("brand", "x").lower().replace(" ", "-")
    model = info.get("model", "x").lower().replace(" ", "-")
    prefix = f"{brand}-{model}"

    photo_b64 = image_to_b64(photo_path)
    logo_b64 = image_to_b64(LOGO_PATH) if LOGO_PATH.exists() else ""

    outputs = []

    templates = [
        ("post", TEMPLATES_DIR / "post-template.html", 1200, 630),
        ("story", TEMPLATES_DIR / "story-template.html", 1080, 1920),
    ]

    themes = ["dark", "light"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for template_type, template_path, width, height in templates:
            for theme in themes:
                html = fill_template(template_path, info, photo_b64, logo_b64, theme, template_type)

                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(html, wait_until="networkidle")

                output_path = PROCESSED_DIR / f"{prefix}-{template_type}-{theme}.jpg"
                page.screenshot(path=str(output_path), type="jpeg", quality=95)
                page.close()

                outputs.append(output_path)
                console.print(f"  [green]{template_type}-{theme} ({width}x{height}): {output_path.name}[/green]")

        browser.close()

    return outputs


# ── CLI ──────────────────────────────────────────────────────────────────────

def select_crane_folder(folder_name: str | None) -> tuple[Path, dict] | None:
    if folder_name:
        f = INPUT_DIR / folder_name
        if not f.exists():
            console.print(f"[red]Folder not found: {f}[/red]")
            return None
    else:
        fs = sorted(d for d in INPUT_DIR.iterdir() if d.is_dir() and (d / "bilgiler.txt").exists())
        if not fs:
            console.print("[red]No crane folders with bilgiler.txt in yeni-vinc/[/red]")
            return None
        f = fs[0]

    bilgiler_path = f / "bilgiler.txt"
    if not bilgiler_path.exists():
        console.print(f"[red]Missing bilgiler.txt in {f.name}/[/red]")
        return None

    return f, parse_bilgiler(bilgiler_path)


@click.command()
@click.option("--auto", is_flag=True)
@click.option("--crane", "crane_folder", default=None)
def main(auto: bool, crane_folder: str | None):
    """GST Cranes — Generate social media images"""
    console.print("[bold cyan]GST Cranes — Post Generator[/bold cyan]")

    sel = select_crane_folder(crane_folder)
    if not sel:
        sys.exit(1)

    folder, bilgiler = sel
    brand = bilgiler.get("brand", "?")
    model = bilgiler.get("model", "?")
    console.print(f"  Crane: {brand} {model}")

    photo = find_best_photo(bilgiler, folder)
    if not photo:
        console.print("[red]No photos found[/red]")
        sys.exit(1)

    console.print(f"  Photo: {photo.name}")

    outputs = render_screenshots(bilgiler, photo)
    console.print(f"\n[bold green]{len(outputs)} images generated[/bold green]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script on the test crane to verify output**

```bash
cd ~/gst-cranes && source .venv/bin/activate
python scripts/post-gorsel.py --auto --crane liebherr-ltm-1090
```

Expected: 4 JPEG files in `processed/`:
- `liebherr-ltm-1090-2-post-dark.jpg` (1200x630)
- `liebherr-ltm-1090-2-post-light.jpg` (1200x630)
- `liebherr-ltm-1090-2-story-dark.jpg` (1080x1920)
- `liebherr-ltm-1090-2-story-light.jpg` (1080x1920)

- [ ] **Step 3: Open all 4 images and visually verify**

```bash
open ~/gst-cranes/processed/liebherr-ltm-1090-2-post-dark.jpg
open ~/gst-cranes/processed/liebherr-ltm-1090-2-post-light.jpg
open ~/gst-cranes/processed/liebherr-ltm-1090-2-story-dark.jpg
open ~/gst-cranes/processed/liebherr-ltm-1090-2-story-light.jpg
```

Check:
- Colors match gstcranes.com (black+red+white for dark, white+red+black for light)
- Logo appears correctly in header
- Crane photo displays without distortion
- Spec boxes show correct values from bilgiler.txt
- Price formatted with dots (285.000)
- Footer contact info complete (website, WhatsApp, IG, email)
- No text cut off, no layout overflow

- [ ] **Step 4: Commit**

```bash
cd ~/gst-cranes
git add scripts/post-gorsel.py
git commit -m "feat: rewrite post-gorsel.py — HTML/CSS + Playwright screenshot

Replaces Pillow pixel drawing with HTML templates + Playwright.
Outputs 4 images per crane: post/story x dark/light.
Post: 1200x630 (Facebook + LinkedIn + Instagram)
Story: 1080x1920 (Facebook + Instagram Story)"
```

---

### Task 4: End-to-End Verification

**Files:** None (testing only)

- [ ] **Step 1: Test with the second crane**

```bash
cd ~/gst-cranes && source .venv/bin/activate
python scripts/post-gorsel.py --auto --crane liebherr-ltm-1350
```

Verify 4 images generated for the second crane as well.

- [ ] **Step 2: Test via orchestrator dry-run**

```bash
python scripts/vinc-yayinla.py --dry-run --crane liebherr-ltm-1090
```

Verify the orchestrator still calls post-gorsel.py correctly (no interface breakage).

- [ ] **Step 3: Verify old Pillow imports are not needed**

Check that `Pillow`, `opencv-python` are only needed by `gorsel-hazirla.py`, not by `post-gorsel.py` anymore. The `requirements.txt` stays the same since other scripts still use Pillow.

---

## Quick Reference

After implementation, generating social media posts works exactly the same as before:

```bash
cd ~/gst-cranes && source .venv/bin/activate

# Generate posts for a specific crane
python scripts/post-gorsel.py --auto --crane liebherr-ltm-1090

# Full pipeline (includes post generation)
python scripts/vinc-yayinla.py --auto --crane liebherr-ltm-1090
```

Output is now 4 files instead of 2:
```
processed/
  liebherr-ltm-1090-2-post-dark.jpg    # 1200x630 — FB/LinkedIn/IG post
  liebherr-ltm-1090-2-post-light.jpg   # 1200x630 — FB/LinkedIn/IG post
  liebherr-ltm-1090-2-story-dark.jpg   # 1080x1920 — FB/IG Story
  liebherr-ltm-1090-2-story-light.jpg  # 1080x1920 — FB/IG Story
```
