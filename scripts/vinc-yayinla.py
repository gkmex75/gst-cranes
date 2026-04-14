"""
vinc-yayinla.py — Main orchestrator for publishing crane listings.

Runs the full pipeline: image processing -> Hercules -> Machinery Line -> Social Media.

Usage:
    python scripts/vinc-yayinla.py --auto --crane <folder>       # Fully automated (for Claude Code)
    python scripts/vinc-yayinla.py --crane <folder>              # Interactive with confirmations
    python scripts/vinc-yayinla.py --auto --skip-images          # Auto, reuse processed images
    python scripts/vinc-yayinla.py --auto --only hercules,social # Auto, specific steps
    python scripts/vinc-yayinla.py --dry-run --crane <folder>    # Preview only
"""

import json
import shutil
import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path.home() / "gst-cranes"
INPUT_DIR = PROJECT_ROOT / "yeni-vinc"
PROCESSED_DIR = PROJECT_ROOT / "processed"
PUBLISHED_DIR = PROJECT_ROOT / "yayinlanan"
LOG_DIR = PROJECT_ROOT / "logs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
ENV_FILE = PROJECT_ROOT / ".env"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

STEPS = {
    "images": {
        "name": "Image Processing",
        "script": "gorsel-hazirla.py",
        "description": "Process images via Adobe Firefly + local enhancement",
        "extra_args": ["--skip-firefly"],  # Default to skip firefly for now
    },
    "hercules": {
        "name": "Hercules Upload",
        "script": "hercules-upload.py",
        "description": "Upload listing to hercules.app/dashboard via AI chat",
        "extra_args": [],
    },
    "machineryline": {
        "name": "Machinery Line Upload",
        "script": "machineryline-upload.py",
        "description": "Upload listing to machineryline.com",
        "extra_args": [],
    },
    "social": {
        "name": "Social Media",
        "script": "sosyal-medya-post.py",
        "description": "Post to Facebook, Instagram, LinkedIn",
        "extra_args": [],
    },
}

STEP_ORDER = ["images", "hercules", "machineryline", "social"]

console = Console()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"{timestamp}_publish.log"

    logger = logging.getLogger("vinc-yayinla")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    logger.info(f"Session log: {log_file}")
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

# ── Crane Folder Selection ───────────────────────────────────────────────────

def select_crane_folder(folder_name: str | None, auto: bool) -> tuple[Path, dict] | None:
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

        if auto or len(folders) == 1:
            folder = folders[0]
            console.print(f"[dim]Selected: {folder.name}[/dim]")
        else:
            console.print("[bold]Available cranes:[/bold]")
            for i, f in enumerate(folders, 1):
                info = parse_bilgiler(f / "bilgiler.txt")
                images = [x for x in f.iterdir() if x.suffix.lower() in IMAGE_EXTENSIONS]
                label = f"{info.get('brand', '?')} {info.get('model', '?')} ({info.get('year', '?')}) — {len(images)} photos"
                console.print(f"  {i}. {f.name} — {label}")

            choice = input("\nSelect crane number: ").strip()
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

# ── Summary ──────────────────────────────────────────────────────────────────

def generate_title(info: dict) -> str:
    return f"{info.get('year', '')} {info.get('brand', '')} {info.get('model', '')} - {info.get('capacity_tons', '')}t Mobile Crane"


def show_summary(folder: Path, bilgiler: dict, steps_to_run: list[str]):
    images = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
    title = generate_title(bilgiler)

    console.print(f"[bold]{title}[/bold]")
    console.print(f"  Price: EUR {bilgiler.get('price_eur', '')}")
    console.print(f"  Photos: {len(images)}")
    console.print(f"  Steps: {', '.join(steps_to_run)}")

# ── Step Execution ───────────────────────────────────────────────────────────

def run_step(step_key: str, crane_folder: str, dry_run: bool) -> bool:
    """Run a single pipeline step. Returns True if successful."""
    step = STEPS[step_key]
    script_path = SCRIPTS_DIR / step["script"]

    if not script_path.exists():
        console.print(f"[red]Script not found: {script_path}[/red]")
        return False

    cmd = [str(VENV_PYTHON), str(script_path)]

    # Add --auto flag to sub-scripts
    cmd.append("--auto")

    # Add crane folder for scripts that need it
    if step_key in ("hercules", "machineryline", "social"):
        cmd.extend(["--crane", crane_folder])

    # Add extra args (like --skip-firefly)
    cmd.extend(step["extra_args"])

    if dry_run:
        console.print(f"  [yellow]DRY RUN — would run: {step['name']}[/yellow]")
        return True

    logger.info(f"Running: {' '.join(cmd)}")
    console.print(f"  Running {step['name']}...")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=600,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(f"{step_key}: success")
            console.print(f"  [green]{step['name']}: OK[/green]")
            return True
        else:
            logger.error(f"{step_key}: failed (exit {result.returncode})")
            logger.error(f"stderr: {result.stderr[-500:]}")
            console.print(f"  [red]{step['name']}: FAILED[/red]")
            if result.stderr:
                console.print(f"  [dim]{result.stderr[-200:]}[/dim]")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"{step_key}: timeout")
        console.print(f"  [red]{step['name']}: TIMEOUT[/red]")
        return False
    except Exception as e:
        logger.error(f"{step_key}: error: {e}")
        console.print(f"  [red]{step['name']}: ERROR — {e}[/red]")
        return False

