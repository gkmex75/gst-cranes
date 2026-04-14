# Claude Code Integration — GST Cranes

## Overview

The GST Cranes automation scripts are designed to be called from Claude Code (CLI, VS Code extension, or desktop app). Claude Code only needs to invoke the scripts — all logic lives in the Python scripts themselves.

## Setup

### 1. Add to CLAUDE.md (already done)

The project's `CLAUDE.md` file contains all context Claude Code needs. When you open a terminal in `~/gst-cranes/` and start Claude Code, it reads `CLAUDE.md` automatically.

### 2. Global Instructions (Optional)

If you want Claude Code to know about GST Cranes from any directory, add this to your global settings at `~/.claude/CLAUDE.md`:

```markdown
## GST Cranes Automation

I run a used crane trading business (gstcranes.com). My automation scripts
are at ~/gst-cranes/. When I ask about publishing cranes, listing cranes,
or crane-related tasks, work from that directory.

Key commands:
- Full publish: cd ~/gst-cranes && source .venv/bin/activate && python scripts/vinc-yayinla.py
- Images only: python scripts/gorsel-hazirla.py
- Hercules only: python scripts/hercules-upload.py
- Machinery Line only: python scripts/machineryline-upload.py
- Social media only: python scripts/sosyal-medya-post.py

Always activate the venv first: source ~/gst-cranes/.venv/bin/activate
```

## Example Prompts

### Publishing

| What you say | What Claude Code does |
|---|---|
| "Publish a new crane" | Checks `yeni-vinc/` for folders, validates `bilgiler.txt`, runs `vinc-yayinla.py` |
| "Publish the Liebherr" | Runs `vinc-yayinla.py --crane liebherr-ltm-1090` |
| "Dry run the new crane" | Runs `vinc-yayinla.py --dry-run` |
| "Publish but skip image processing" | Runs `vinc-yayinla.py --skip-images` |

### Partial Steps

| What you say | What Claude Code does |
|---|---|
| "Just process the images" | Runs `gorsel-hazirla.py` |
| "Upload to Hercules only" | Runs `vinc-yayinla.py --only hercules` |
| "Post only to social media" | Runs `vinc-yayinla.py --only social` |
| "Upload to Hercules and Machinery Line" | Runs `vinc-yayinla.py --only hercules,machineryline` |

### Republishing / Updates

| What you say | What Claude Code does |
|---|---|
| "Republish with new photos" | Replaces images in `yeni-vinc/`, runs `gorsel-hazirla.py`, then the upload scripts |
| "Update the social media posts" | Runs `sosyal-medya-post.py` for the relevant crane |
| "Reprocess images without Firefly" | Runs `gorsel-hazirla.py --skip-firefly` |

### Setup & Diagnostics

| What you say | What Claude Code does |
|---|---|
| "Check my API credentials" | Runs `sosyal-medya-post.py --check-auth` and `gorsel-hazirla.py --check-auth` |
| "Help me set up Adobe Firefly" | Opens `ADOBE_SETUP.md` and walks through the steps |
| "Help me set up social media APIs" | Opens `SOCIAL_SETUP.md` and walks through the steps |
| "Show me what's been published" | Lists JSON files in `yayinlanan/` |

### Adding a New Crane

| What you say | What Claude Code does |
|---|---|
| "I have a new crane to add" | Creates a folder in `yeni-vinc/`, creates `bilgiler.txt` from template, asks you to fill in details |
| "New crane: Tadano GR-1000XL, 2015, 100t, 8500 hours, 320000 EUR" | Creates folder + pre-fills `bilgiler.txt` with the info you gave |

## How Claude Code Should Handle Requests

When asked to publish a crane, Claude Code should follow this sequence:

### Step 1: Validate Input
```bash
ls ~/gst-cranes/yeni-vinc/
```
Check if there are crane folders with images and `bilgiler.txt`.

If no folders exist or `bilgiler.txt` is missing/incomplete:
- Ask the user for the crane details
- Create the folder and `bilgiler.txt`

### Step 2: Run the Pipeline
```bash
cd ~/gst-cranes && source .venv/bin/activate
python scripts/vinc-yayinla.py --crane <folder-name>
```

The script handles everything interactively — it will prompt for confirmations at each step.

### Step 3: Report Results
After the script completes, read the latest publish report:
```bash
ls -t ~/gst-cranes/logs/*publish-report.json | head -1
```
Summarize the results in natural language.

## Important Rules

- **Never bypass the scripts** — always call them, don't try to replicate their logic
- **Never publish without confirmation** — the scripts handle this, let them prompt
- **Never mention Turkey** in worldwide delivery context
- **Always activate the venv** before running scripts
