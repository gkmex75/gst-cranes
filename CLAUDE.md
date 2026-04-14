# GST Cranes Automation

## 1. Project Overview

- **Business:** GST Cranes — international used mobile crane trading
- **Website:** [gstcranes.com](https://www.gstcranes.com)
- **Owner:** Gokmen Tanacar
- **Target markets:** Europe, Asia, Africa, Middle East, Americas
- **RULE:** Do NOT mention Turkey in worldwide delivery messaging
- **Primary platforms:**
  - Hercules dashboard (website backend at hercules.app/dashboard, GST Cranes project)
  - Machinery Line (machineryline.com)
  - Facebook
  - Instagram
  - LinkedIn

## 2. Folder Structure

```
~/gst-cranes/
├── yeni-vinc/       # Input: raw photos + bilgiler.txt per crane
├── processed/       # Output: cleaned & resized images
├── yayinlanan/      # Archive: published crane records
├── sablonlar/       # Templates (bilgiler.txt example, etc.)
├── scripts/         # Python automation scripts
├── logs/            # Session logs with timestamps
└── .env             # API keys and config (gitignored)
```

### Workflow per crane

1. User creates a subfolder in `yeni-vinc/` (e.g. `yeni-vinc/liebherr-ltm-1090/`)
2. User drops raw photos + filled `bilgiler.txt` into that subfolder
3. Run `vinc-yayinla.py` (orchestrator) or individual scripts as needed
4. After publishing, the subfolder moves to `yayinlanan/` as archive

## 3. Scripts (Build Order)

| # | Script | Purpose |
|---|--------|---------|
| 1 | `scripts/gorsel-hazirla.py` | Image processing via Adobe Firefly API — remove text/logos, color enhancement, resize for web + social media |
| 2 | `scripts/hercules-upload.py` | Upload listing to hercules.app/dashboard (GST Cranes project) using Playwright with existing Chrome session |
| 3 | `scripts/machineryline-upload.py` | Upload listing to machineryline.com using Playwright |
| 4 | `scripts/sosyal-medya-post.py` | Post to Facebook, Instagram, LinkedIn (prefer official APIs: Meta Graph API, LinkedIn API; fallback to browser automation) |
| 5 | `scripts/vinc-yayinla.py` | Main orchestrator — runs all above in sequence with user approval checkpoints between each step |

## 4. Coding Standards

- **Python 3.11+**
- Each script must be independently runnable (`if __name__ == "__main__"`)
- Use `rich` library for console output with progress bars and status indicators
- Use `Playwright` (not Selenium) for all browser automation
- Use existing Chrome session via persistent context — no re-login required
- Use `python-dotenv` for secrets; **never** hardcode credentials
- Log all actions to `~/gst-cranes/logs/` with timestamps (format: `YYYY-MM-DD_HH-MM-SS_scriptname.log`)
- Clear error handling with helpful, actionable messages
- Comments and all user-facing messages in **English**
- Ask for user confirmation before any irreversible action (publish, post, delete)

## 5. Crane Listing Template

### Title Format

```
[YEAR] [BRAND] [MODEL] - [CAPACITY]t Mobile Crane
```

**Example:** `2008 Liebherr LTM 1090-2 - 90t Mobile Crane`

### Full Description (for Hercules / Machinery Line)

```
[BRAND] [MODEL] — Year [YEAR]
Operating hours: [HOURS]
Capacity: [CAPACITY] tons
Boom length: [BOOM] m
Price: EUR [PRICE]

Condition: Excellent, fully inspected and ready for immediate operation.
Origin: [COUNTRY]
Inspection available on request at our yard.

Delivery worldwide — Europe, Asia, Africa, Middle East, and the Americas.

Contact GST Cranes:
info@gstcranes.com
WhatsApp: +32 483 56 64 65
www.gstcranes.com
```

## 6. Social Media Template

```
[YEAR] [BRAND] [MODEL] — Now Available

[CAPACITY]t capacity
[HOURS] operating hours
Fully inspected
Worldwide delivery

Price: EUR [PRICE]
WhatsApp: +32 483 56 64 65
info@gstcranes.com

#MobileCrane #[Brand] #UsedCranes #GSTCranes #CraneForSale
```

## 7. bilgiler.txt Format

Each crane subfolder in `yeni-vinc/` must contain a `bilgiler.txt` with:

```
brand = 
model = 
year = 
capacity_tons = 
boom_length_m = 
operating_hours = 
price_eur = 
origin_country = 
notes = 
```

All fields required except `notes`. See `sablonlar/bilgiler-ornek.txt` for a filled example.

## 8. Rules — NEVER Do Without Asking

1. **Delete** any file, listing, or message
2. **Publish or post** without explicit user confirmation
3. **Mention Turkey** in "worldwide delivery" context
4. **Share customer contact info** with third parties
5. **Omit WhatsApp +32 483 56 64 65** — must be included in every listing and social media template

## 9. Self-Update Policy

When new rules or templates are provided during a session ("from now on use X"), this CLAUDE.md file will be updated immediately and the change will be summarized to the user.

## 10. Contact Info (for templates)

- **Email:** info@gstcranes.com
- **WhatsApp:** +32 483 56 64 65
- **Website:** www.gstcranes.com

## 11. Using with Claude Code

Claude Code can run the full pipeline via natural language. The scripts do all the heavy lifting — Claude Code only needs to call them.

### Quick Reference

```bash
# Always activate venv first
cd ~/gst-cranes && source .venv/bin/activate

# Full pipeline
python scripts/vinc-yayinla.py

# Dry run (preview only)
python scripts/vinc-yayinla.py --dry-run

# Skip image processing
python scripts/vinc-yayinla.py --skip-images

# Specific steps only
python scripts/vinc-yayinla.py --only hercules,social

# Individual scripts
python scripts/gorsel-hazirla.py
python scripts/hercules-upload.py --crane <folder>
python scripts/machineryline-upload.py --crane <folder>
python scripts/sosyal-medya-post.py --crane <folder>

# Check credentials
python scripts/sosyal-medya-post.py --check-auth
python scripts/gorsel-hazirla.py --check-auth
```

### Adding a New Crane via Claude Code

When the user says "I have a new crane", Claude Code should:
1. Create a folder in `yeni-vinc/` (e.g. `yeni-vinc/tadano-gr-1000xl/`)
2. Create `bilgiler.txt` from the template, pre-filling any details the user provided
3. Ask for missing required fields
4. Prompt the user to add photos to the folder
5. Run `vinc-yayinla.py` when ready

See `COWORK_INTEGRATION.md` for full details and example prompts.
