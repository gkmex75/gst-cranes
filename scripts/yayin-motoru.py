"""
yayin-motoru.py — Publish to Facebook, Instagram, LinkedIn via APIs.

Usage:
    python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "Post text"
    python scripts/yayin-motoru.py --platform instagram --image output/story.jpg --story
    python scripts/yayin-motoru.py --platform facebook,linkedin --image output/post.jpg --text "..."
    python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "..." --dry-run
"""

from typing import Optional, List, Tuple, Dict
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

import click
import requests
from dotenv import load_dotenv
from rich.console import Console

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
PAYLASILAN_FILE = DATA_DIR / "paylasilan.json"

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_yayin-motoru.log"

    logger = logging.getLogger("yayin-motoru")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ── Data ─────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_published(record: dict):
    """Append a publish record to paylasilan.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    records = load_json(PAYLASILAN_FILE)
    records.append(record)
    PAYLASILAN_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ── Facebook Publishing (Meta Graph API) ─────────────────────────────────────

def publish_facebook_post(image_path: Path, text: str) -> dict:
    """Publish a photo post to Facebook Page via Meta Graph API."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")

    if not token or not page_id:
        return {"success": False, "error": "META_PAGE_ACCESS_TOKEN or META_PAGE_ID not set in .env"}

    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"

    with open(image_path, "rb") as img:
        resp = requests.post(url, data={
            "message": text,
            "access_token": token,
        }, files={
            "source": img,
        }, timeout=60)

    if resp.status_code == 200:
        data = resp.json()
        post_id = data.get("post_id") or data.get("id")
        logger.info(f"Facebook post published: {post_id}")
        return {"success": True, "platform": "facebook", "post_id": post_id}
    else:
        error = resp.json().get("error", {}).get("message", resp.text)
        logger.error(f"Facebook publish failed: {error}")
        return {"success": False, "platform": "facebook", "error": error}


def publish_facebook_story(image_path: Path) -> dict:
    """Publish a story to Facebook Page (2-step: upload photo, then create story)."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")

    if not token or not page_id:
        return {"success": False, "error": "META credentials not set"}

    # Step 1: Upload photo as unpublished
    with open(image_path, "rb") as img:
        upload_resp = requests.post(
            f"https://graph.facebook.com/v21.0/{page_id}/photos",
            data={"published": "false", "access_token": token},
            files={"source": img},
            timeout=60
        )

    if upload_resp.status_code != 200:
        error = upload_resp.json().get("error", {}).get("message", upload_resp.text)
        return {"success": False, "platform": "facebook_story", "error": f"Photo upload failed: {error}"}

    photo_id = upload_resp.json().get("id")

    # Step 2: Create story with the uploaded photo
    story_resp = requests.post(
        f"https://graph.facebook.com/v21.0/{page_id}/photo_stories",
        data={"photo_id": photo_id, "access_token": token},
        timeout=60
    )

    if story_resp.status_code == 200:
        data = story_resp.json()
        post_id = data.get("post_id", "")
        logger.info(f"Facebook story published: {post_id}")
        return {"success": True, "platform": "facebook_story", "post_id": post_id}
    else:
        error = story_resp.json().get("error", {}).get("message", story_resp.text)
        logger.error(f"Facebook story failed: {error}")
        return {"success": False, "platform": "facebook_story", "error": error}


# ── Instagram Publishing (Meta Graph API) ────────────────────────────────────

def publish_instagram_post(image_path: Path, text: str) -> dict:
    """Publish a photo post to Instagram via Meta Graph API (container-based)."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    ig_id = os.getenv("META_INSTAGRAM_ACCOUNT_ID")

    if not token or not ig_id:
        return {"success": False, "error": "META_PAGE_ACCESS_TOKEN or META_INSTAGRAM_ACCOUNT_ID not set"}

    # Instagram requires a publicly accessible URL for the image
    # We need to upload the image to Facebook first, then use its URL
    # OR host it temporarily. For now, we upload to FB page (unpublished)
    # and use the resulting URL.

    page_id = os.getenv("META_PAGE_ID")

    # Step 1: Upload image to get a public URL via Facebook
    upload_url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    with open(image_path, "rb") as img:
        upload_resp = requests.post(upload_url, data={
            "published": "false",
            "access_token": token,
        }, files={
            "source": img,
        }, timeout=60)

    if upload_resp.status_code != 200:
        error = upload_resp.json().get("error", {}).get("message", upload_resp.text)
        return {"success": False, "platform": "instagram", "error": f"Image upload failed: {error}"}

    # Get the image URL from the uploaded photo
    photo_id = upload_resp.json().get("id")
    photo_url_resp = requests.get(
        f"https://graph.facebook.com/v21.0/{photo_id}",
        params={"fields": "images", "access_token": token},
        timeout=30
    )

    if photo_url_resp.status_code != 200:
        return {"success": False, "platform": "instagram", "error": "Could not get image URL"}

    images = photo_url_resp.json().get("images", [])
    if not images:
        return {"success": False, "platform": "instagram", "error": "No image URL returned"}

    image_url = images[0]["source"]

    # Step 2: Create Instagram media container
    container_url = f"https://graph.facebook.com/v21.0/{ig_id}/media"
    container_resp = requests.post(container_url, data={
        "image_url": image_url,
        "caption": text,
        "access_token": token,
    }, timeout=60)

    if container_resp.status_code != 200:
        error = container_resp.json().get("error", {}).get("message", container_resp.text)
        return {"success": False, "platform": "instagram", "error": f"Container creation failed: {error}"}

    creation_id = container_resp.json().get("id")

    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v21.0/{ig_id}/media_publish"
    publish_resp = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": token,
    }, timeout=60)

    if publish_resp.status_code == 200:
        media_id = publish_resp.json().get("id")
        logger.info(f"Instagram post published: {media_id}")
        return {"success": True, "platform": "instagram", "post_id": media_id}
    else:
        error = publish_resp.json().get("error", {}).get("message", publish_resp.text)
        logger.error(f"Instagram publish failed: {error}")
        return {"success": False, "platform": "instagram", "error": error}


