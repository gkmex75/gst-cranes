"""
machineryline-upload.py — Upload crane listing to machineryline.com.

Fills the real Machinery Line form with correct field names.
Does NOT submit without --publish flag.

Usage:
    python scripts/machineryline-upload.py --auto --crane <folder>              # Fill form only
    python scripts/machineryline-upload.py --auto --crane <folder> --publish    # Fill + submit
    python scripts/machineryline-upload.py --explore                            # Manual exploration
"""

import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout
from rich.console import Console
from rich.panel import Panel

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
INPUT_DIR = PROJECT_ROOT / "yeni-vinc"
PROCESSED_DIR = PROJECT_ROOT / "processed"
PUBLISHED_DIR = PROJECT_ROOT / "yayinlanan"
LOG_DIR = PROJECT_ROOT / "logs"
CHROME_PROFILE = Path.home() / ".gst-chrome-profiles" / "machineryline"
SCREENSHOTS_DIR = PROJECT_ROOT / "logs" / "screenshots"
ENV_FILE = PROJECT_ROOT / ".env"

ML_ADD = "https://machineryline.info/add/"

# crane_type → ML category text on the add page
ML_CATEGORY = {
    "mobile": "All-terrain crane",
    "crawler": "Crawler crane",
    "truck": "Truck crane",
}

# Brand name → ML trademark value
ML_BRAND_MAP = {
    "liebherr": "2657",
    "demag": "2529",
    "grove": "2591",
    "faun": "2552",
    "kato": "2928",
    "sany": "4053",
    "palfinger sany": "8304",
    "liugong": "3657",
    "ppm": "2723",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_machineryline-upload.log"

    logger = logging.getLogger("machineryline-upload")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ── bilgiler.txt Parser ─────────────────────────────────────────────────────

def parse_bilgiler(bilgiler_path: Path) -> dict:
    data = {}
    for line in bilgiler_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data

# ── Template ─────────────────────────────────────────────────────────────────

def generate_title(info: dict) -> str:
    return f"{info.get('year', '')} {info.get('brand', '')} {info.get('model', '')} - {info.get('capacity_tons', '')}t Mobile Crane"


def generate_description(info: dict) -> str:
    brand = info.get("brand", "")
    model = info.get("model", "")
    year = info.get("year", "")
    hours = info.get("operating_hours", "N/A")
    capacity = info.get("capacity_tons", "")
    boom = info.get("boom_length_m", "N/A")
    price = info.get("price_eur", "")
    country = info.get("origin_country", "")
    notes = info.get("notes", "")

    desc = f"""{brand} {model} — Year {year}
Operating hours: {hours}
Capacity: {capacity} tons
Boom length: {boom} m
Price: EUR {price}

Condition: Excellent, fully inspected and ready for immediate operation.
Origin: {country}
Inspection available on request at our yard.

Delivery worldwide — Europe, Asia, Africa, Middle East, and the Americas.

Contact GST Cranes:
info@gstcranes.com
WhatsApp: +32 483 56 64 65
www.gstcranes.com"""

    if notes:
        desc += f"\n\n{notes}"

    return desc

# ── Image Finder ─────────────────────────────────────────────────────────────

def find_images(info: dict, folder: Path) -> list[Path]:
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")
    prefix = f"{brand}-{model}-"

    crane_dir = PROCESSED_DIR / prefix.rstrip("-")
    if crane_dir.exists():
        processed = sorted(
            f for f in crane_dir.iterdir()
            if f.name.startswith(prefix) and f.name.endswith("-web.jpg")
        )
        if processed:
            return processed

    return sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)

# ── Browser Helpers ──────────────────────────────────────────────────────────

def take_screenshot(page: Page, name: str) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"{timestamp}_ml_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info(f"Screenshot: {path}")
    return path

# ── Main Upload ──────────────────────────────────────────────────────────────

