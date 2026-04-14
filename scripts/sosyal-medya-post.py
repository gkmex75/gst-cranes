"""
sosyal-medya-post.py — Post crane listings to Facebook, Instagram, and LinkedIn.

Prefers official APIs (Meta Graph API, LinkedIn Share API). Falls back to
browser automation via Playwright if API credentials are missing.

Usage:
    python scripts/sosyal-medya-post.py                        # Post to all platforms
    python scripts/sosyal-medya-post.py --platform facebook    # Single platform
    python scripts/sosyal-medya-post.py --platform instagram
    python scripts/sosyal-medya-post.py --platform linkedin
    python scripts/sosyal-medya-post.py --browser              # Force browser mode
    python scripts/sosyal-medya-post.py --crane <folder>       # Specify crane folder
    python scripts/sosyal-medya-post.py --check-auth           # Verify all credentials
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import click
import requests
from dotenv import load_dotenv
from PIL import Image
from rich.console import Console
from rich.panel import Panel

# Global auto mode flag
AUTO_MODE = False


def prompt(message: str, default: str = "") -> str:
    """Ask user for input. In auto mode, return default silently."""
    if AUTO_MODE:
        return default
    try:
        return input(message).strip()
    except EOFError:
        return default
from rich.table import Table

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
INPUT_DIR = PROJECT_ROOT / "yeni-vinc"
PROCESSED_DIR = PROJECT_ROOT / "processed"
PUBLISHED_DIR = PROJECT_ROOT / "yayinlanan"
LOG_DIR = PROJECT_ROOT / "logs"
CHROME_PROFILE_SOCIAL = PROJECT_ROOT / ".chrome-profile-social"
SCREENSHOTS_DIR = PROJECT_ROOT / "logs" / "screenshots"
ENV_FILE = PROJECT_ROOT / ".env"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PLATFORMS = ["facebook", "instagram", "linkedin"]

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_sosyal-medya-post.log"

    logger = logging.getLogger("sosyal-medya-post")
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

# ── Caption Generation ───────────────────────────────────────────────────────

def generate_social_caption(info: dict) -> str:
    """Standard social media caption from CLAUDE.md template."""
    year = info.get("year", "")
    brand = info.get("brand", "")
    model = info.get("model", "")
    capacity = info.get("capacity_tons", "")
    hours = info.get("operating_hours", "N/A")
    price = info.get("price_eur", "")

    return f"""{year} {brand} {model} — Now Available

{capacity}t capacity
{hours} operating hours
Fully inspected
Worldwide delivery

Price: EUR {price}
WhatsApp: +32 483 56 64 65
info@gstcranes.com

#MobileCrane #{brand.replace(' ', '')} #UsedCranes #GSTCranes #CraneForSale"""


def generate_linkedin_caption(info: dict) -> str:
    """LinkedIn variant — more professional tone, B2B hashtags."""
    year = info.get("year", "")
    brand = info.get("brand", "")
    model = info.get("model", "")
    capacity = info.get("capacity_tons", "")
    hours = info.get("operating_hours", "N/A")
    price = info.get("price_eur", "")
    boom = info.get("boom_length_m", "N/A")

    return f"""Now Available: {year} {brand} {model}

We are pleased to offer this {capacity}-ton mobile crane, fully inspected and ready for immediate deployment.

Key specifications:
- Capacity: {capacity} tons
- Boom length: {boom} m
- Operating hours: {hours}
- Price: EUR {price}

Inspection available at our yard. Worldwide delivery to Europe, Asia, Africa, Middle East, and the Americas.

Contact us:
info@gstcranes.com
WhatsApp: +32 483 56 64 65
www.gstcranes.com

#ConstructionEquipment #HeavyMachinery #MobileCrane #{brand.replace(' ', '')} #UsedCranes #GSTCranes #CraneForSale #HeavyLifting #Infrastructure"""

# ── Image Helpers ────────────────────────────────────────────────────────────

def find_social_images(info: dict) -> list[Path]:
    """Find social-sized (1080x1080) processed images."""
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")
    prefix = f"{brand}-{model}-"

    if not PROCESSED_DIR.exists():
        return []

    return sorted(
        f for f in PROCESSED_DIR.iterdir()
        if f.name.startswith(prefix) and f.name.endswith("-social.jpg")
    )


