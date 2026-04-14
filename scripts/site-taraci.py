"""
site-taraci.py — Scrape gstcranes.com inventory.

Navigates to the website, extracts all crane listings,
saves to data/envanter.json. Detects new and removed listings.

Usage:
    python scripts/site-taraci.py              # Scrape and save
    python scripts/site-taraci.py --diff       # Show changes since last run
"""

from typing import Optional, List, Tuple, Dict
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import click
import requests
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.table import Table

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
ENVANTER_FILE = DATA_DIR / "envanter.json"

SITE_URL = "https://www.gstcranes.com"
INVENTORY_URL = f"{SITE_URL}/inventory"

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_site-taraci.log"

    logger = logging.getLogger("site-taraci")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ── Scraper ──────────────────────────────────────────────────────────────────

def scrape_inventory() -> List[dict]:
    """Scrape all crane listings from gstcranes.com."""
    cranes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        logger.info(f"Navigating to {SITE_URL}")
        page.goto(SITE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for content to render (Hercules SPA)
        page.wait_for_timeout(5000)

        # Scroll down to load all listings
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1000)

        # Back to top
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1000)

        # Try to find inventory section / navigate to inventory page
        # The site may have inventory on homepage or separate page
        # Try both approaches

        # Extract crane cards — Hercules sites typically use common card patterns
        # We'll extract using multiple selector strategies
        cards = extract_crane_cards(page)

        if not cards:
            # Try inventory page directly
            logger.info(f"No cards on homepage, trying {INVENTORY_URL}")
            page.goto(INVENTORY_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(1000)
            cards = extract_crane_cards(page)

        cranes = cards
        logger.info(f"Found {len(cranes)} cranes")

        # Take screenshot for debugging
        screenshot_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_inventory.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot: {screenshot_path}")

        browser.close()

    return cranes


def extract_crane_cards(page) -> List[dict]:
    """Extract crane data from the current page using JS evaluation."""
    # Use JavaScript to extract structured data from the rendered page
    # This is more robust than CSS selectors for Hercules SPA sites
    cards_data = page.evaluate("""
    () => {
        const cranes = [];

        // Strategy 1: Look for product/listing cards with price
        // Hercules sites render cards with images, titles, and prices
        const allLinks = document.querySelectorAll('a[href*="/inventory/"], a[href*="/crane"], a[href*="/product"]');
        const cardElements = new Set();

        allLinks.forEach(link => {
            // Walk up to find the card container
            let el = link;
            for (let i = 0; i < 5; i++) {
                if (el.parentElement) el = el.parentElement;
            }
            cardElements.add(el);
        });

        // Strategy 2: Find cards by looking for price patterns (EUR/€)
        const allText = document.querySelectorAll('*');
        allText.forEach(el => {
            const text = el.textContent || '';
            if ((text.includes('€') || text.includes('EUR')) && text.length < 200) {
                // Might be a price element, walk up to card
                let card = el;
                for (let i = 0; i < 5; i++) {
                    if (card.parentElement) card = card.parentElement;
                }
                cardElements.add(card);
            }
        });

        // Strategy 3: Look for image cards with crane-related text
        const imgContainers = document.querySelectorAll('[class*="card"], [class*="listing"], [class*="product"], [class*="item"]');
        imgContainers.forEach(el => cardElements.add(el));

        // Now extract data from unique card-like containers
        // Filter: must contain an image AND text with crane brand keywords
        const brands = ['liebherr', 'tadano', 'grove', 'demag', 'terex', 'sany', 'xcmg', 'zoomlion', 'kobelco', 'manitowoc', 'link-belt'];

        cardElements.forEach(card => {
            const text = (card.textContent || '').toLowerCase();
            const hasBrand = brands.some(b => text.includes(b));
            if (!hasBrand) return;

            const img = card.querySelector('img');
            const imgSrc = img ? (img.src || img.dataset.src || '') : '';

            // Extract price
            const priceMatch = (card.textContent || '').match(/[€EUR]*\s*([\d.,]+)/);
            const price = priceMatch ? priceMatch[1].replace(/\./g, '').replace(',', '') : '';

            // Extract year
            const yearMatch = (card.textContent || '').match(/\b(19|20)\d{2}\b/);
            const year = yearMatch ? yearMatch[0] : '';

            // Extract link
            const link = card.querySelector('a[href*="/"]');
            const href = link ? link.href : '';

            // Extract title/heading text
            const headings = card.querySelectorAll('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="name"]');
            let title = '';
            headings.forEach(h => { if (h.textContent.trim().length > title.length) title = h.textContent.trim(); });
            if (!title) {
                // Fallback: find the longest short text that contains a brand
                const texts = [];
                card.querySelectorAll('*').forEach(el => {
                    const t = el.textContent.trim();
                    if (t.length > 5 && t.length < 100 && brands.some(b => t.toLowerCase().includes(b))) {
                        texts.push(t);
                    }
                });
                if (texts.length > 0) title = texts[0];
            }

            // Extract capacity (tons/tonnes/t)
            const capMatch = (card.textContent || '').match(/(\d+)\s*(?:ton|tonnes?|t\b)/i);
            const capacity = capMatch ? capMatch[1] : '';

            // Detect type from badge text
            const typeMatch = (card.textContent || '').toLowerCase();
            let craneType = 'mobile';
            if (typeMatch.includes('crawler')) craneType = 'crawler';

            if (title || imgSrc) {
                cranes.push({
                    title: title,
                    photo_url: imgSrc,
                    listing_url: href,
                    price_raw: price,
                    year: year,
                    capacity_tons: capacity,
                    crane_type: craneType
                });
            }
        });

        // Deduplicate by listing_url or title
        const seen = new Set();
        return cranes.filter(c => {
            const key = c.listing_url || c.title;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }
    """)

    # Post-process in Python
    today = datetime.now().strftime("%Y-%m-%d")
    results = []

    for card in cards_data:
        title = card.get("title", "")
        if not title:
            continue

        # Parse brand and model from title
        brand, model = parse_title(title)

        crane_id = f"{brand}-{model}".lower().replace(" ", "-")

        # Parse price
        price_raw = card.get("price_raw", "")
        try:
            price_eur = int(price_raw) if price_raw else 0
        except ValueError:
            price_eur = 0

        results.append({
            "id": crane_id,
            "brand": brand,
            "model": model,
            "year": int(card.get("year")) if card.get("year") else 0,
            "capacity_tons": int(card.get("capacity_tons")) if card.get("capacity_tons") else 0,
            "price_eur": price_eur,
            "crane_type": card.get("crane_type", "mobile"),
            "photo_urls": [card["photo_url"]] if card.get("photo_url") else [],
            "listing_url": card.get("listing_url", ""),
            "first_seen": today,
            "last_seen": today,
        })

    return results


def parse_title(title: str) -> Tuple[str, str]:
    """Parse 'Liebherr LTM 1350-6.1' into ('Liebherr', 'LTM 1350-6.1')."""
    brands = {
        "liebherr": "Liebherr",
        "tadano": "Tadano",
        "grove": "Grove",
        "demag": "Demag",
        "terex": "Terex",
        "sany": "Sany",
        "xcmg": "XCMG",
        "zoomlion": "Zoomlion",
        "kobelco": "Kobelco",
        "manitowoc": "Manitowoc",
        "link-belt": "Link-Belt",
    }

    title_lower = title.lower()
    for key, brand_name in brands.items():
        if key in title_lower:
            # Model is everything after the brand name
            idx = title_lower.index(key)
            model = title[idx + len(key):].strip()
            if not model:
                model = title[:idx].strip()
            return brand_name, model

    # Fallback: first word is brand, rest is model
    parts = title.split(None, 1)
    return parts[0] if parts else "Unknown", parts[1] if len(parts) > 1 else ""


# ── Data Management ──────────────────────────────────────────────────────────

def load_envanter() -> List[dict]:
    """Load existing inventory from JSON file."""
    if not ENVANTER_FILE.exists():
        return []
    try:
        return json.loads(ENVANTER_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_envanter(cranes: List[dict]):
    """Save inventory to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ENVANTER_FILE.write_text(
        json.dumps(cranes, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    logger.info(f"Saved {len(cranes)} cranes to {ENVANTER_FILE}")


def merge_envanter(old: List[dict], new: List[dict]) -> tuple[List[dict], List[dict], List[dict]]:
    """
    Merge old and new inventory.
    Returns: (merged, added, removed)
    - Updates last_seen for existing cranes
    - Preserves first_seen from old data
    - Identifies new and removed listings
    """
    today = datetime.now().strftime("%Y-%m-%d")
    old_by_id = {c["id"]: c for c in old}
    new_by_id = {c["id"]: c for c in new}

    merged = []
    added = []
    removed = []

    # Process new listings
    for crane_id, crane in new_by_id.items():
        if crane_id in old_by_id:
            # Existing crane — update last_seen, keep first_seen
            crane["first_seen"] = old_by_id[crane_id].get("first_seen", today)
            crane["last_seen"] = today
        else:
            # New crane
            crane["first_seen"] = today
            crane["last_seen"] = today
            added.append(crane)
        merged.append(crane)

    # Identify removed listings
    for crane_id, crane in old_by_id.items():
        if crane_id not in new_by_id:
            removed.append(crane)

    return merged, added, removed


# ── Display ──────────────────────────────────────────────────────────────────

def print_inventory(cranes: List[dict]):
    """Print inventory as a table."""
    table = Table(title=f"GST Cranes Inventory ({len(cranes)} cranes)")
    table.add_column("Brand", style="cyan")
    table.add_column("Model", style="white")
    table.add_column("Year", style="yellow")
    table.add_column("Capacity", style="green")
    table.add_column("Price (EUR)", style="bold")
    table.add_column("Type", style="dim")

    for c in cranes:
        price_str = f"{c['price_eur']:,}".replace(",", ".") if c["price_eur"] else "—"
        table.add_row(
            c["brand"],
            c["model"],
            str(c["year"]) if c["year"] else "—",
            f"{c['capacity_tons']}t" if c["capacity_tons"] else "—",
            price_str,
            c["crane_type"],
        )

    console.print(table)


def print_diff(added: List[dict], removed: List[dict]):
    """Print changes since last run."""
    if added:
        console.print(f"\n[green]+ {len(added)} new listing(s):[/green]")
        for c in added:
            console.print(f"  [green]+ {c['brand']} {c['model']} — EUR {c.get('price_eur', 0):,}[/green]")

    if removed:
        console.print(f"\n[red]- {len(removed)} removed listing(s):[/red]")
        for c in removed:
            console.print(f"  [red]- {c['brand']} {c['model']}[/red]")

    if not added and not removed:
        console.print("[dim]No changes since last run.[/dim]")


# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--diff", is_flag=True, help="Show changes since last run")
def main(diff: bool):
    """GST Marketing — Website Inventory Scraper"""
    console.print("[bold cyan]GST Marketing — Site Scraper[/bold cyan]")

    old_cranes = load_envanter()

    console.print(f"  Scraping {SITE_URL}...")
    new_cranes = scrape_inventory()

    if not new_cranes:
        console.print("[red]No cranes found on website. Check logs for details.[/red]")
        console.print(f"[dim]Logs: {LOG_DIR}[/dim]")
        sys.exit(1)

    merged, added, removed = merge_envanter(old_cranes, new_cranes)
    save_envanter(merged)

    print_inventory(merged)
    print_diff(added, removed)

    console.print(f"\nSaved to: [cyan]{ENVANTER_FILE}[/cyan]")


if __name__ == "__main__":
    main()