def run_ml_upload(bilgiler: dict, images: list[Path], auto_publish: bool = False) -> dict:
    result = {
        "status": "failed",
        "url": None,
        "screenshots": [],
        "error": None,
    }

    crane_type = bilgiler.get("crane_type", "mobile").lower()
    ml_category = ML_CATEGORY.get(crane_type, "All-terrain crane")

    with sync_playwright() as p:
        CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Step 1: Go to add page
            console.print("  Opening Machinery Line...")
            page.goto(ML_ADD, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if "sign" in page.url.lower() or "login" in page.url.lower():
                result["error"] = "Not logged in. Run: python scripts/machineryline-upload.py --explore"
                result["status"] = "needs_login"
                console.print("  [red]Not logged in[/red]")
                return result

            console.print("  [green]Logged in[/green]")

            # Step 2: Select category from "recently used" links
            console.print(f"  Selecting: {ml_category}...")
            try:
                # Click any element containing the category text
                page.click(f'text="{ml_category}"', timeout=5000)
                page.wait_for_timeout(3000)
                console.print(f"  [green]Category: {ml_category}[/green]")
            except PlaywrightTimeout:
                # Fallback: try via JS click
                try:
                    page.evaluate(f"""
                        () => {{
                            const els = document.querySelectorAll('*');
                            for (const el of els) {{
                                if (el.textContent.trim() === '{ml_category}' && el.children.length === 0) {{
                                    el.click();
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """)
                    page.wait_for_timeout(3000)
                    console.print(f"  [green]Category: {ml_category} (via JS)[/green]")
                except Exception:
                    result["error"] = f"Could not find category: {ml_category}"
                    console.print(f"  [red]Category not found[/red]")
                    return result

            # Step 3: Fill form fields
            console.print("  Filling form...")

            # Brand (select dropdown)
            brand = bilgiler.get("brand", "")
            brand_val = ML_BRAND_MAP.get(brand.lower(), "")
            if brand_val:
                try:
                    page.select_option('select[name="v--trademark"]', value=brand_val)
                    page.wait_for_timeout(1000)
                    console.print(f"  Brand: {brand}")
                    logger.info(f"Brand: {brand} (value={brand_val})")
                except Exception as e:
                    logger.warning(f"Brand select failed: {e}")

            # Model — hidden input, set via JS
            model = bilgiler.get("model", "")
            if model:
                try:
                    page.wait_for_timeout(1500)
                    page.evaluate(f"""
                        () => {{
                            const input = document.querySelector('input[name="v--model"]');
                            if (input) {{
                                input.value = '{model}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                    """)
                    console.print(f"  Model: {model}")
                except Exception as e:
                    logger.warning(f"Model fill failed: {e}")

            # Year of manufacture
            year = bilgiler.get("year", "")
            if year:
                try:
                    page.select_option('select[name="v--yearmade"]', value=year)
                    console.print(f"  Year: {year}")
                except Exception as e:
                    logger.warning(f"Year select failed: {e}")

            # Condition: Used (click radio)
            try:
                page.click('label:has-text("Used")', timeout=2000)
            except PlaywrightTimeout:
                pass

            # Running hours
            hours = bilgiler.get("operating_hours", "")
            if hours:
                try:
                    page.fill('input[name="v--narabotka"]', hours)
                    console.print(f"  Running hours: {hours}")
                except Exception as e:
                    logger.warning(f"Hours fill failed: {e}")

            # Load capacity — field is in kg, convert from tons
            capacity = bilgiler.get("capacity_tons", "")
            if capacity:
                try:
                    capacity_kg = str(int(float(capacity) * 1000))
                    page.fill('input[name="v--tonnage"]', capacity_kg)
                    console.print(f"  Capacity: {capacity}t ({capacity_kg} kg)")
                except Exception as e:
                    logger.warning(f"Capacity fill failed: {e}")

            # Boom length (lifting height)
            boom = bilgiler.get("boom_length_m", "")
            if boom:
                try:
                    page.fill('input[name="v--spec_vysota_podjema"]', boom)
                    console.print(f"  Boom/lifting height: {boom}m")
                except Exception as e:
                    logger.warning(f"Boom fill failed: {e}")

            # Description (English)
            description = generate_description(bilgiler)
            try:
                page.fill('textarea[name="text-field-description-en"]', description)
                console.print(f"  Description (EN): {len(description)} chars")
                logger.info(f"Description filled ({len(description)} chars)")
            except Exception as e:
                logger.warning(f"Description fill failed: {e}")

            # Price
            price = bilgiler.get("price_eur", "")
            if price:
                try:
                    page.fill('input[name="v--price"]', price)
                    console.print(f"  Price: {price}")
                    # Select EUR currency
                    try:
                        page.select_option('select[name="v--currency"]', value="EUR")
                        console.print(f"  Currency: EUR")
                    except Exception:
                        logger.warning("Could not select EUR currency")
                except Exception as e:
                    logger.warning(f"Price fill failed: {e}")

            # Advert type: Sale
            try:
                page.click('label:has-text("Sale")', timeout=2000)
            except PlaywrightTimeout:
                pass

            console.print("  [green]Form filled[/green]")

            # Step 4: Upload photos
            if images:
                console.print(f"  Uploading {len(images)} photos...")
                try:
                    file_inputs = page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        file_inputs[0].set_input_files([str(img) for img in images])
                        page.wait_for_timeout(5000)
                        console.print(f"  [green]Uploaded {len(images)} photos[/green]")
                    else:
                        console.print("  [yellow]No file input found[/yellow]")
                except Exception as e:
                    console.print(f"  [yellow]Photo upload failed: {e}[/yellow]")

            # Step 5: Screenshot
            page.wait_for_timeout(2000)
            screenshot = take_screenshot(page, "form-filled")
            result["screenshots"].append(str(screenshot))
            console.print(f"  Screenshot: {screenshot}")

            # Step 6: Submit or wait
            if auto_publish:
                console.print("  Submitting form...")
                try:
                    # Step 1: Click "Place your ad" / save button on the form
                    for btn in ["Place your ad", "Save", "Submit", "Publish"]:
                        try:
                            page.click(f'button:has-text("{btn}"), input[value="{btn}"], a:has-text("{btn}")', timeout=3000)
                            page.wait_for_timeout(5000)
                            logger.info(f"Clicked form submit: {btn}")
                            break
                        except PlaywrightTimeout:
                            continue

                    screenshot = take_screenshot(page, "preview")
                    result["screenshots"].append(str(screenshot))
                    console.print(f"  Form submitted, preview page loaded")

                    # Step 2: Click Advertise/Activate button on preview page
                    console.print("  Activating listing...")
                    page.wait_for_timeout(3000)
                    screenshot = take_screenshot(page, "preview")
                    result["screenshots"].append(str(screenshot))

                    activated = False
                    for btn_text in ["Advertise", "Activate", "Publish", "Place"]:
                        try:
                            page.click(f'a:has-text("{btn_text}"), button:has-text("{btn_text}")', timeout=3000)
                            page.wait_for_timeout(5000)
                            logger.info(f"Clicked: {btn_text}")
                            activated = True
                            break
                        except PlaywrightTimeout:
                            continue

                    if not activated:
                        # Try clicking any prominent orange/green button
                        try:
                            page.click('a.button-orange, a.btn-primary, button.btn-primary, a[class*="advertise"], a[class*="activate"]', timeout=3000)
                            page.wait_for_timeout(5000)
                            activated = True
                        except PlaywrightTimeout:
                            pass

                    # Handle any confirmation dialog
                    try:
                        page.click('button:has-text("OK"), button:has-text("Confirm"), button:has-text("Yes")', timeout=3000)
                        page.wait_for_timeout(3000)
                    except PlaywrightTimeout:
                        pass

                    # Step 3: On my/sales page, find and click "Activate" button
                    console.print("  Looking for Activate button...")
                    page.wait_for_timeout(3000)

                    try:
                        # Find the first Activate button (newest listing is usually at top)
                        page.click('a:has-text("Activate"), button:has-text("Activate")', timeout=5000)
                        page.wait_for_timeout(5000)
                        logger.info("Clicked Activate")

                        # Handle any confirmation after Activate
                        try:
                            page.click('button:has-text("OK"), button:has-text("Confirm"), button:has-text("Yes"), a:has-text("OK")', timeout=3000)
                            page.wait_for_timeout(3000)
                        except PlaywrightTimeout:
                            pass

                        activated = True
                        console.print(f"  [green]Activated![/green]")
                    except PlaywrightTimeout:
                        console.print(f"  [yellow]Activate button not found[/yellow]")

                    screenshot = take_screenshot(page, "final")
                    result["screenshots"].append(str(screenshot))
                    result["status"] = "published" if activated else "generated"
                    result["url"] = page.url
                    if activated:
                        console.print(f"  [bold green]Listed and activated![/bold green]")
                    else:
                        console.print(f"  [yellow]Submitted but not activated[/yellow]")

                except Exception as e:
                    result["error"] = f"Submit failed: {e}"
                    console.print(f"  [red]Submit failed: {e}[/red]")
            else:
                result["status"] = "generated"
                console.print("  [yellow]Form filled — waiting for approval[/yellow]")

        except Exception as e:
            logger.error(f"Error: {e}")
            result["error"] = str(e)
            try:
                take_screenshot(page, "error")
            except Exception:
                pass

        finally:
            context.close()

    return result

# ── Record Saving ────────────────────────────────────────────────────────────

def save_publish_record(info: dict, result: dict) -> Path:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")

    record = {
        "platform": "machineryline",
        "title": generate_title(info),
        "url": result.get("url"),
        "status": result.get("status"),
        "published_at": datetime.now().isoformat(),
        "screenshots": result.get("screenshots", []),
        "crane_info": info,
    }

    record_path = PUBLISHED_DIR / f"{date_str}-machineryline-{brand}-{model}.json"
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record_path

# ── Crane Folder Selection ───────────────────────────────────────────────────

def select_crane_folder(folder_name: str | None) -> tuple[Path, dict] | None:
    if folder_name:
        folder = INPUT_DIR / folder_name
        if not folder.exists():
            console.print(f"[red]Folder not found: {folder}[/red]")
            return None
    else:
        folders = sorted(
            d for d in INPUT_DIR.iterdir()
            if d.is_dir() and (d / "bilgiler.txt").exists()
        )
        if not folders:
            console.print("[red]No crane folders in yeni-vinc/[/red]")
            return None
        folder = folders[0]

    bilgiler = parse_bilgiler(folder / "bilgiler.txt")
    required = ["brand", "model", "year", "capacity_tons", "price_eur"]
    missing = [f for f in required if not bilgiler.get(f)]
    if missing:
        console.print(f"[red]Missing: {', '.join(missing)}[/red]")
        return None

    return folder, bilgiler

# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--auto", is_flag=True, help="Fully automated, no prompts")
@click.option("--explore", is_flag=True, help="Open for manual exploration")
@click.option("--crane", "crane_folder", default=None, help="Crane folder name")
@click.option("--publish", is_flag=True, help="Auto-submit (default: fill only)")
def main(auto: bool, explore: bool, crane_folder: str | None, publish: bool):
    """GST Cranes — Machinery Line Upload"""

    load_dotenv(ENV_FILE)
    console.print("[bold cyan]GST Cranes — Machinery Line Upload[/bold cyan]")
    console.print()

    if explore:
        with sync_playwright() as p:
            CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(CHROME_PROFILE), headless=False,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(ML_ADD, wait_until="domcontentloaded", timeout=30000)
            console.print("Browser open. Press Enter when done.")
            try:
                input()
            except EOFError:
                page.wait_for_timeout(60000)
            finally:
                context.close()
        return

    selection = select_crane_folder(crane_folder)
    if not selection:
        sys.exit(1)
    folder, bilgiler = selection

    title = generate_title(bilgiler)
    images = find_images(bilgiler, folder)
    ml_cat = ML_CATEGORY.get(bilgiler.get("crane_type", "mobile"), "All-terrain crane")

    console.print(f"Crane: [bold]{title}[/bold]")
    console.print(f"Category: {ml_cat}")
    console.print(f"Images: {len(images)}")
    console.print(f"Submit: {'yes' if publish else 'no — fill only'}")
    console.print()

    result = run_ml_upload(bilgiler, images, auto_publish=publish)
    record_path = save_publish_record(bilgiler, result)

    console.print()
    if result["status"] == "published":
        console.print(f"[bold green]Submitted![/bold green]")
        console.print(f"  URL: {result['url']}")
    elif result["status"] == "generated":
        console.print(f"[yellow]Form filled, waiting for approval[/yellow]")
    elif result["status"] == "needs_login":
        console.print(f"[red]Login needed: python scripts/machineryline-upload.py --explore[/red]")
        sys.exit(1)
    else:
        console.print(f"[red]Failed: {result.get('error')}[/red]")
        sys.exit(1)

    console.print(f"  Record: {record_path}")
    for ss in result.get("screenshots", []):
        console.print(f"  Screenshot: {ss}")


if __name__ == "__main__":
    main()
