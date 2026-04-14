"""
hercules-upload.py — Fully automated crane listing via Hercules AI.

Opens browser, navigates to GST Cranes app, attaches photos, sends message,
waits for Hercules AI to build the page, publishes. No manual interaction needed.

Usage:
    python scripts/hercules-upload.py --crane <folder>       # Full auto upload
    python scripts/hercules-upload.py --crane <folder> --no-publish  # Don't publish, just create
    python scripts/hercules-upload.py --explore              # Manual exploration
"""

import json
import os
import sys
import logging
import time
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
CHROME_PROFILE = PROJECT_ROOT / ".chrome-profile"
SCREENSHOTS_DIR = PROJECT_ROOT / "logs" / "screenshots"
ENV_FILE = PROJECT_ROOT / ".env"

HERCULES_DASHBOARD = "https://hercules.app/dashboard"
GST_CRANES_APP = "https://hercules.app/dashboard/app/01KN7PHC5CDE8W8RBWAD8MVT83"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_hercules-upload.log"

    logger = logging.getLogger("hercules-upload")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ── Selectors ────────────────────────────────────────────────────────────────

SELECTORS = {
    "gst_cranes_app": 'text="GST Cranes"',
    "chat_input": 'textarea[placeholder*="message"], textarea[placeholder*="Message"], textarea[placeholder*="Hercules"], textarea[placeholder*="Ask"], [contenteditable="true"], div[role="textbox"]',
    "attach_image": 'text="Attach Image", button[aria-label="Attach"]',
    "image_upload": 'input[type="file"]',
    "build_mode": 'text="Build mode"',
    "publish_btn": 'button:has-text("Publish")',
    "new_chat": 'text="New chat", button:has-text("New chat")',
}

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

# ── Message Generation ───────────────────────────────────────────────────────

def generate_title(info: dict) -> str:
    year = info.get("year", "")
    brand = info.get("brand", "")
    model = info.get("model", "")
    capacity = info.get("capacity_tons", "")
    return f"{year} {brand} {model} - {capacity}t Mobile Crane"


def generate_hercules_prompt(info: dict) -> str:
    """Short message for Hercules AI — photos + key details."""
    brand = info.get("brand", "")
    model = info.get("model", "")
    year = info.get("year", "")
    hours = info.get("operating_hours", "")
    capacity = info.get("capacity_tons", "")
    boom = info.get("boom_length_m", "")
    price = info.get("price_eur", "")
    country = info.get("origin_country", "")
    notes = info.get("notes", "")

    crane_type = info.get("crane_type", "mobile").lower()

    # Map crane type to section name
    section_map = {
        "mobile": "Mobile Cranes (Mobil Vincler)",
        "crawler": "Crawler Cranes (Paletli Vincler)",
    }
    section = section_map.get(crane_type, "Mobile Cranes (Mobil Vincler)")

    prompt = f"Add a new crane listing to the {section} section under VINC SAT: {year} {brand} {model}, {capacity}t, {hours} hours, boom {boom}m, EUR {price}, origin {country}."

    if notes:
        prompt += f" {notes}."

    prompt += " Use the attached photos."

    return prompt

# ── Image Finder ─────────────────────────────────────────────────────────────

def find_images(info: dict, folder: Path) -> list[Path]:
    """Find processed web images, fall back to raw images."""
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")
    prefix = f"{brand}-{model}-"

    if PROCESSED_DIR.exists():
        processed = sorted(
            f for f in PROCESSED_DIR.iterdir()
            if f.name.startswith(prefix) and f.name.endswith("-web.jpg")
        )
        if processed:
            return processed

    # Fallback to raw
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)

# ── Browser Automation (fully automated) ─────────────────────────────────────

def take_screenshot(page: Page, name: str) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOTS_DIR / f"{timestamp}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info(f"Screenshot: {path}")
    return path


