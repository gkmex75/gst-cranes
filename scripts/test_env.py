"""Test that all required libraries are importable."""

import sys

def main():
    errors = []

    libs = [
        ("playwright.sync_api", "Playwright"),
        ("PIL", "Pillow"),
        ("cv2", "OpenCV"),
        ("dotenv", "python-dotenv"),
        ("requests", "Requests"),
        ("rich", "Rich"),
        ("click", "Click"),
    ]

    for module, name in libs:
        try:
            __import__(module)
        except ImportError:
            errors.append(name)

    if errors:
        print(f"MISSING: {', '.join(errors)}")
        sys.exit(1)

    from rich.console import Console
    Console().print("[bold green]Environment ready[/bold green]")


if __name__ == "__main__":
    main()
