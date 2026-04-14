"""
log-temizle.py — Delete logs and screenshots older than 30 days.

Usage:
    python scripts/log-temizle.py           # Preview (dry run)
    python scripts/log-temizle.py --delete  # Actually delete
"""

import sys
import time
from pathlib import Path

import click
from rich.console import Console

PROJECT_ROOT = Path.home() / "gst-cranes"
LOG_DIR = PROJECT_ROOT / "logs"
MAX_AGE_DAYS = 30

console = Console()


def find_old_files(directory: Path, max_age_days: int) -> list[Path]:
    """Find files older than max_age_days."""
    if not directory.exists():
        return []
    cutoff = time.time() - (max_age_days * 86400)
    old = []
    for f in directory.rglob("*"):
        if f.is_file() and f.stat().st_mtime < cutoff:
            old.append(f)
    return sorted(old)


@click.command()
@click.option("--delete", is_flag=True, help="Actually delete (default is dry run)")
@click.option("--days", default=MAX_AGE_DAYS, help=f"Max age in days (default: {MAX_AGE_DAYS})")
def main(delete: bool, days: int):
    """Clean up old log files and screenshots."""
    console.print(f"[bold cyan]GST Cranes — Log Cleanup[/bold cyan]")
    console.print(f"  Looking for files older than {days} days in {LOG_DIR}")

    old_files = find_old_files(LOG_DIR, days)

    if not old_files:
        console.print("[green]No old files found.[/green]")
        return

    total_size = sum(f.stat().st_size for f in old_files)
    console.print(f"  Found {len(old_files)} files ({total_size / 1024 / 1024:.1f} MB)")

    for f in old_files:
        rel = f.relative_to(LOG_DIR)
        if delete:
            f.unlink()
            console.print(f"  [red]Deleted:[/red] {rel}")
        else:
            console.print(f"  [yellow]Would delete:[/yellow] {rel}")

    if not delete:
        console.print(f"\n[yellow]Dry run — use --delete to actually remove files[/yellow]")
    else:
        console.print(f"\n[green]Deleted {len(old_files)} files ({total_size / 1024 / 1024:.1f} MB freed)[/green]")


if __name__ == "__main__":
    main()
