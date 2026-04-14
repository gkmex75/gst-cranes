"""
icerik-uretici.py — Generate social media post images + text.

Picks a crane from inventory, downloads photo, renders HTML template
via Playwright, generates post text via Claude API.

Usage:
    python scripts/icerik-uretici.py --type sale        # Inventory post
    python scripts/icerik-uretici.py --type buy          # "We Buy Cranes" post
    python scripts/icerik-uretici.py --type sold --crane "Liebherr LTM 1090-2" --country Germany
    python scripts/icerik-uretici.py --type sale --crane "Liebherr LTM 1350-6.1"
"""

from typing import Optional, List, Tuple, Dict
import base64
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import click
import requests
from anthropic import Anthropic
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from rich.console import Console

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
TEMPLATES_DIR = PROJECT_ROOT / "sablonlar"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGO_PATH = TEMPLATES_DIR / "logo.png"

ENVANTER_FILE = DATA_DIR / "envanter.json"
PAYLASILAN_FILE = DATA_DIR / "paylasilan.json"

console = Console()

# ── Data Loaders ─────────────────────────────────────────────────────────────

def load_json(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Crane Selection ──────────────────────────────────────────────────────────

def select_crane(crane_name: Optional[str]) -> Optional[dict]:
    """Select a crane from inventory. If name given, find it. Otherwise pick next in rotation."""
    envanter = load_json(ENVANTER_FILE)
    if not envanter:
        console.print("[red]No inventory data. Run site-taraci.py first.[/red]")
        return None

    if crane_name:
        # Find by name (fuzzy match on brand + model)
        crane_lower = crane_name.lower()
        for crane in envanter:
            full_name = f"{crane['brand']} {crane['model']}".lower()
            if crane_lower in full_name or full_name in crane_lower:
                return crane
        console.print(f"[red]Crane not found: {crane_name}[/red]")
        console.print("[dim]Available cranes:[/dim]")
        for c in envanter:
            console.print(f"  - {c['brand']} {c['model']}")
        return None

    # Auto-select: pick crane not posted in last 7 days
    paylasilan = load_json(PAYLASILAN_FILE)
    recent_ids = set()
    cutoff = datetime.now().timestamp() - (7 * 86400)
    for p in paylasilan:
        if p.get("timestamp", 0) > cutoff:
            recent_ids.add(p.get("crane_id"))

    for crane in envanter:
        if crane["id"] not in recent_ids:
            return crane

    # All posted recently, start over with the oldest posted
    return envanter[0]


# ── Photo Download ───────────────────────────────────────────────────────────

def download_photo(url: str) -> Optional[Path]:
    """Download a photo from URL to a temp file."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        suffix = ".jpg" if "jpeg" in resp.headers.get("content-type", "") or url.endswith(".jpg") else ".png"
        tmp = Path(tempfile.mktemp(suffix=suffix))
        tmp.write_bytes(resp.content)
        return tmp
    except requests.RequestException as e:
        console.print(f"[yellow]Photo download failed: {e}[/yellow]")
        return None


# ── Template Rendering ───────────────────────────────────────────────────────

def image_to_b64(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def fmt_price(s) -> str:
    try:
        return f"{int(float(s)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(s) if s else "—"


def render_template(template_path: Path, replacements: dict, width: int, height: int, output_path: Path):
    """Render an HTML template with Playwright and save screenshot."""
    html = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        html = html.replace(key, str(value))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content(html, wait_until="networkidle")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output_path), type="jpeg", quality=95)
        page.close()
        browser.close()


def generate_images(crane: dict, post_type: str, photo_path: Optional[Path], country: str = "") -> List[Path]:
    """Generate all image variants for a post. Returns list of output paths."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logo_b64 = image_to_b64(LOGO_PATH) if LOGO_PATH.exists() else ""
    photo_b64 = image_to_b64(photo_path) if photo_path and photo_path.exists() else ""

    crane_id = crane.get("id", "unknown")
    brand = crane.get("brand", "").upper()
    model = crane.get("model", "")

    outputs = []

    if post_type == "sale":
        templates = [
            ("post", TEMPLATES_DIR / "post-template.html", 1200, 630),
            ("story", TEMPLATES_DIR / "story-template.html", 1080, 1920),
        ]
        replacements_base = {
            "{logo_b64}": logo_b64,
            "{photo_b64}": photo_b64,
            "{brand}": brand,
            "{model}": model,
            "{crane_type_label}": "All Terrain Mobile Crane" if crane.get("crane_type") == "mobile" else "Crawler Crane",
            "{year}": str(crane.get("year", "—")),
            "{capacity}": str(crane.get("capacity_tons", "—")),
            "{boom}": str(crane.get("boom_length_m", "—")),
            "{hours}": str(crane.get("operating_hours", "—")),
            "{price}": fmt_price(crane.get("price_eur")),
            "{extra_specs_html}": "",
        }

        for ttype, tpath, w, h in templates:
            if not tpath.exists():
                console.print(f"[yellow]Template not found: {tpath}[/yellow]")
                continue
            for theme in ["dark", "light"]:
                replacements = {**replacements_base, "{theme_class}": theme}
                out = OUTPUT_DIR / f"{crane_id}-{ttype}-{theme}.jpg"
                render_template(tpath, replacements, w, h, out)
                outputs.append(out)
                console.print(f"  [green]{ttype}-{theme}: {out.name}[/green]")

    elif post_type == "sold":
        tpath = TEMPLATES_DIR / "sold-template.html"
        replacements_base = {
            "{logo_b64}": logo_b64,
            "{photo_b64}": photo_b64,
            "{brand}": brand,
            "{model}": model,
            "{year}": str(crane.get("year", "—")),
            "{capacity}": str(crane.get("capacity_tons", "—")),
            "{country}": country or "a new owner",
        }
        for theme in ["dark", "light"]:
            replacements = {**replacements_base, "{theme_class}": theme}
            out = OUTPUT_DIR / f"{crane_id}-sold-{theme}.jpg"
            render_template(tpath, replacements, 1200, 630, out)
            outputs.append(out)
            console.print(f"  [green]sold-{theme}: {out.name}[/green]")

    elif post_type == "buy":
        tpath = TEMPLATES_DIR / "alim-template.html"
        all_brands = ["Liebherr", "Tadano", "Demag", "Grove", "Terex", "Sany", "XCMG"]
        brands_html = "".join(f'<span class="brand-tag">{b}</span>' for b in all_brands)
        replacements_base = {
            "{logo_b64}": logo_b64,
            "{badge_text}": "WE BUY CRANES",
            "{headline_html}": '<span class="we">WE</span> <span class="buy">BUY</span> <span class="cranes">CRANES</span>',
            "{subtext}": "All brands, all tonnages, worldwide pickup.<br>Fast evaluation &amp; fair market prices.",
            "{brands_html}": brands_html,
        }
        for theme in ["dark", "light"]:
            replacements = {**replacements_base, "{theme_class}": theme}
            out = OUTPUT_DIR / f"we-buy-cranes-{theme}.jpg"
            render_template(tpath, replacements, 1200, 630, out)
            outputs.append(out)
            console.print(f"  [green]buy-{theme}: {out.name}[/green]")

    elif post_type == "wanted":
        tpath = TEMPLATES_DIR / "alim-template.html"
        wanted_brand = crane.get("brand", "").upper()
        wanted_model = crane.get("model", "")
        crane_label = f"{wanted_brand} {wanted_model}".strip()
        replacements_base = {
            "{logo_b64}": logo_b64,
            "{badge_text}": "WANTED",
            "{headline_html}": f'<span class="buy">WANTED:</span> <span class="cranes">{crane_label}</span>',
            "{subtext}": f"We are looking to buy a {crane_label}.<br>Contact us if you have one available!",
            "{brands_html}": "",
        }
        for theme in ["dark", "light"]:
            replacements = {**replacements_base, "{theme_class}": theme}
            out = OUTPUT_DIR / f"wanted-{crane_id}-{theme}.jpg"
            render_template(tpath, replacements, 1200, 630, out)
            outputs.append(out)
            console.print(f"  [green]wanted-{theme}: {out.name}[/green]")

    return outputs


# ── Text Generation (Claude API) ────────────────────────────────────────────

def generate_post_text(crane: dict, post_type: str, country: str = "") -> dict:
    """Generate post text using Claude API. Returns dict with 'text' key."""
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        # Fallback: use templates without AI
        return generate_fallback_text(crane, post_type, country)

    client = Anthropic(api_key=api_key)

    brand = crane.get("brand", "")
    model = crane.get("model", "")
    year = crane.get("year", "")
    capacity = crane.get("capacity_tons", "")
    price = crane.get("price_eur", "")

    if post_type == "sale":
        prompt = f"""Write a social media post for selling a used crane. Keep it concise (3-4 lines max).

Crane: {year} {brand} {model}, {capacity}t capacity, EUR {price:,}
Company: GST Cranes (gstcranes.com)
Contact: WhatsApp +32 483 56 64 65

Requirements:
1. English only
2. MUST include: "We also BUY cranes! Sell your crane to GST Cranes — contact us today!"
3. Include these hashtags: #gstcranes #usedcranes #craneforsale #webuycanes #sellyourcrane #heavyequipment #construction #crane #{brand.lower()}

Return as JSON: {{"text": "english text"}}"""

    elif post_type == "sold":
        prompt = f"""Write a social media post announcing a crane has been SOLD. Keep it concise (3-4 lines max).

Crane: {brand} {model}, {capacity}t
Delivered to: {country or 'a satisfied customer'}
Company: GST Cranes

Requirements:
1. English only
2. Start with "SOLD —"
3. MUST include buying message: "We buy & sell cranes worldwide! DM us"
4. Include hashtags: #gstcranes #sold #craneforsale #webuycanes #usedcranes #heavyequipment

Return as JSON: {{"text": "english text"}}"""

    elif post_type == "buy":
        prompt = f"""Write a social media post for buying cranes. GST Cranes wants to BUY used cranes. Keep it concise (3-4 lines max).

Company: GST Cranes
Brands we buy: Liebherr, Tadano, Demag, Grove, Terex, Sany, XCMG
Contact: WhatsApp +32 483 56 64 65

Requirements:
1. English only
2. Focus on BUYING, not selling
3. "All brands, all tonnages, worldwide pickup"
4. Include hashtags: #webuycanes #sellyourcrane #gstcranes #cranebuyer #usedcranes #heavyequipment

Return as JSON: {{"text": "english text"}}"""

    elif post_type == "wanted":
        prompt = f"""Write a social media post for GST Cranes looking to BUY a specific crane. Keep it concise (3-4 lines max).

Crane wanted: {brand} {model}
Company: GST Cranes (gstcranes.com)
Contact: WhatsApp +32 483 56 64 65

Requirements:
1. English only
2. Focus: we are LOOKING TO BUY this specific crane
3. "If you have one available, contact us!"
4. Include hashtags: #wanted #webuycanes #gstcranes #{brand.lower()} #usedcranes #craneforsale #heavyequipment

Return as JSON: {{"text": "english text"}}"""
    else:
        return generate_fallback_text(crane, post_type, country)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        console.print(f"[yellow]Claude API error, using fallback: {e}[/yellow]")

    return generate_fallback_text(crane, post_type, country)


def generate_fallback_text(crane: dict, post_type: str, country: str = "") -> dict:
    """Fallback text templates when Claude API is unavailable."""
    brand = crane.get("brand", "")
    model = crane.get("model", "")
    year = crane.get("year", "")
    capacity = crane.get("capacity_tons", "")
    price = crane.get("price_eur", 0)

    if post_type == "sale":
        price_fmt = f"{price:,}".replace(",", ".") if price else "Contact us"
        return {
            "text": f"\U0001f3d7\ufe0f {year} {brand} {model} \u2014 {capacity}t Mobile Crane\nPrice: EUR {price_fmt}\nFully inspected, worldwide delivery\n\n\U0001f3d7\ufe0f We also BUY cranes! Sell your crane to GST Cranes \u2014 contact us today! \U0001f4de\nWhatsApp: +32 483 56 64 65\n\n#gstcranes #usedcranes #craneforsale #webuycanes #sellyourcrane #heavyequipment #construction #crane #{brand.lower()}",
        }
    elif post_type == "sold":
        return {
            "text": f"\u2705 SOLD \u2014 Another successful delivery by GST Cranes! {brand} {model} {capacity}t delivered to {country or 'a satisfied customer'}.\nWe buy & sell cranes worldwide! DM us \U0001f4e9\nWhatsApp: +32 483 56 64 65\n\n#gstcranes #sold #craneforsale #webuycanes #usedcranes #heavyequipment",
        }
    elif post_type == "wanted":
        return {
            "text": f"\U0001f50d WANTED: {brand} {model}\n\nGST Cranes is looking to buy a {brand} {model}.\nIf you have one available, contact us!\n\nWhatsApp: +32 483 56 64 65\ninfo@gstcranes.com\n\n#wanted #webuycanes #gstcranes #{brand.lower()} #usedcranes #craneforsale #heavyequipment",
        }
    else:  # buy
        return {
            "text": "\U0001f3d7\ufe0f WE BUY CRANES!\nAll brands: Liebherr, Tadano, Demag, Grove, Terex, Sany, XCMG\nAll tonnages, worldwide pickup.\nFast evaluation & fair market prices.\n\nWhatsApp: +32 483 56 64 65\ninfo@gstcranes.com\n\n#webuycanes #sellyourcrane #gstcranes #cranebuyer #usedcranes #heavyequipment",
        }


# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--type", "post_type", required=True, type=click.Choice(["sale", "buy", "sold", "wanted"]))
@click.option("--crane", "crane_name", default=None, help="Crane name (e.g. 'Liebherr LTM 1090-2')")
@click.option("--country", default="", help="Delivery country (for SOLD posts)")
def main(post_type: str, crane_name: Optional[str], country: str):
    """GST Marketing — Content Generator"""
    console.print("[bold cyan]GST Marketing — Content Generator[/bold cyan]")

    # For "buy" type, no crane needed
    if post_type == "buy":
        crane = {"id": "we-buy-cranes", "brand": "", "model": ""}
        photo_path = None
    elif post_type == "wanted":
        if not crane_name:
            console.print("[red]--crane required for wanted posts (e.g. --crane 'Liebherr LTM 1230-5')[/red]")
            sys.exit(1)
        # Create a minimal crane dict from the name
        parts = crane_name.split(None, 1)
        crane = {
            "id": crane_name.lower().replace(" ", "-"),
            "brand": parts[0] if parts else crane_name,
            "model": parts[1] if len(parts) > 1 else "",
        }
        photo_path = None
    else:
        crane = select_crane(crane_name)
        if not crane:
            sys.exit(1)

        console.print(f"  Crane: {crane['brand']} {crane['model']}")

        # Download photo
        photo_path = None
        if crane.get("photo_urls"):
            console.print(f"  Downloading photo...")
            photo_path = download_photo(crane["photo_urls"][0])
            if photo_path:
                console.print(f"  Photo: {photo_path.name}")
            else:
                console.print("[yellow]  No photo available, generating without photo[/yellow]")

    # Generate images
    console.print(f"\n  Generating {post_type} images...")
    images = generate_images(crane, post_type, photo_path, country)

    # Generate text
    console.print(f"  Generating post text...")
    texts = generate_post_text(crane, post_type, country)

    # Save text alongside images
    text_path = OUTPUT_DIR / f"{crane.get('id', 'post')}-{post_type}-text.json"
    save_json(text_path, texts)

    # Summary
    console.print(f"\n[bold green]{len(images)} images generated[/bold green]")
    console.print(f"[bold]English text:[/bold]\n{texts.get('text', texts.get('en', ''))[:200]}...")
    console.print(f"\nOutput: [cyan]{OUTPUT_DIR}[/cyan]")

    # Clean up temp photo
    if photo_path and photo_path.exists() and str(photo_path).startswith(tempfile.gettempdir()):
        photo_path.unlink()


if __name__ == "__main__":
    main()
