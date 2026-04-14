# GST Cranes — Full Automation Platform

## 1. Project Overview

- **Business:** GST Cranes — international used mobile crane trading
- **Website:** [gstcranes.com](https://www.gstcranes.com)
- **Owner:** Gokmen Tanacar
- **Target markets:** Europe, Asia, Africa, Middle East, Americas
- **RULE:** Do NOT mention Turkey in worldwide delivery messaging
- **RULE:** ALL post text in English only (no Turkish)
- **Platforms:** Hercules, Machinery Line, Facebook, Instagram, LinkedIn

## 2. Folder Structure

```
~/gst-cranes/
├── yeni-vinc/       # Input: raw photos + bilgiler.txt per crane
├── processed/       # Output: cleaned & resized images (per-crane subdirs)
├── yayinlanan/      # Archive: published crane records
├── sablonlar/       # HTML templates + assets (logo, icons)
├── scripts/         # All automation scripts
├── data/            # envanter.json, paylasilan.json, sold.json
├── output/          # Generated social media images
├── logs/            # Session logs with timestamps
└── .env             # API keys (gitignored)
```

## 3. Two Workflows

### A. New Crane Listing (vinç listeleme)
User says: "Yeni vinç geldi" / "New crane: Liebherr LTM 1200, 2019, 200t"
1. Create folder in `yeni-vinc/` with `bilgiler.txt`
2. User adds photos
3. Run `vinc-yayinla.py` → Hercules + Machinery Line + Social Media

### B. Daily Marketing (sosyal medya)
User says any of these:

| User says | What to do |
|-----------|-----------|
| "Sabah postunu at" / "Post today's crane" | `site-taraci.py` → `icerik-uretici.py --type sale` → show preview → on approval → `yayin-motoru.py --platform all` |
| "We Buy postu at" | `icerik-uretici.py --type buy` → preview → approval → publish |
| "LTM 1090 satıldı" / "LTM 1090 sold to Germany" | `icerik-uretici.py --type sold --crane "Liebherr LTM 1090" --country Germany` → preview → approval → publish |
| "LTM 1230-5 arıyoruz" / "Looking for LTM 1230-5" | `icerik-uretici.py --type wanted --crane "Liebherr LTM 1230-5"` → preview → approval → publish |
| "Story at" | Generate story image → `yayin-motoru.py --platform facebook,instagram --story` |
| "Şu vincin postunu hazırla" | `icerik-uretici.py --type sale --crane "..."` → show images + text |

**IMPORTANT:** NEVER publish without showing the user first and getting explicit approval.

## 4. Scripts

### Crane Listing Scripts
| Script | Purpose |
|--------|---------|
| `gorsel-hazirla.py` | Image processing — remove text/logos, resize |
| `hercules-upload.py` | Upload to hercules.app via Playwright |
| `machineryline-upload.py` | Upload to machineryline.com via Playwright |
| `post-gorsel.py` | Generate post/story images from HTML templates |
| `vinc-yayinla.py` | Orchestrator — runs all listing steps |

### Marketing Scripts
| Script | Purpose |
|--------|---------|
| `site-taraci.py` | Scrape gstcranes.com inventory → `data/envanter.json` |
| `icerik-uretici.py` | Generate post images + text (sale/buy/sold/wanted) |
| `yayin-motoru.py` | Publish to FB + IG + LinkedIn via APIs |
| `log-temizle.py` | Clean logs older than 30 days |

### Social Media Templates (in sablonlar/)
| Template | Size | Usage |
|----------|------|-------|
| `post-template.html` | 1200x630 | Inventory sale post (dark + light) |
| `story-template.html` | 1080x1920 | Story (dark + light) |
| `sold-template.html` | 1200x630 | SOLD post with green badge |
| `alim-template.html` | 1200x630 | "We Buy" + "Wanted" posts |

## 5. Quick Reference

```bash
# Always activate venv first
cd ~/gst-cranes && source .venv/bin/activate

# ── Crane Listing Pipeline ──
python scripts/vinc-yayinla.py                          # Full pipeline
python scripts/vinc-yayinla.py --dry-run                # Preview only
python scripts/vinc-yayinla.py --only hercules,social   # Specific steps

# ── Marketing: Scrape Inventory ──
python scripts/site-taraci.py                           # Update envanter.json

# ── Marketing: Generate Content ──
python scripts/icerik-uretici.py --type sale             # Next crane from inventory
python scripts/icerik-uretici.py --type sale --crane "Liebherr LTM 1350-6.1"
python scripts/icerik-uretici.py --type buy              # "We Buy Cranes" post
python scripts/icerik-uretici.py --type sold --crane "Liebherr LTM 1090-2" --country Germany
python scripts/icerik-uretici.py --type wanted --crane "Liebherr LTM 1230-5"

# ── Marketing: Publish ──
python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "..."
python scripts/yayin-motoru.py --platform facebook,instagram --image output/story.jpg --story
python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "..." --dry-run
```

## 6. Morning Routine (when user says "sabah rutini" or "morning routine")

1. Run `site-taraci.py` — update inventory from website
2. Run `icerik-uretici.py --type sale` — pick next crane, generate images + text
3. Show the generated images and text to user
4. Wait for approval
5. On "ok" / "at" / "paylaş": run `yayin-motoru.py --platform all` for post + story
6. Later (afternoon): run `icerik-uretici.py --type buy` for "We Buy" post → approval → publish

## 7. bilgiler.txt Format

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

## 8. Rules — NEVER Do Without Asking

1. **Publish or post** without explicit user confirmation
2. **Delete** any file, listing, or message
3. **Mention Turkey** in "worldwide delivery" context
4. **Share customer contact info** with third parties
5. **Omit WhatsApp +32 483 56 64 65** from any post/listing
6. **Send LinkedIn DMs or connection requests** automatically
7. **Like or comment** on social media automatically

## 9. Contact Info (for all templates)

- **Email:** info@gstcranes.com
- **WhatsApp:** +32 483 56 64 65
- **Website:** www.gstcranes.com
- **Instagram:** @gstcranes

## 10. API Credentials (.env)

- **Meta Graph API** — Facebook + Instagram (permanent page token, never expires)
- **LinkedIn API** — Personal profile posting (token expires ~60 days, renew by 2026-06-13)
- Chrome profiles at `~/.gst-chrome-profiles/` (hercules, machineryline)

## 11. Self-Update Policy

When new rules or templates are provided during a session ("from now on use X"), this CLAUDE.md file will be updated immediately and the change will be summarized to the user.