def find_web_images(info: dict) -> list[Path]:
    """Find web-sized processed images (fallback for LinkedIn)."""
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")
    prefix = f"{brand}-{model}-"

    if not PROCESSED_DIR.exists():
        return []

    return sorted(
        f for f in PROCESSED_DIR.iterdir()
        if f.name.startswith(prefix) and f.name.endswith("-web.jpg")
    )

# ── Credential Check ────────────────────────────────────────────────────────

def get_meta_credentials() -> dict | None:
    """Load Meta API credentials from .env."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")
    ig_id = os.getenv("META_INSTAGRAM_ACCOUNT_ID")

    if not token or not page_id:
        return None

    return {
        "access_token": token,
        "page_id": page_id,
        "instagram_account_id": ig_id,
    }


def get_linkedin_credentials() -> dict | None:
    """Load LinkedIn API credentials from .env."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    org_id = os.getenv("LINKEDIN_ORGANIZATION_ID")

    if not token or not org_id:
        return None

    return {
        "access_token": token,
        "organization_id": org_id,
    }


def check_all_credentials() -> dict[str, bool]:
    """Check which platform credentials are available."""
    meta = get_meta_credentials()
    linkedin = get_linkedin_credentials()

    status = {
        "facebook_api": meta is not None,
        "instagram_api": meta is not None and meta.get("instagram_account_id"),
        "linkedin_api": linkedin is not None,
    }
    return status

# ── Meta Graph API (Facebook + Instagram) ────────────────────────────────────

GRAPH_API = "https://graph.facebook.com/v21.0"


