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
