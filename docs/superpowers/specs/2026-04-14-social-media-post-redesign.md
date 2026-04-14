# Social Media Post Redesign — HTML/CSS + Playwright

**Date:** 2026-04-14
**Status:** Approved

## Problem

Current `post-gorsel.py` uses Pillow to draw social media posts pixel-by-pixel. This is:
- Hard to maintain (manual y-coordinate math)
- Hard to modify (every change requires recalculating layout)
- Visually inconsistent with gstcranes.com brand identity (navy+gold vs site's black+red+white)

## Solution

Replace Pillow rendering with HTML/CSS templates + Playwright screenshot.

## Technical Approach

- Rewrite `scripts/post-gorsel.py` to use HTML/CSS templates + Playwright `page.screenshot()`
- HTML templates stored in `sablonlar/`
- Playwright headless Chromium renders the HTML → exports JPEG
- No new dependencies (Playwright already in project)

## Output Per Crane

| # | Size | Usage | Filename |
|---|------|-------|----------|
| 1 | 1200x630 | Facebook + LinkedIn + Instagram post | `{brand}-{model}-post-dark.jpg` |
| 2 | 1200x630 | Facebook + LinkedIn + Instagram post | `{brand}-{model}-post-light.jpg` |
| 3 | 1080x1920 | Facebook Story + Instagram Story | `{brand}-{model}-story-dark.jpg` |
| 4 | 1080x1920 | Facebook Story + Instagram Story | `{brand}-{model}-story-light.jpg` |

4 files per crane.

## Color Palette

### Dark Theme
| Element | Color |
|---------|-------|
| Background | `#0A0A0A` black |
| Secondary bg (cards, boxes) | `#1A1A1A` |
| Accent / CTA | `#C41E1E` dark red |
| Primary text | `#FFFFFF` white |
| Secondary text | `#9CA3AF` gray |
| Borders | `#2A2A2A` |

### Light Theme
| Element | Color |
|---------|-------|
| Background | `#FFFFFF` white |
| Secondary bg (cards, boxes) | `#F3F4F6` light gray |
| Accent / CTA | `#C41E1E` same red |
| Primary text | `#0A0A0A` black |
| Secondary text | `#6B7280` gray |
| Borders | `#E5E7EB` |

### Typography
- **Font:** Oswald from Google Fonts (bold, condensed, industrial)
- **Fallback:** Arial Black
- **Logo text:** "GST" in theme color (white/black), "CRANES" always `#C41E1E`

## Post Layout (1200x630)

```
┌──────────────────────────────────┐
│  [Logo] GST CRANES    FOR SALE   │  Header bar + red badge
│──────────────────────────────────│  Red accent line
│                                  │
│          LIEBHERR                │  Brand (large, bold)
│        LTM 1350-6.1             │  Model (red accent)
│     All Terrain Mobile Crane     │  Subtitle (gray, small)
│                                  │
│  ┌────────────────────────────┐  │
│  │       [CRANE PHOTO]        │  │  Main photo (rounded corners)
│  └────────────────────────────┘  │
│                                  │
│  ┌─YEAR──┐ ┌─CAPACITY┐ ┌─BOOM─┐ │  Spec boxes (3-4 per row)
│  │ 2008  │ │  90t    │ │ 52m  │ │
│  └───────┘ └─────────┘ └──────┘ │
│                                  │
│  ┌──────── EUR 1.250.000 ──────┐ │  Price box (red border)
│  │  Available for delivery      │ │
│  └──────────────────────────────┘ │
│──────────────────────────────────│
│  gstcranes.com  WP  IG  email   │  Footer (contact info)
└──────────────────────────────────┘
```

Story (1080x1920): Same elements, more vertical space — larger photo, more breathing room between sections.

## File Changes

### Modified
- `scripts/post-gorsel.py` — Full rewrite: Pillow → HTML/CSS + Playwright

### New Files
- `sablonlar/post-template.html` — 1200x630 post template (dark + light CSS)
- `sablonlar/story-template.html` — 1080x1920 story template (dark + light CSS)

### Unchanged
- `scripts/gorsel-hazirla.py` — Adobe Firefly text/logo removal stays as-is
- `scripts/vinc-yayinla.py` — Orchestrator calls post-gorsel.py the same way
- `bilgiler.txt` format — unchanged
- All other scripts — untouched

## Design Principles

- Match gstcranes.com brand identity (black + red + white)
- Metallic logo with crane hook
- "FOR SALE" red badge like site's "MOBILE" badge
- Spec boxes minimal like inventory cards
- Rounded corners on photo (card style)
- Industrial, premium feel