# ── Archive ──────────────────────────────────────────────────────────────────

def archive_crane(folder: Path, bilgiler: dict) -> Path:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    brand = bilgiler.get("brand", "unknown").lower().replace(" ", "-")
    model = bilgiler.get("model", "unknown").lower().replace(" ", "-")

    archive_name = f"{date_str}-{brand}-{model}"
    archive_path = PUBLISHED_DIR / archive_name

    if archive_path.exists():
        archive_path = PUBLISHED_DIR / f"{archive_name}-{datetime.now().strftime('%H%M%S')}"

    shutil.move(str(folder), str(archive_path))
    logger.info(f"Archived: {folder.name} -> {archive_path}")
    return archive_path

# ── Final Report ─────────────────────────────────────────────────────────────

def collect_publish_records(bilgiler: dict) -> list[dict]:
    if not PUBLISHED_DIR.exists():
        return []

    brand = bilgiler.get("brand", "").lower().replace(" ", "-")
    model = bilgiler.get("model", "").lower().replace(" ", "-")
    today = datetime.now().strftime("%Y-%m-%d")

    records = []
    for f in PUBLISHED_DIR.iterdir():
        if f.suffix == ".json" and today in f.name and brand in f.name and model in f.name:
            try:
                records.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
    return records


def generate_report(bilgiler: dict, step_results: dict[str, str]) -> dict:
    """Generate and save the final report. Returns report dict."""
    title = generate_title(bilgiler)
    records = collect_publish_records(bilgiler)

    report = {
        "crane": title,
        "published_at": datetime.now().isoformat(),
        "steps": step_results,
        "records": records,
        "bilgiler": bilgiler,
    }

    # Print summary
    console.print()
    console.print(Rule(f"Report — {title}", style="bold green"))

    table = Table()
    table.add_column("Step", style="bold")
    table.add_column("Result")

    for step_key in STEP_ORDER:
        if step_key in step_results:
            r = step_results[step_key]
            style = {"success": "[green]OK[/green]", "skipped": "[dim]Skipped[/dim]", "failed": "[red]Failed[/red]"}
            table.add_row(STEPS[step_key]["name"], style.get(r, r))

    console.print(table)

    if records:
        for r in records:
            if r.get("url"):
                console.print(f"  {r.get('platform', '?').title()}: {r['url']}")

    # Save report
    report_path = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_publish-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"\nReport: {report_path}")

    return report

# ── CLI ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--auto", is_flag=True, help="Fully automated, no prompts (for Claude Code)")
@click.option("--dry-run", is_flag=True, help="Preview only, don't publish")
@click.option("--skip-images", is_flag=True, help="Skip image processing")
@click.option("--only", "only_steps", default=None, help="Comma-separated: images,hercules,machineryline,social")
@click.option("--crane", "crane_folder", default=None, help="Crane folder name in yeni-vinc/")
def main(auto: bool, dry_run: bool, skip_images: bool, only_steps: str | None, crane_folder: str | None):
    """GST Cranes — Publish a crane to all platforms"""

    load_dotenv(ENV_FILE)

    console.print("[bold cyan]GST Cranes — Publisher[/bold cyan]")

    # Determine steps
    if only_steps:
        steps_to_run = [s.strip() for s in only_steps.split(",") if s.strip() in STEPS]
    else:
        steps_to_run = list(STEP_ORDER)

    if skip_images and "images" in steps_to_run:
        steps_to_run.remove("images")

    # Select crane
    result = select_crane_folder(crane_folder, auto)
    if not result:
        sys.exit(1)
    folder, bilgiler = result

    # Auto-add image step if no processed images exist
    if "images" not in steps_to_run:
        brand = bilgiler.get("brand", "").lower().replace(" ", "-")
        model = bilgiler.get("model", "").lower().replace(" ", "-")
        prefix = f"{brand}-{model}-"
        crane_dir = PROCESSED_DIR / prefix.rstrip("-")
        existing = [f for f in crane_dir.iterdir() if f.name.startswith(prefix)] if crane_dir.exists() else []
        if not existing:
            steps_to_run.insert(0, "images")
            console.print("[dim]No processed images, adding image step[/dim]")

    # Show summary
    show_summary(folder, bilgiler, steps_to_run)

    # Confirm (skip in auto mode)
    if not auto and not dry_run:
        confirm = input("\nReady to publish? (y/n): ").strip().lower()
        if confirm != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    # Execute pipeline
    step_results = {}

    for step_key in STEP_ORDER:
        if step_key not in steps_to_run:
            step_results[step_key] = "skipped"
            continue

        success = run_step(step_key, folder.name, dry_run)
        step_results[step_key] = "success" if success else "failed"

        # In auto mode: if a step fails, skip it and continue
        # In interactive mode: ask what to do
        if not success and not auto and not dry_run:
            choice = input(f"  {STEPS[step_key]['name']} failed. Continue? (y/n): ").strip().lower()
            if choice != "y":
                break

    # Archive (auto mode: always archive on any success)
    successful = [k for k, v in step_results.items() if v == "success"]
    if successful and not dry_run:
        archive_path = archive_crane(folder, bilgiler)
        console.print(f"Archived: {archive_path}")

    # Report
    report = generate_report(bilgiler, step_results)

    if dry_run:
        console.print("[yellow]DRY RUN — nothing was published[/yellow]")

    # Exit code: 0 if any step succeeded, 1 if all failed
    if not successful and not dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