def meta_verify_token(creds: dict) -> bool:
    """Verify Meta page access token is valid."""
    try:
        resp = requests.get(
            f"{GRAPH_API}/me",
            params={"access_token": creds["access_token"]},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Meta token valid for: {data.get('name', 'unknown')}")
            return True
        logger.error(f"Meta token invalid: {resp.text}")
        return False
    except requests.RequestException as e:
        logger.error(f"Meta token check failed: {e}")
        return False


def facebook_post_photos(creds: dict, caption: str, images: list[Path]) -> str | None:
    """
    Post multiple photos to Facebook Page.
    Uses the unpublished photo + feed post method for multi-photo posts.
    """
    page_id = creds["page_id"]
    token = creds["access_token"]

    if not images:
        logger.error("No images to post to Facebook")
        return None

    # Step 1: Upload each photo as unpublished
    photo_ids = []
    for img_path in images:
        try:
            with open(img_path, "rb") as f:
                resp = requests.post(
                    f"{GRAPH_API}/{page_id}/photos",
                    data={
                        "published": "false",
                        "access_token": token,
                    },
                    files={"source": (img_path.name, f, "image/jpeg")},
                    timeout=60,
                )
            resp.raise_for_status()
            photo_id = resp.json().get("id")
            if photo_id:
                photo_ids.append(photo_id)
                logger.info(f"Uploaded unpublished photo: {photo_id}")
        except requests.RequestException as e:
            logger.error(f"Facebook photo upload failed for {img_path.name}: {e}")

    if not photo_ids:
        logger.error("No photos uploaded successfully")
        return None

    # Step 2: Create feed post with all photos attached
    post_data = {
        "message": caption,
        "access_token": token,
    }
    for i, pid in enumerate(photo_ids):
        post_data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})

    try:
        resp = requests.post(
            f"{GRAPH_API}/{page_id}/feed",
            data=post_data,
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.json().get("id")
        post_url = f"https://www.facebook.com/{post_id}"
        logger.info(f"Facebook post created: {post_url}")
        return post_url
    except requests.RequestException as e:
        logger.error(f"Facebook feed post failed: {e}")
        return None


def instagram_post_carousel(creds: dict, caption: str, images: list[Path]) -> str | None:
    """
    Post a carousel (multi-image) to Instagram via Graph API.
    Requires images to be publicly accessible URLs — we upload to Facebook first.
    """
    ig_id = creds.get("instagram_account_id")
    token = creds["access_token"]
    page_id = creds["page_id"]

    if not ig_id:
        logger.error("Instagram account ID not configured")
        return None

    # Instagram requires image URLs, not file uploads.
    # Upload to Facebook Page as unpublished photos to get URLs.
    image_urls = []
    for img_path in images[:10]:  # Instagram carousel max 10
        try:
            with open(img_path, "rb") as f:
                resp = requests.post(
                    f"{GRAPH_API}/{page_id}/photos",
                    data={
                        "published": "false",
                        "access_token": token,
                    },
                    files={"source": (img_path.name, f, "image/jpeg")},
                    timeout=60,
                )
            resp.raise_for_status()
            photo_id = resp.json().get("id")

            # Get the photo URL
            photo_resp = requests.get(
                f"{GRAPH_API}/{photo_id}",
                params={"fields": "images", "access_token": token},
                timeout=10,
            )
            photo_resp.raise_for_status()
            photo_images = photo_resp.json().get("images", [])
            if photo_images:
                image_urls.append(photo_images[0]["source"])
                logger.info(f"Got Instagram image URL for {img_path.name}")
        except requests.RequestException as e:
            logger.error(f"Instagram image prep failed for {img_path.name}: {e}")

    if not image_urls:
        logger.error("No image URLs obtained for Instagram")
        return None

    # Single image post
    if len(image_urls) == 1:
        try:
            resp = requests.post(
                f"{GRAPH_API}/{ig_id}/media",
                data={
                    "image_url": image_urls[0],
                    "caption": caption,
                    "access_token": token,
                },
                timeout=30,
            )
            resp.raise_for_status()
            creation_id = resp.json().get("id")

            # Publish
            pub_resp = requests.post(
                f"{GRAPH_API}/{ig_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=30,
            )
            pub_resp.raise_for_status()
            media_id = pub_resp.json().get("id")
            permalink = _get_ig_permalink(media_id, token)
            logger.info(f"Instagram single post: {permalink}")
            return permalink
        except requests.RequestException as e:
            logger.error(f"Instagram single post failed: {e}")
            return None

    # Carousel post (multiple images)
    container_ids = []
    for url in image_urls:
        try:
            resp = requests.post(
                f"{GRAPH_API}/{ig_id}/media",
                data={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": token,
                },
                timeout=30,
            )
            resp.raise_for_status()
            container_ids.append(resp.json().get("id"))
        except requests.RequestException as e:
            logger.error(f"Instagram carousel item failed: {e}")

    if not container_ids:
        return None

    # Create carousel container
    try:
        resp = requests.post(
            f"{GRAPH_API}/{ig_id}/media",
            data={
                "media_type": "CAROUSEL",
                "caption": caption,
                "children": ",".join(container_ids),
                "access_token": token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        carousel_id = resp.json().get("id")

        # Wait for processing
        time.sleep(5)

        # Publish
        pub_resp = requests.post(
            f"{GRAPH_API}/{ig_id}/media_publish",
            data={"creation_id": carousel_id, "access_token": token},
            timeout=30,
        )
        pub_resp.raise_for_status()
        media_id = pub_resp.json().get("id")
        permalink = _get_ig_permalink(media_id, token)
        logger.info(f"Instagram carousel post: {permalink}")
        return permalink
    except requests.RequestException as e:
        logger.error(f"Instagram carousel publish failed: {e}")
        return None


def _get_ig_permalink(media_id: str, token: str) -> str:
    """Get Instagram post permalink."""
    try:
        resp = requests.get(
            f"{GRAPH_API}/{media_id}",
            params={"fields": "permalink", "access_token": token},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("permalink", f"instagram://media?id={media_id}")
    except requests.RequestException:
        return f"instagram://media?id={media_id}"

# ── LinkedIn API ─────────────────────────────────────────────────────────────

LINKEDIN_API = "https://api.linkedin.com/v2"
LINKEDIN_REST = "https://api.linkedin.com/rest"


def linkedin_verify_token(creds: dict) -> bool:
    """Verify LinkedIn access token."""
    try:
        resp = requests.get(
            f"{LINKEDIN_API}/me",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("LinkedIn token valid")
            return True
        logger.error(f"LinkedIn token invalid: {resp.status_code}")
        return False
    except requests.RequestException as e:
        logger.error(f"LinkedIn token check failed: {e}")
        return False


def linkedin_upload_image(creds: dict, image_path: Path) -> str | None:
    """Upload image to LinkedIn and return the asset URN."""
    token = creds["access_token"]
    org_id = creds["organization_id"]
    org_urn = f"urn:li:organization:{org_id}"

    # Step 1: Register upload
    register_payload = {
        "registerUploadRequest": {
            "owner": org_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {
                    "identifier": "urn:li:userGeneratedContent",
                    "relationshipType": "OWNER",
                }
            ],
        }
    }

    try:
        resp = requests.post(
            f"{LINKEDIN_API}/assets?action=registerUpload",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=register_payload,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()

        upload_url = result["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = result["value"]["asset"]

    except (requests.RequestException, KeyError) as e:
        logger.error(f"LinkedIn image register failed: {e}")
        return None

    # Step 2: Upload binary
    try:
        with open(image_path, "rb") as f:
            resp = requests.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "image/jpeg",
                },
                data=f,
                timeout=120,
            )
        resp.raise_for_status()
        logger.info(f"LinkedIn image uploaded: {asset}")
        return asset
    except requests.RequestException as e:
        logger.error(f"LinkedIn image upload failed: {e}")
        return None


def linkedin_post(creds: dict, caption: str, images: list[Path]) -> str | None:
    """Create a LinkedIn organization post with images."""
    token = creds["access_token"]
    org_id = creds["organization_id"]
    org_urn = f"urn:li:organization:{org_id}"

    # Upload images (LinkedIn supports multi-image posts, use up to 4)
    asset_urns = []
    for img_path in images[:4]:
        asset = linkedin_upload_image(creds, img_path)
        if asset:
            asset_urns.append(asset)

    if not asset_urns:
        logger.error("No images uploaded to LinkedIn")
        return None

    # Build media array
    media = []
    for urn in asset_urns:
        media.append({
            "status": "READY",
            "media": urn,
        })

    # Create post
    post_payload = {
        "author": org_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "IMAGE",
                "media": media,
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    try:
        resp = requests.post(
            f"{LINKEDIN_API}/ugcPosts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=post_payload,
            timeout=30,
        )
        resp.raise_for_status()

        post_urn = resp.headers.get("X-RestLi-Id", resp.json().get("id", ""))
        # Convert URN to URL
        post_id = post_urn.split(":")[-1] if post_urn else ""
        post_url = f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None
        logger.info(f"LinkedIn post created: {post_url}")
        return post_url
    except requests.RequestException as e:
        logger.error(f"LinkedIn post failed: {e}")
        return None

# ── Browser Fallback ─────────────────────────────────────────────────────────

def browser_post_facebook(caption: str, images: list[Path]) -> str | None:
    """Fallback: post to Facebook via browser. Skipped in auto mode."""
    if AUTO_MODE:
        console.print("  [yellow]Facebook: no API credentials, browser fallback skipped (auto mode)[/yellow]")
        return None

    from playwright.sync_api import sync_playwright

    console.print("  [cyan]Using browser fallback for Facebook...[/cyan]")

    with sync_playwright() as p:
        CHROME_PROFILE_SOCIAL.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_SOCIAL),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("https://www.facebook.com", wait_until="networkidle", timeout=30000)

            if "login" in page.url.lower():
                console.print("  [yellow]Please log in to Facebook manually, then press Enter.[/yellow]")
                prompt("")

            console.print("  [yellow]Navigate to GST Cranes page, click 'Create post', then press Enter.[/yellow]")
            prompt("")

            console.print(Panel(caption, title="Caption", border_style="dim"))
            console.print("  [yellow]After posting, paste the post URL (or 'skip'):[/yellow]")

            post_url = prompt("  Post URL: ", "skip")
            if post_url.lower() == "skip":
                return None
            return post_url if post_url else None

        finally:
            context.close()


def browser_post_instagram(caption: str, images: list[Path]) -> str | None:
    """Fallback: guide user through Instagram posting. Skipped in auto mode."""
    if AUTO_MODE:
        console.print("  [yellow]Instagram: no API credentials, browser fallback skipped (auto mode)[/yellow]")
        return None

    console.print("  [cyan]Instagram browser fallback — manual posting.[/cyan]")
    console.print(Panel(caption, title="Caption to copy", border_style="dim"))
    post_url = prompt("  After posting, paste the Instagram post URL (or 'skip'): ", "skip")
    if post_url.lower() == "skip":
        return None
    return post_url if post_url else None


def browser_post_linkedin(caption: str, images: list[Path]) -> str | None:
    """Fallback: post to LinkedIn via browser. Skipped in auto mode."""
    if AUTO_MODE:
        console.print("  [yellow]LinkedIn: no API credentials, browser fallback skipped (auto mode)[/yellow]")
        return None

    from playwright.sync_api import sync_playwright

    console.print("  [cyan]Using browser fallback for LinkedIn...[/cyan]")

    with sync_playwright() as p:
        CHROME_PROFILE_SOCIAL.mkdir(parents=True, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_SOCIAL),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("https://www.linkedin.com", wait_until="networkidle", timeout=30000)

            if "login" in page.url.lower():
                console.print("  [yellow]Please log in to LinkedIn manually, then press Enter.[/yellow]")
                prompt("")

            console.print("  [yellow]Navigate to GST Cranes page, create post, then press Enter.[/yellow]")
            prompt("")

            console.print(Panel(caption, title="Caption to paste", border_style="dim"))
            console.print("  [yellow]After posting, paste the post URL (or 'skip'):[/yellow]")

            post_url = prompt("  Post URL: ", "skip")
            if post_url.lower() == "skip":
                return None
            return post_url if post_url else None

        finally:
            context.close()

# ── Save Records ─────────────────────────────────────────────────────────────

def save_post_record(info: dict, platform: str, post_url: str | None, status: str):
    """Save a record of the social media post."""
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    brand = info.get("brand", "unknown").lower().replace(" ", "-")
    model = info.get("model", "unknown").lower().replace(" ", "-")

    record = {
        "platform": platform,
        "url": post_url,
        "status": status,
        "posted_at": datetime.now().isoformat(),
        "crane_info": info,
    }

    record_path = PUBLISHED_DIR / f"{date_str}-{platform}-{brand}-{model}.json"
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Post record saved: {record_path}")
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
            console.print("[red]No crane folders with bilgiler.txt found in yeni-vinc/[/red]")
            return None

        console.print("[bold]Available cranes:[/bold]")
        for i, f in enumerate(folders, 1):
            info = parse_bilgiler(f / "bilgiler.txt")
            label = f"{info.get('brand', '?')} {info.get('model', '?')} ({info.get('year', '?')})"
            console.print(f"  {i}. {f.name} — {label}")

        choice = prompt("\nSelect crane number (or folder name): ", "1")
        try:
            idx = int(choice) - 1
            folder = folders[idx]
        except (ValueError, IndexError):
            folder = INPUT_DIR / choice
            if not folder.exists():
                console.print("[red]Invalid selection[/red]")
                return None

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

# ── Platform Posting Orchestration ───────────────────────────────────────────

def post_to_platform(
    platform: str,
    info: dict,
    social_images: list[Path],
    web_images: list[Path],
    force_browser: bool,
) -> dict:
    """Post to a single platform. Returns result dict."""
    result = {"platform": platform, "status": "skipped", "url": None}

    # Choose caption and images per platform
    if platform == "linkedin":
        caption = generate_linkedin_caption(info)
        images = web_images[:4]  # LinkedIn: web images, up to 4
    elif platform == "instagram":
        caption = generate_social_caption(info)
        images = social_images[:10]  # Instagram: square images, up to 10
    else:
        caption = generate_social_caption(info)
        images = social_images  # Facebook: all social images

    if not images:
        console.print(f"  [yellow]No images available for {platform}[/yellow]")
        return result

    # Preview
    console.print()
    console.print(Panel(
        f"{caption}\n\n[dim]Images: {len(images)} ({images[0].name}, ...)[/dim]",
        title=f"Post Preview — {platform.title()}",
        border_style="cyan",
    ))

    choice = prompt(f"Post to {platform.title()}? (y/n/skip): ", "y").lower()

    if choice != "y":
        console.print(f"  [dim]Skipped {platform}[/dim]")
        return result

    # Attempt API first, then browser fallback
    post_url = None

    if not force_browser:
        if platform == "facebook":
            creds = get_meta_credentials()
            if creds:
                console.print(f"  [cyan]Posting to Facebook via API...[/cyan]")
                post_url = facebook_post_photos(creds, caption, images)
            else:
                console.print(f"  [yellow]Meta API credentials not found, using browser fallback[/yellow]")

        elif platform == "instagram":
            creds = get_meta_credentials()
            if creds and creds.get("instagram_account_id"):
                console.print(f"  [cyan]Posting to Instagram via API...[/cyan]")
                post_url = instagram_post_carousel(creds, caption, images)
            else:
                console.print(f"  [yellow]Instagram API not configured, using browser fallback[/yellow]")

        elif platform == "linkedin":
            creds = get_linkedin_credentials()
            if creds:
                console.print(f"  [cyan]Posting to LinkedIn via API...[/cyan]")
                post_url = linkedin_post(creds, caption, images)
            else:
                console.print(f"  [yellow]LinkedIn API not configured, using browser fallback[/yellow]")

    # Browser fallback
    if post_url is None:
        if platform == "facebook":
            post_url = browser_post_facebook(caption, images)
        elif platform == "instagram":
            post_url = browser_post_instagram(caption, images)
        elif platform == "linkedin":
            post_url = browser_post_linkedin(caption, images)

    if post_url:
        result["status"] = "posted"
        result["url"] = post_url
        save_post_record(info, platform, post_url, "posted")
        console.print(f"  [bold green]Posted to {platform.title()}![/bold green]")
        console.print(f"  URL: {post_url}")
    else:
        result["status"] = "failed"
        console.print(f"  [red]Failed to post to {platform.title()}[/red]")

    return result

# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--auto", is_flag=True, help="Fully automated, no prompts (for Claude Code)")
@click.option("--platform", type=click.Choice(PLATFORMS), default=None, help="Post to specific platform only")
@click.option("--browser", "force_browser", is_flag=True, help="Force browser mode (skip APIs)")
@click.option("--crane", "crane_folder", default=None, help="Crane folder name in yeni-vinc/")
@click.option("--check-auth", is_flag=True, help="Verify all API credentials")
def main(auto: bool, platform: str | None, force_browser: bool, crane_folder: str | None, check_auth: bool):
    """GST Cranes — Social Media Posting"""

    global AUTO_MODE
    AUTO_MODE = auto

    load_dotenv(ENV_FILE)

    console.print("[bold cyan]GST Cranes — Social Media Post[/bold cyan]")
    console.print()

    # Auth check mode
    if check_auth:
        status = check_all_credentials()
        table = Table(title="API Credentials Status")
        table.add_column("Platform")
        table.add_column("Status")
        table.add_column("Mode")

        for name, available in status.items():
            platform_name = name.replace("_api", "").title()
            if available:
                table.add_row(platform_name, "[green]Configured[/green]", "API")
            else:
                table.add_row(platform_name, "[yellow]Not configured[/yellow]", "Browser fallback")

        console.print(table)
        console.print()

        # Verify tokens that are configured
        meta = get_meta_credentials()
        if meta:
            if meta_verify_token(meta):
                console.print("[green]Meta token: valid[/green]")
            else:
                console.print("[red]Meta token: invalid or expired[/red]")

        li = get_linkedin_credentials()
        if li:
            if linkedin_verify_token(li):
                console.print("[green]LinkedIn token: valid[/green]")
            else:
                console.print("[red]LinkedIn token: invalid or expired[/red]")

        if not any(status.values()):
            console.print()
            console.print("See [bold]SOCIAL_SETUP.md[/bold] for credential setup instructions.")

        return

    # Select crane
    result = select_crane_folder(crane_folder)
    if not result:
        return
    folder, bilgiler = result

    brand = bilgiler.get("brand", "")
    model = bilgiler.get("model", "")
    console.print(f"[bold]Crane:[/bold] {bilgiler.get('year', '')} {brand} {model}")

    # Find images
    social_images = find_social_images(bilgiler)
    web_images = find_web_images(bilgiler)
    console.print(f"[bold]Images:[/bold] {len(social_images)} social, {len(web_images)} web")

    if not social_images and not web_images:
        console.print("[red]No processed images found. Run gorsel-hazirla.py first.[/red]")
        return

    # Show credential status
    status = check_all_credentials()
    for name, available in status.items():
        mode = "API" if available else "browser fallback"
        console.print(f"  {name.replace('_api', '').title()}: {mode}")
    console.print()

    # Determine which platforms to post to
    platforms_to_post = [platform] if platform else PLATFORMS

    # Post to each platform
    results = []
    for p in platforms_to_post:
        r = post_to_platform(p, bilgiler, social_images, web_images, force_browser)
        results.append(r)

    # Summary
    console.print()
    table = Table(title="Posting Summary")
    table.add_column("Platform", style="cyan")
    table.add_column("Status")
    table.add_column("URL", style="dim")

    for r in results:
        status_str = {
            "posted": "[green]Posted[/green]",
            "failed": "[red]Failed[/red]",
            "skipped": "[dim]Skipped[/dim]",
        }.get(r["status"], r["status"])
        table.add_row(r["platform"].title(), status_str, r.get("url") or "-")

    console.print(table)


if __name__ == "__main__":
    main()