def publish_instagram_story(image_path: Path) -> dict:
    """Publish a story to Instagram via Meta Graph API."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    ig_id = os.getenv("META_INSTAGRAM_ACCOUNT_ID")
    page_id = os.getenv("META_PAGE_ID")

    if not token or not ig_id:
        return {"success": False, "error": "META credentials not set"}

    # Upload image to get public URL
    upload_url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    with open(image_path, "rb") as img:
        upload_resp = requests.post(upload_url, data={
            "published": "false",
            "access_token": token,
        }, files={"source": img}, timeout=60)

    if upload_resp.status_code != 200:
        return {"success": False, "platform": "instagram_story", "error": "Image upload failed"}

    photo_id = upload_resp.json().get("id")
    photo_url_resp = requests.get(
        f"https://graph.facebook.com/v21.0/{photo_id}",
        params={"fields": "images", "access_token": token}, timeout=30
    )
    images = photo_url_resp.json().get("images", [])
    if not images:
        return {"success": False, "platform": "instagram_story", "error": "No image URL"}
    image_url = images[0]["source"]

    # Create story container
    container_resp = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media",
        data={"image_url": image_url, "media_type": "STORIES", "access_token": token},
        timeout=60
    )

    if container_resp.status_code != 200:
        error = container_resp.json().get("error", {}).get("message", container_resp.text)
        return {"success": False, "platform": "instagram_story", "error": error}

    creation_id = container_resp.json().get("id")

    publish_resp = requests.post(
        f"https://graph.facebook.com/v21.0/{ig_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=60
    )

    if publish_resp.status_code == 200:
        media_id = publish_resp.json().get("id")
        logger.info(f"Instagram story published: {media_id}")
        return {"success": True, "platform": "instagram_story", "post_id": media_id}
    else:
        error = publish_resp.json().get("error", {}).get("message", publish_resp.text)
        return {"success": False, "platform": "instagram_story", "error": error}


# ── LinkedIn Publishing ──────────────────────────────────────────────────────

def publish_linkedin_post(image_path: Path, text: str) -> dict:
    """Publish a photo post to LinkedIn personal profile."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    member_id = os.getenv("LINKEDIN_ORG_ID")  # Actually member ID (person URN sub)

    if not token or not member_id:
        return {"success": False, "error": "LINKEDIN_ACCESS_TOKEN or LINKEDIN_ORG_ID not set"}

    author_urn = f"urn:li:person:{member_id}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Step 1: Register image upload
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    register_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }

    reg_resp = requests.post(register_url, headers=headers, json=register_body, timeout=30)

    if reg_resp.status_code != 200:
        error = reg_resp.text[:200]
        return {"success": False, "platform": "linkedin", "error": f"Register failed: {error}"}

    reg_data = reg_resp.json()
    upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset = reg_data["value"]["asset"]

    # Step 2: Upload image binary
    with open(image_path, "rb") as img:
        upload_resp = requests.put(upload_url, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/jpeg",
        }, data=img, timeout=60)

    if upload_resp.status_code not in (200, 201):
        return {"success": False, "platform": "linkedin", "error": "Image upload failed"}

    # Step 3: Create post with image
    post_url = "https://api.linkedin.com/v2/ugcPosts"
    post_body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "media": asset,
                }]
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    post_resp = requests.post(post_url, headers=headers, json=post_body, timeout=30)

    if post_resp.status_code in (200, 201):
        post_id = post_resp.headers.get("X-RestLi-Id", "")
        logger.info(f"LinkedIn post published: {post_id}")
        return {"success": True, "platform": "linkedin", "post_id": post_id}
    else:
        error = post_resp.text[:200]
        logger.error(f"LinkedIn publish failed: {error}")
        return {"success": False, "platform": "linkedin", "error": error}