def run_hercules_upload(
    bilgiler: dict,
    images: list[Path],
    auto_publish: bool = False,
) -> dict:
    """
    Fully automated Hercules upload. No manual interaction.
    Returns dict with status, url, screenshot paths.
    """
    result = {
        "status": "failed",
        "url": None,
        "screenshots": [],
        "error": None,
    }

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
            # Step 1: Navigate to dashboard
            console.print("  Opening Hercules dashboard...")
            page.goto(HERCULES_DASHBOARD, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            logger.info(f"Navigated to {HERCULES_DASHBOARD}")

            # Check if login required
            if any(word in page.url.lower() for word in ["login", "signin", "auth"]):
                screenshot = take_screenshot(page, "needs-login")
                result["screenshots"].append(str(screenshot))
                result["error"] = "Not logged in. Run once manually to save session: python scripts/hercules-upload.py --explore"
                result["status"] = "needs_login"
                console.print("  [red]Not logged in to Hercules[/red]")
                console.print("  [yellow]Run from your terminal first to log in:[/yellow]")
                console.print("  [yellow]  python scripts/hercules-upload.py --explore[/yellow]")
                return result

            console.print("  [green]Logged in[/green]")

            # Step 2: Navigate directly to GST Cranes app
            console.print("  Opening GST Cranes app...")
            page.goto(GST_CRANES_APP, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)  # Let the app fully render
            logger.info(f"Navigated to GST Cranes app: {page.url}")
            console.print(f"  [green]In GST Cranes app[/green]")

            # Step 3: Attach images via hidden file input
            if images:
                console.print(f"  Attaching {len(images)} images...")
                try:
                    # Hercules has hidden input[type="file"] elements — use the first one
                    file_inputs = page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        file_inputs[0].set_input_files([str(img) for img in images])
                        page.wait_for_timeout(3000)  # Wait for upload
                        console.print(f"  [green]Attached {len(images)} images[/green]")
                        logger.info(f"Attached {len(images)} images via hidden file input")
                    else:
                        console.print("  [yellow]No file input found, continuing without images[/yellow]")
                        logger.warning("No file input found")
                except Exception as e:
                    console.print(f"  [yellow]Image attach failed: {e}[/yellow]")
                    logger.warning(f"Image attach failed: {e}")

            # Step 4: Type and send message
            message = generate_hercules_prompt(bilgiler)
            console.print(f"  Sending: {message}")

            sent = False
            # Try multiple chat input strategies
            for selector in [
                'textarea[placeholder*="message"]',
                'textarea[placeholder*="Message"]',
                'textarea',
                '[contenteditable="true"]',
                'div[role="textbox"]',
                'input[placeholder*="message"]',
            ]:
                try:
                    chat = page.wait_for_selector(selector, timeout=3000)
                    chat.click()
                    page.wait_for_timeout(300)

                    # Try fill first (works for textarea/input)
                    try:
                        chat.fill(message)
                    except Exception:
                        # For contenteditable, use keyboard typing
                        page.keyboard.type(message, delay=10)

                    page.wait_for_timeout(500)
                    page.keyboard.press("Enter")
                    logger.info(f"Message sent via selector: {selector}")
                    console.print("  [green]Message sent to Hercules AI[/green]")
                    sent = True
                    break
                except PlaywrightTimeout:
                    continue

            if not sent:
                screenshot = take_screenshot(page, "no-chat-input")
                result["screenshots"].append(str(screenshot))
                result["error"] = f"Could not find chat input. Screenshot: {screenshot}"
                console.print(f"  [red]Could not find chat input[/red]")
                return result

            # Step 5: Wait for Hercules AI to fully finish
            console.print("  Waiting for Hercules AI to generate listing...")
            _wait_for_generation(page)

            # Take screenshot after generation
            page.wait_for_timeout(3000)  # Extra buffer
            screenshot = take_screenshot(page, "generated")
            result["screenshots"].append(str(screenshot))
            console.print(f"  [green]Listing generated[/green]")
            console.print(f"  Screenshot: {screenshot}")

            # Step 6: Verify the preview looks good
            # Navigate to the preview to check the crane page
            preview_screenshot = take_screenshot(page, "preview")
            result["screenshots"].append(str(preview_screenshot))
            console.print(f"  Preview: {preview_screenshot}")
            result["status"] = "generated"

            # Step 7: Publish only if auto_publish
            if auto_publish:
                console.print("  Publishing site...")
                try:
                    pub = page.wait_for_selector(SELECTORS["publish_btn"], timeout=10000)
                    pub.click()
                    page.wait_for_timeout(8000)  # Wait for publish to complete
                    logger.info("Clicked Publish")

                    screenshot = take_screenshot(page, "published")
                    result["screenshots"].append(str(screenshot))
                    result["status"] = "published"
                    result["url"] = page.url
                    console.print(f"  [bold green]Published![/bold green]")
                except PlaywrightTimeout:
                    console.print("  [yellow]Could not find Publish button[/yellow]")
                    result["error"] = "Listing generated but could not auto-publish."
            else:
                console.print("  [yellow]Listing generated (--no-publish flag)[/yellow]")

        except Exception as e:
            logger.error(f"Error: {e}")
            result["error"] = str(e)
            try:
                screenshot = take_screenshot(page, "error")
                result["screenshots"].append(str(screenshot))
            except Exception:
                pass

        finally:
            context.close()

    return result


def _wait_for_generation(page: Page, timeout_seconds: int = 180):
    """
    Wait for Hercules AI to finish generating.
    Checks for "Building your app", "Stop" button, loading indicators.
    Waits until page is stable for 15+ seconds.
    """
    console.print("  [dim]Waiting for Hercules AI...[/dim]")
    page.wait_for_timeout(10000)  # Initial wait for generation to start

    stable_count = 0
    for i in range(timeout_seconds // 5):
        page.wait_for_timeout(5000)

        is_busy = page.evaluate("""
            () => {
                // Check for "Building your app" text
                const body = document.body.innerText || '';
                if (body.includes('Building your app')) return true;

                // Check for Stop button (visible during generation)
                const stopBtn = document.querySelector('button[aria-label="Stop"]');
                if (stopBtn && stopBtn.offsetParent !== null) return true;

                // Check for loading/spinner indicators
                const indicators = document.querySelectorAll(
                    '[class*="loading"], [class*="spinner"], [class*="generating"], [class*="typing"], [class*="animate-pulse"]'
                );
                for (const el of indicators) {
                    if (el.offsetParent !== null) return true;
                }

                return false;
            }
        """)

        elapsed = (i + 1) * 5 + 10
        if is_busy:
            stable_count = 0
            console.print(f"  [dim]Still generating... ({elapsed}s)[/dim]")
        else:
            stable_count += 1
            if stable_count >= 3:  # Stable for 15 seconds
                console.print(f"  [green]Generation complete ({elapsed}s)[/green]")
                return

    console.print(f"  [yellow]Wait timeout ({timeout_seconds}s) — proceeding anyway[/yellow]")

# ── Record Saving ────────────────────────────────────────────────────────────

def save_publish_record(info: dict, result: dict) -> Path:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")

    record = {
        "platform": "hercules",
        "title": generate_title(info),
        "url": result.get("url"),
        "status": result.get("status"),
        "published_at": datetime.now().isoformat(),
        "screenshots": result.get("screenshots", []),
        "crane_info": info,
    }

    record_path = PUBLISHED_DIR / f"{date_str}-hercules-{brand}-{model}.json"
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Record saved: {record_path}")
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
            console.print("[red]No crane folders with bilgiler.txt in yeni-vinc/[/red]")
            return None

        if len(folders) == 1:
            folder = folders[0]
        else:
            # Auto-select first folder, print which one
            folder = folders[0]
            console.print(f"[dim]Multiple cranes found, using first: {folder.name}[/dim]")

    bilgiler_path = folder / "bilgiler.txt"
    if not bilgiler_path.exists():
        console.print(f"[red]Missing bilgiler.txt in {folder.name}/[/red]")
        return None

    bilgiler = parse_bilgiler(bilgiler_path)
    required = ["brand", "model", "year", "capacity_tons", "price_eur"]
    missing = [f for f in required if not bilgiler.get(f)]
    if missing:
        console.print(f"[red]Missing fields in bilgiler.txt: {', '.join(missing)}[/red]")
        return None

    return folder, bilgiler

# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--auto", is_flag=True, help="Fully automated, no prompts (for Claude Code)")
@click.option("--explore", is_flag=True, help="Open dashboard for manual exploration + login")
@click.option("--crane", "crane_folder", default=None, help="Crane folder name in yeni-vinc/")
@click.option("--publish", is_flag=True, help="Auto-publish after generation (default: generate only, wait for approval)")
def main(auto: bool, explore: bool, crane_folder: str | None, publish: bool):
    """GST Cranes — Automated Hercules Upload"""

    load_dotenv(ENV_FILE)

    console.print("[bold cyan]GST Cranes — Hercules Upload[/bold cyan]")
    console.print()

    # Explore mode — for initial login and manual inspection
    if explore:
        with sync_playwright() as p:
            CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(CHROME_PROFILE),
                headless=False,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(HERCULES_DASHBOARD, wait_until="domcontentloaded", timeout=30000)

            console.print("Browser is open. Log in and explore.")
            console.print("Press Enter here when done.")
            try:
                input()
            except EOFError:
                console.print("[dim]Non-interactive mode. Browser will close in 60s.[/dim]")
                page.wait_for_timeout(60000)
            finally:
                context.close()
        return

    # Normal automated mode
    selection = select_crane_folder(crane_folder)
    if not selection:
        sys.exit(1)
    folder, bilgiler = selection

    title = generate_title(bilgiler)
    images = find_images(bilgiler, folder)

    console.print(f"Crane: [bold]{title}[/bold]")
    console.print(f"Images: {len(images)}")
    console.print(f"Publish: {'yes' if publish else 'no — will wait for your approval'}")
    console.print()

    # Run upload — default: generate only, don't publish
    result = run_hercules_upload(bilgiler, images, auto_publish=publish)

    # Save record
    record_path = save_publish_record(bilgiler, result)

    # Report
    console.print()
    if result["status"] == "published":
        console.print(f"[bold green]SUCCESS — Listing published[/bold green]")
        console.print(f"  URL: {result['url']}")
    elif result["status"] == "generated":
        console.print(f"[yellow]Listing generated but not published[/yellow]")
        if result.get("error"):
            console.print(f"  Note: {result['error']}")
    elif result["status"] == "needs_login":
        console.print(f"[red]Login required. Run from terminal first:[/red]")
        console.print(f"  python scripts/hercules-upload.py --explore")
        sys.exit(1)
    else:
        console.print(f"[red]Failed: {result.get('error', 'Unknown error')}[/red]")
        sys.exit(1)

    console.print(f"  Record: {record_path}")
    for ss in result.get("screenshots", []):
        console.print(f"  Screenshot: {ss}")


if __name__ == "__main__":
    main()
