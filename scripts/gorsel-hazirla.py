"""
gorsel-hazirla.py — Image processing for GST Cranes listings.

Uses Adobe Firefly Generative Remove API to clean text/logos from crane photos,
applies local color enhancement, and exports web + social media versions.

Usage:
    python scripts/gorsel-hazirla.py                  # Process all images in yeni-vinc/
    python scripts/gorsel-hazirla.py --check-auth     # Verify Adobe credentials
    python scripts/gorsel-hazirla.py --skip-firefly   # Skip API calls, local processing only
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import click
import cv2
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageEnhance
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
INPUT_DIR = PROJECT_ROOT / "yeni-vinc"
OUTPUT_DIR = PROJECT_ROOT / "processed"
LOG_DIR = PROJECT_ROOT / "logs"
TOKEN_CACHE = PROJECT_ROOT / ".adobe-token-cache.json"
ENV_FILE = PROJECT_ROOT / ".env"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_gorsel-hazirla.log"

    logger = logging.getLogger("gorsel-hazirla")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ── bilgiler.txt Parser ─────────────────────────────────────────────────────

def parse_bilgiler(bilgiler_path: Path) -> dict:
    """Parse a bilgiler.txt key=value file."""
    data = {}
    for line in bilgiler_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def find_crane_folders() -> list[Path]:
    """Find subfolders in yeni-vinc/ that contain images."""
    folders = []
    if not INPUT_DIR.exists():
        return folders
    for item in sorted(INPUT_DIR.iterdir()):
        if item.is_dir():
            images = [f for f in item.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
            if images:
                folders.append(item)
    return folders


def get_crane_images(folder: Path) -> list[Path]:
    """Get all image files from a crane folder."""
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)


def build_output_prefix(bilgiler: dict) -> str:
    """Build filename prefix from crane info: brand-model."""
    brand = bilgiler.get("brand", "unknown").lower().replace(" ", "-")
    model = bilgiler.get("model", "unknown").lower().replace(" ", "-")
    return f"{brand}-{model}"

# ── Adobe Firefly API ────────────────────────────────────────────────────────

class AdobeFireflyClient:
    """Client for Adobe Firefly Services API."""

    TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
    UPLOAD_URL = "https://firefly-api.adobe.io/v2/storage/image"
    REMOVE_URL = "https://firefly-api.adobe.io/v2/images/generate-remove"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = 0

    def authenticate(self) -> bool:
        """Get or refresh OAuth access token."""
        # Check cache first
        if self._load_cached_token():
            return True

        logger.info("Requesting new Adobe access token")
        try:
            resp = requests.post(self.TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "openid,AdobeID,firefly_api,ff_apis",
            }, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Adobe auth failed: {e}")
            return False

        token_data = resp.json()
        self.access_token = token_data["access_token"]
        self.token_expiry = time.time() + token_data.get("expires_in", 86400) - 300

        self._save_cached_token()
        logger.info("Adobe authentication successful")
        return True

    def _load_cached_token(self) -> bool:
        if not TOKEN_CACHE.exists():
            return False
        try:
            cache = json.loads(TOKEN_CACHE.read_text())
            if cache.get("expiry", 0) > time.time():
                self.access_token = cache["access_token"]
                self.token_expiry = cache["expiry"]
                logger.info("Using cached Adobe access token")
                return True
        except (json.JSONDecodeError, KeyError):
            pass
        return False

    def _save_cached_token(self):
        TOKEN_CACHE.write_text(json.dumps({
            "access_token": self.access_token,
            "expiry": self.token_expiry,
        }))

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-api-key": self.client_id,
        }

    def upload_image(self, image_path: Path) -> str | None:
        """Upload an image to Adobe storage. Returns the upload ID/reference."""
        logger.info(f"Uploading {image_path.name} to Adobe storage")
        mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    self.UPLOAD_URL,
                    headers={**self._headers(), "Content-Type": mime},
                    data=f,
                    timeout=120,
                )
            resp.raise_for_status()
            result = resp.json()
            image_id = result.get("images", [{}])[0].get("id")
            logger.info(f"Uploaded {image_path.name} → {image_id}")
            return image_id
        except requests.RequestException as e:
            logger.error(f"Upload failed for {image_path.name}: {e}")
            return None

    def generative_remove(self, image_id: str, mask_b64: str) -> bytes | None:
        """Call Firefly Generative Remove with a mask. Returns result image bytes."""
        logger.info(f"Calling Generative Remove for {image_id}")

        payload = {
            "image": {"source": {"uploadId": image_id}},
            "mask": {"source": {"base64": mask_b64}},
        }

        try:
            resp = requests.post(
                self.REMOVE_URL,
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )

            # Handle rate limiting
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                console.print(f"[yellow]Rate limited, waiting {retry_after}s...[/yellow]")
                time.sleep(retry_after)
                resp = requests.post(
                    self.REMOVE_URL,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )

            resp.raise_for_status()
            result = resp.json()

            # Download the result image
            output_url = result.get("outputs", [{}])[0].get("image", {}).get("url")
            if output_url:
                img_resp = requests.get(output_url, headers=self._headers(), timeout=120)
                img_resp.raise_for_status()
                logger.info("Generative Remove complete")
                return img_resp.content

        except requests.RequestException as e:
            logger.error(f"Generative Remove failed: {e}")
        return None

# ── Local Text Detection (OpenCV EAST) ───────────────────────────────────────

EAST_MODEL_URL = "https://raw.githubusercontent.com/oyyd/frozen_east_text_detection/master/frozen_east_text_detection.pb"
EAST_MODEL_PATH = PROJECT_ROOT / "scripts" / "frozen_east_text_detection.pb"


def download_east_model():
    """Download the EAST text detection model if not present."""
    if EAST_MODEL_PATH.exists():
        return
    console.print("[cyan]Downloading EAST text detection model (one-time)...[/cyan]")
    logger.info("Downloading EAST model")
    resp = requests.get(EAST_MODEL_URL, timeout=120, stream=True)
    resp.raise_for_status()
    EAST_MODEL_PATH.write_bytes(resp.content)
    logger.info("EAST model downloaded")


def detect_text_regions(image_path: Path) -> tuple[np.ndarray | None, int]:
    """
    Detect text regions in an image using OpenCV EAST detector.
    Returns (mask_image, region_count). Mask is white where text was found.
    """
    download_east_model()

    img = cv2.imread(str(image_path))
    if img is None:
        return None, 0

    orig_h, orig_w = img.shape[:2]

    # EAST requires dimensions multiples of 32
    new_w = (orig_w // 32) * 32
    new_h = (orig_h // 32) * 32
    if new_w == 0:
        new_w = 32
    if new_h == 0:
        new_h = 32

    ratio_w = orig_w / new_w
    ratio_h = orig_h / new_h

    resized = cv2.resize(img, (new_w, new_h))
    blob = cv2.dnn.blobFromImage(resized, 1.0, (new_w, new_h), (123.68, 116.78, 103.94), swapRB=True, crop=False)

    net = cv2.dnn.readNet(str(EAST_MODEL_PATH))
    output_layers = ["feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"]
    net.setInput(blob)
    scores, geometry = net.forward(output_layers)

    # Decode detections
    rects, confidences = _decode_east(scores, geometry, min_confidence=0.5)

    if len(rects) == 0:
        return None, 0

    # Create mask at original resolution
    mask = np.zeros((orig_h, orig_w), dtype=np.uint8)

    for (start_x, start_y, end_x, end_y) in rects:
        # Scale back to original size with padding
        pad = 15
        x1 = max(0, int(start_x * ratio_w) - pad)
        y1 = max(0, int(start_y * ratio_h) - pad)
        x2 = min(orig_w, int(end_x * ratio_w) + pad)
        y2 = min(orig_h, int(end_y * ratio_h) + pad)
        mask[y1:y2, x1:x2] = 255

    return mask, len(rects)


def _decode_east(scores, geometry, min_confidence=0.5):
    """Decode EAST text detector output into bounding boxes."""
    num_rows, num_cols = scores.shape[2:4]
    rects = []
    confidences = []

    for y in range(num_rows):
        scores_data = scores[0, 0, y]
        x0 = geometry[0, 0, y]
        x1 = geometry[0, 1, y]
        x2 = geometry[0, 2, y]
        x3 = geometry[0, 3, y]
        angles = geometry[0, 4, y]

        for x in range(num_cols):
            if scores_data[x] < min_confidence:
                continue

            offset_x = x * 4.0
            offset_y = y * 4.0

            h = x0[x] + x2[x]
            w = x1[x] + x3[x]

            start_x = int(offset_x - x1[x])
            start_y = int(offset_y - x0[x])
            end_x = int(offset_x + x3[x])
            end_y = int(offset_y + x2[x])

            rects.append((start_x, start_y, end_x, end_y))
            confidences.append(float(scores_data[x]))

    # Apply non-max suppression
    if len(rects) == 0:
        return [], []

    boxes = np.array(rects)
    confs = np.array(confidences)
    indices = cv2.dnn.NMSBoxes(
        [(x, y, w - x, h - y) for (x, y, w, h) in boxes],
        confs.tolist(), min_confidence, 0.4
    )

    if len(indices) == 0:
        return [], []

    indices = indices.flatten()
    return [rects[i] for i in indices], [confidences[i] for i in indices]


def mask_to_base64(mask: np.ndarray) -> str:
    """Convert a mask numpy array to base64-encoded PNG."""
    import base64
    _, buffer = cv2.imencode(".png", mask)
    return base64.b64encode(buffer).decode("utf-8")

# ── Color Enhancement (Pillow) ───────────────────────────────────────────────

def enhance_image(img: Image.Image) -> Image.Image:
    """Apply brightness +10%, contrast +5%, saturation +5%."""
    img = ImageEnhance.Brightness(img).enhance(1.10)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = ImageEnhance.Color(img).enhance(1.05)
    return img

# ── Export Versions ──────────────────────────────────────────────────────────

def export_web(img: Image.Image, output_path: Path):
    """Export web version: max 1920px width, 85% JPEG quality."""
    w, h = img.size
    if w > 1920:
        ratio = 1920 / w
        img = img.resize((1920, int(h * ratio)), Image.LANCZOS)
    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=85, optimize=True)


def export_social(img: Image.Image, output_path: Path):
    """Export social version: 1080x1080 square, smart center crop."""
    w, h = img.size
    # Crop to square from center, biased slightly upward for cranes
    side = min(w, h)
    left = (w - side) // 2
    top = max(0, (h - side) // 2 - int(side * 0.05))  # slight upward bias
    if top + side > h:
        top = h - side

    img = img.crop((left, top, left + side, top + side))
    img = img.resize((1080, 1080), Image.LANCZOS)
    img = img.convert("RGB")
    img.save(output_path, "JPEG", quality=90, optimize=True)

# ── Main Processing ──────────────────────────────────────────────────────────

def process_crane_folder(
    folder: Path,
    bilgiler: dict,
    firefly_client: AdobeFireflyClient | None,
    skip_firefly: bool,
) -> list[dict]:
    """Process all images in one crane folder. Returns list of result dicts."""
    images = get_crane_images(folder)
    prefix = build_output_prefix(bilgiler)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    crane_dir = OUTPUT_DIR / prefix
    crane_dir.mkdir(parents=True, exist_ok=True)
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Processing {folder.name}", total=len(images))

        for idx, image_path in enumerate(images, 1):
            num = f"{idx:02d}"
            result = {"file": image_path.name, "status": "ok", "details": []}

            try:
                # Step 1: Text removal via Firefly
                if not skip_firefly and firefly_client:
                    mask, region_count = detect_text_regions(image_path)
                    if mask is not None and region_count > 0:
                        result["details"].append(f"detected {region_count} text region(s)")
                        mask_b64 = mask_to_base64(mask)
                        image_id = firefly_client.upload_image(image_path)
                        if image_id:
                            cleaned_bytes = firefly_client.generative_remove(image_id, mask_b64)
                            if cleaned_bytes:
                                # Use cleaned image for further processing
                                from io import BytesIO
                                pil_img = Image.open(BytesIO(cleaned_bytes))
                                result["details"].append(f"removed {region_count} text region(s) via Firefly")
                            else:
                                pil_img = Image.open(image_path)
                                result["details"].append("Firefly remove failed, using original")
                        else:
                            pil_img = Image.open(image_path)
                            result["details"].append("upload failed, using original")
                    else:
                        pil_img = Image.open(image_path)
                        result["details"].append("no text detected")
                else:
                    pil_img = Image.open(image_path)
                    if skip_firefly:
                        result["details"].append("Firefly skipped")

                # Step 2: Color enhancement
                pil_img = enhance_image(pil_img)
                result["details"].append("color enhanced")

                # Step 3: Export
                web_path = crane_dir / f"{prefix}-{num}-web.jpg"
                social_path = crane_dir / f"{prefix}-{num}-social.jpg"

                export_web(pil_img, web_path)
                export_social(pil_img, social_path)

                result["web"] = web_path.name
                result["social"] = social_path.name
                result["details"].append("exported web + social")

                logger.info(f"Processed {image_path.name} → {web_path.name}, {social_path.name}")

            except Exception as e:
                result["status"] = "error"
                result["details"] = [str(e)]
                logger.error(f"Failed to process {image_path.name}: {e}")

            progress.advance(task)
            results.append(result)

            # Print per-image status
            status_icon = "[green]OK[/green]" if result["status"] == "ok" else "[red]FAIL[/red]"
            detail_str = ", ".join(result["details"])
            console.print(f"  {status_icon} {image_path.name} -> {detail_str}")

    return results


def print_summary(all_results: dict[str, list[dict]]):
    """Print a summary table of all processed images."""
    table = Table(title="Processing Summary")
    table.add_column("Crane", style="cyan")
    table.add_column("File", style="white")
    table.add_column("Status", style="white")
    table.add_column("Web Output", style="green")
    table.add_column("Social Output", style="green")
    table.add_column("Details", style="dim")

    total = 0
    ok = 0
    for crane_name, results in all_results.items():
        for r in results:
            total += 1
            status = "[green]OK[/green]" if r["status"] == "ok" else "[red]FAIL[/red]"
            if r["status"] == "ok":
                ok += 1
            table.add_row(
                crane_name,
                r["file"],
                status,
                r.get("web", "-"),
                r.get("social", "-"),
                ", ".join(r["details"]),
            )

    console.print()
    console.print(table)
    console.print(f"\n[bold]Total: {ok}/{total} images processed successfully[/bold]")


def get_firefly_client() -> AdobeFireflyClient | None:
    """Initialize and authenticate the Firefly client."""
    load_dotenv(ENV_FILE)
    client_id = os.getenv("ADOBE_CLIENT_ID")
    client_secret = os.getenv("ADOBE_CLIENT_SECRET")

    if not client_id or not client_secret:
        console.print("[yellow]Adobe credentials not found in .env[/yellow]")
        console.print()
        console.print("To set up Adobe Firefly API:")
        console.print("  1. Go to https://developer.adobe.com/console")
        console.print("  2. Create project -> Add Firefly Services API")
        console.print("  3. Generate OAuth Server-to-Server credentials")
        console.print("  4. Copy Client ID and Secret to ~/gst-cranes/.env")
        console.print()
        console.print("See ADOBE_SETUP.md for detailed instructions.")
        console.print("[dim]You can run with --skip-firefly to skip text removal.[/dim]")
        return None

    client = AdobeFireflyClient(client_id, client_secret)
    if not client.authenticate():
        console.print("[red]Adobe authentication failed. Check your credentials.[/red]")
        return None

    console.print("[green]Adobe Firefly authenticated[/green]")
    return client

# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--auto", is_flag=True, help="Fully automated, no prompts (for Claude Code)")
@click.option("--check-auth", is_flag=True, help="Only verify Adobe API credentials")
@click.option("--skip-firefly", is_flag=True, help="Skip Firefly API, local processing only")
def main(auto: bool, check_auth: bool, skip_firefly: bool):
    """GST Cranes — Image Processing Script"""

    console.print("[bold cyan]GST Cranes — Image Processor[/bold cyan]")
    console.print()

    # Auth-only mode
    if check_auth:
        client = get_firefly_client()
        if client:
            console.print("[bold green]Authentication successful![/bold green]")
        else:
            console.print("[bold red]Authentication failed.[/bold red]")
            sys.exit(1)
        return

    # Find crane folders
    folders = find_crane_folders()
    if not folders:
        console.print("[red]No crane folders with images found in yeni-vinc/[/red]")
        console.print("[dim]Create a subfolder with images and bilgiler.txt, e.g.:[/dim]")
        console.print("[dim]  yeni-vinc/liebherr-ltm-1090/bilgiler.txt[/dim]")
        console.print("[dim]  yeni-vinc/liebherr-ltm-1090/photo1.jpg[/dim]")
        sys.exit(1)

    # Initialize Firefly if needed
    firefly_client = None
    if not skip_firefly:
        firefly_client = get_firefly_client()
        if not firefly_client:
            console.print("[yellow]Continuing without Firefly (local processing only)[/yellow]")
            skip_firefly = True

    # Process each crane folder
    all_results = {}
    total_images = sum(len(get_crane_images(f)) for f in folders)
    console.print(f"Found [bold]{len(folders)}[/bold] crane(s) with [bold]{total_images}[/bold] images total")

    if not skip_firefly:
        console.print("Images will be processed via Adobe Firefly + local enhancement")
    else:
        console.print("Images will be processed with local enhancement only (no Firefly)")
    console.print()

    for folder in folders:
        bilgiler_path = folder / "bilgiler.txt"
        if not bilgiler_path.exists():
            console.print(f"[red]Missing bilgiler.txt in {folder.name}/[/red]")
            console.print(f"[dim]Copy sablonlar/bilgiler-ornek.txt to {folder}/bilgiler.txt and fill it in[/dim]")
            continue

        bilgiler = parse_bilgiler(bilgiler_path)

        # Validate required fields
        required = ["brand", "model"]
        missing = [f for f in required if not bilgiler.get(f)]
        if missing:
            console.print(f"[red]Missing fields in {folder.name}/bilgiler.txt: {', '.join(missing)}[/red]")
            continue

        console.print(f"[bold]Processing: {bilgiler.get('brand')} {bilgiler.get('model')}[/bold]")
        results = process_crane_folder(folder, bilgiler, firefly_client, skip_firefly)
        all_results[folder.name] = results

    # Summary
    if all_results:
        print_summary(all_results)
        console.print(f"\nOutput saved to: [cyan]{OUTPUT_DIR}[/cyan]")
    else:
        console.print("[yellow]No images were processed.[/yellow]")


if __name__ == "__main__":
    main()