# ── Orchestrator ─────────────────────────────────────────────────────────────

PUBLISHERS = {
    "facebook": publish_facebook_post,
    "instagram": publish_instagram_post,
    "linkedin": publish_linkedin_post,
}

STORY_PUBLISHERS = {
    "facebook": publish_facebook_story,
    "instagram": publish_instagram_story,
}


def publish_to_platforms(platforms: list[str], image_path: Path, text: str, is_story: bool, dry_run: bool) -> List[dict]:
    """Publish to multiple platforms. Returns list of results."""
    results = []

    for platform in platforms:
        if dry_run:
            console.print(f"  [yellow]DRY RUN — would publish to {platform}[/yellow]")
            results.append({"success": True, "platform": platform, "dry_run": True})
            continue

        if is_story:
            fn = STORY_PUBLISHERS.get(platform)
            if fn:
                result = fn(image_path)
            else:
                result = {"success": False, "platform": platform, "error": f"Stories not supported on {platform}"}
        else:
            fn = PUBLISHERS.get(platform)
            if fn:
                result = fn(image_path, text)
            else:
                result = {"success": False, "platform": platform, "error": f"Unknown platform: {platform}"}

        results.append(result)

        if result["success"]:
            console.print(f"  [green]{platform}: Published ✓[/green]")
        else:
            console.print(f"  [red]{platform}: Failed — {result.get('error', 'unknown')}[/red]")

    return results


# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--platform", required=True, help="Platforms: all, facebook, instagram, linkedin (comma-separated)")
@click.option("--image", "image_path", required=True, type=click.Path(exists=True), help="Image file to publish")
@click.option("--text", default="", help="Post text/caption")
@click.option("--story", is_flag=True, help="Publish as story instead of post")
@click.option("--dry-run", is_flag=True, help="Preview without publishing")
@click.option("--crane-id", default=None, help="Crane ID for tracking in paylasilan.json")
def main(platform: str, image_path: str, text: str, story: bool, dry_run: bool, crane_id: Optional[str]):
    """GST Marketing — Publishing Engine"""
    load_dotenv(PROJECT_ROOT / ".env")

    console.print("[bold cyan]GST Marketing — Publisher[/bold cyan]")

    # Parse platforms
    if platform == "all":
        platforms = ["facebook", "instagram", "linkedin"]
    else:
        platforms = [p.strip() for p in platform.split(",")]

    image = Path(image_path)
    console.print(f"  Image: {image.name}")
    console.print(f"  Platforms: {', '.join(platforms)}")
    console.print(f"  Type: {'Story' if story else 'Post'}")
    if text:
        console.print(f"  Text: {text[:100]}...")

    results = publish_to_platforms(platforms, image, text, story, dry_run)

    # Track in paylasilan.json
    if not dry_run and any(r["success"] for r in results):
        record = {
            "crane_id": crane_id,
            "timestamp": datetime.now().timestamp(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": "story" if story else "post",
            "platforms": {r["platform"]: r.get("post_id", "") for r in results if r["success"]},
            "text": text[:200] if text else "",
            "image": image.name,
        }
        save_published(record)
        console.print(f"\n  [dim]Recorded in {PAYLASILAN_FILE}[/dim]")

    # Summary
    ok = sum(1 for r in results if r["success"])
    fail = sum(1 for r in results if not r["success"])
    if dry_run:
        console.print(f"\n[yellow]DRY RUN — nothing published[/yellow]")
    else:
        console.print(f"\n[bold]Results: {ok} published, {fail} failed[/bold]")


if __name__ == "__main__":
    main()


# --- SP4 wrapper (added by promote-api integration) ---
# Loaded by promote-api/runners/social.py. The story_image_path parameter is what
# lets promote-api forward the Premium Dealer Ad STORY creative end-to-end; it is
# detected via inspect.signature on the promote-api side, so keep the name stable.
def _safe_publish(fn, *args) -> dict:
    """Call a publish_* helper, turning a RAISED exception (network/timeout/file
    error) into the same {"success": False, "error": ...} contract the helpers
    already use for API failures. This keeps one platform crashing from aborting
    the others or faking a post id — and is what guarantees a story failure can
    never erase feed success even under an unexpected exception."""
    try:
        return fn(*args)
    except Exception as e:  # one platform must not sink the rest
        return {"success": False, "error": str(e)}


def post_to_all(captions: dict, image_path: str, story_image_path: str | None = None) -> dict:
    """Publish the feed creative to Facebook, Instagram and LinkedIn organic using
    the platform-specific captions, and — when story_image_path is given — ALSO
    publish the story creative to Facebook + Instagram (never LinkedIn).

    captions = {"fb": "<fb copy>", "ig": "<ig caption+tags>", "linkedin": "<li copy>"}
    image_path        = feed image (already downloaded), e.g. "/tmp/post.jpg"
    story_image_path  = optional 1080x1920 story image, e.g. "/tmp/story.jpg"

    Returns (feed keys are ALWAYS present; a missing post id is None, never faked):
        {
          "fb_post_id": str | None,
          "ig_post_id": str | None,
          "linkedin_post_urn": str | None,
          "errors": {"<platform>": "<message>", ...},      # only if a feed post failed
          "stories": {                                      # only if story_image_path given
            "facebook_story_post_id": str | None,
            "instagram_story_post_id": str | None,
            "errors": {"<platform>": "<message>", ...},     # only if a story post failed
          },
        }

    A story failure never erases feed success (and vice-versa). Backward compatible:
    called as post_to_all(captions, image_path) it behaves exactly feed-only — no
    "stories" key. Wraps the existing publish_* helpers; performs real API calls
    when invoked (mock the helpers in tests).
    """
    img = Path(image_path)
    fb = _safe_publish(publish_facebook_post, img, captions["fb"])
    ig = _safe_publish(publish_instagram_post, img, captions["ig"])
    li = _safe_publish(publish_linkedin_post, img, captions["linkedin"])

    result: dict = {
        "fb_post_id": fb.get("post_id") if fb.get("success") else None,
        "ig_post_id": ig.get("post_id") if ig.get("success") else None,
        "linkedin_post_urn": li.get("post_id") if li.get("success") else None,
    }
    feed_errors = {
        name: res.get("error", "unknown error")
        for name, res in (("facebook", fb), ("instagram", ig), ("linkedin", li))
        if not res.get("success")
    }
    if feed_errors:
        result["errors"] = feed_errors

    # Story: Facebook + Instagram only — there is no LinkedIn story publisher.
    if story_image_path:
        story_img = Path(story_image_path)
        fb_story = _safe_publish(publish_facebook_story, story_img)
        ig_story = _safe_publish(publish_instagram_story, story_img)
        stories: dict = {
            "facebook_story_post_id": fb_story.get("post_id") if fb_story.get("success") else None,
            "instagram_story_post_id": ig_story.get("post_id") if ig_story.get("success") else None,
        }
        story_errors = {
            name: res.get("error", "unknown error")
            for name, res in (("facebook_story", fb_story), ("instagram_story", ig_story))
            if not res.get("success")
        }
        if story_errors:
            stories["errors"] = story_errors
        result["stories"] = stories

    return result
