# Gkmex Terex Demag CC 2400-1 Organic Reel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the supplied 2007 Terex Demag CC 2400-1 as a Gkmex-owned used-crane sale listing, create a portrait-first GST green Reel with restrained crane motion, and distribute it organically to Facebook, Instagram and LinkedIn without changing paid advertising.

**Architecture:** The production listing is written idempotently to Cloudflare D1 and the byte-identical supplied image is stored in production R2. A single new `ToweringRig` Remotion composition fits the entire 3:4 crane image or motion clip inside a 1080×1920 canvas, adds the approved six-beat sales story, and supplies the existing organic publisher with a platform-compatible MP4. The workflow captures read-only Meta campaign snapshots before and after organic publishing.

**Tech Stack:** Cloudflare D1/R2 via Wrangler, fal.ai Kling image-to-video, Remotion 4, TypeScript/React, Python/pytest, FFmpeg/FFprobe, Meta Graph API and LinkedIn UGC API.

---

## Locked identifiers and files

- Listing ID: `4eea1e9b-4395-4703-932d-ae0df719f650`
- Listing slug: `terex-demag-cc-2400-1-400t-2007`
- Listing photo ID: `a1441a4a-95bf-4ef8-b662-5833120df730`
- Gkmex auth user ID: `40cf02d8-29e0-49f9-8a00-5752d4860ac0`
- Listing photo R2 key: `listings/uploads/40cf02d8-29e0-49f9-8a00-5752d4860ac0/a1441a4a-95bf-4ef8-b662-5833120df730.jpg`
- Source image: `/tmp/codex-remote-attachments/019f8f43-8787-7c80-8ca1-075d7ebc786f/A6A0E977-12FB-4F74-8934-BE209F54BFD4/1-Fotoğraf-1.jpg`
- Expected source SHA-256: `0adcc6e659026147066364f3704336a54803e3cca96bb87c1512f250a67c5199`
- Marketplace repo: `/Users/gokmentanacar/projects/crane-rental-directory`
- Marketing repo: `/Users/gokmentanacar/gst-cranes`
- Remotion source asset: `remotion-shorts/public/gkmex-cc2400-11200h-original.jpg`
- Generated motion asset: `remotion-shorts/public/gkmex-cc2400-11200h-motion.mp4`
- Render props: `remotion-shorts/props/gkmex-cc2400-11200h-sale.json`
- Caption: `output/gkmex-cc2400-11200h-caption.txt`
- Final Reel: `remotion-shorts/output/gkmex-cc2400-11200h-sale.mp4`
- Publication audit: `output/gkmex-cc2400-11200h-organic-result.json`

### Task 1: Prove source, seller, schema, duplicate and paid-state preconditions

**Files:**
- Read: source image
- Read: `/Users/gokmentanacar/projects/crane-rental-directory/wrangler.toml`
- Read remotely: D1 `listings`, `listing_photos`, `auth_users`, `user_profile`
- Create temporarily: `/tmp/gkmex-cc2400-meta-campaigns-before.json`

- [ ] **Step 1: Verify the source contract**

Run:

```bash
SOURCE='/tmp/codex-remote-attachments/019f8f43-8787-7c80-8ca1-075d7ebc786f/A6A0E977-12FB-4F74-8934-BE209F54BFD4/1-Fotoğraf-1.jpg'
shasum -a 256 "$SOURCE"
sips -g pixelWidth -g pixelHeight "$SOURCE"
stat -f '%z' "$SOURCE"
```

Expected:

```text
0adcc6e659026147066364f3704336a54803e3cca96bb87c1512f250a67c5199
pixelWidth: 960
pixelHeight: 1280
311298
```

- [ ] **Step 2: Re-read production schemas before SQL**

Run from `/Users/gokmentanacar/projects/crane-rental-directory`:

```bash
npx wrangler d1 execute crane-directory-prod --remote --command \
  "PRAGMA table_info(listings); PRAGMA table_info(listing_photos); PRAGMA table_info(auth_users); PRAGMA table_info(user_profile);"
```

Expected: `listings.id` and `listings.user_id` are `TEXT`; `listing_photos.position` exists; `listing_photos.display_order` does not.

- [ ] **Step 3: Verify the existing Gkmex account**

Run:

```bash
npx wrangler d1 execute crane-directory-prod --remote --command \
  "SELECT au.id, au.email, au.email_verified, up.company_name, up.phone_e164, up.whatsapp_e164,
          up.contact_email AS profile_email, up.website, up.logo_r2_key
   FROM auth_users au
   JOIN user_profile up ON up.user_id=au.id
   WHERE au.id='40cf02d8-29e0-49f9-8a00-5752d4860ac0';"
```

Expected: exactly one row for Gkmex with `gkm@gkmex.com`, verified email, `+905456867277`, website `gkmex.com`, and the existing Gkmex logo key.

- [ ] **Step 4: Prove no duplicate listing exists**

Run:

```bash
npx wrangler d1 execute crane-directory-prod --remote --command \
  "SELECT id, slug, user_id, status, year, hours, asking_price_eur
   FROM listings
   WHERE slug='terex-demag-cc-2400-1-400t-2007'
      OR (lower(brand)='terex demag' AND lower(model)='cc 2400-1' AND year=2007);"
```

Expected before creation: zero rows. On a resumed run, the fixed listing ID may exist; compare its complete locked fields and do not create another row.

- [ ] **Step 5: Capture the read-only Meta paid-campaign baseline**

Run from `/Users/gokmentanacar/gst-cranes`:

```bash
set -a
source /Users/gokmentanacar/projects/gst-cranes-marketing/.env.local
set +a
python3 - <<'PY'
import json, os, requests

account = os.environ["META_AD_ACCOUNT_ID"]
token = os.environ["META_ACCESS_TOKEN"]
url = f"https://graph.facebook.com/v21.0/{account}/campaigns"
params = {
    "fields": "id,name,status,effective_status",
    "limit": 500,
    "access_token": token,
}
rows = []
while url:
    payload = requests.get(url, params=params, timeout=30).json()
    if "error" in payload:
        raise SystemExit(payload["error"])
    rows.extend(payload.get("data", []))
    url = payload.get("paging", {}).get("next")
    params = None
rows.sort(key=lambda row: row["id"])
with open("/tmp/gkmex-cc2400-meta-campaigns-before.json", "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=2, sort_keys=True)
print(f"captured {len(rows)} campaigns")
PY
```

Expected: a non-error campaign count. This is a GET-only request.

### Task 2: Build the portrait-first `ToweringRig` composition with TDD

**Files:**
- Create: `tests/test_towering_rig_contract.py`
- Create: `remotion-shorts/src/ToweringRig.tsx`
- Modify: `remotion-shorts/src/Root.tsx`
- Create: `remotion-shorts/props/gkmex-cc2400-11200h-sale.json`

- [ ] **Step 1: Write the failing contract test**

Create `tests/test_towering_rig_contract.py`:

```python
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_towering_rig_is_registered_as_a_15_second_portrait_reel():
    root = (ROOT / "remotion-shorts/src/Root.tsx").read_text()
    assert 'id="ToweringRig"' in root
    assert "durationInFrames={450}" in root
    assert "width={1080}" in root
    assert "height={1920}" in root
    assert 'from "./ToweringRig"' in root


def test_cc2400_props_lock_the_verified_facts_and_green_brand():
    props = json.loads(
        (ROOT / "remotion-shorts/props/gkmex-cc2400-11200h-sale.json").read_text()
    )
    assert props["headline"] == "TEREX DEMAG CC 2400-1"
    assert props["specLine1"] == "2007 · 400 T · 11,200 HOURS"
    assert props["specLine2"] == "84 M BOOM · 84 M LUFFING JIB"
    assert props["specLine3"] == "12 M FIXED JIB · 30 M SUPERLIFT MAST"
    assert props["price"] == "€1,250,000"
    assert props["sellerName"] == "Gkmex"
    assert props["phone"] == "+90 545 686 72 77"
    assert props["email"] == "gkm@gkmex.com"
    assert props["accent"].lower() == "#16a34a"


def test_public_reel_copy_excludes_forbidden_scope():
    text = (
        (ROOT / "remotion-shorts/src/ToweringRig.tsx").read_text()
        + (ROOT / "remotion-shorts/props/gkmex-cc2400-11200h-sale.json").read_text()
    ).lower()
    for forbidden in ("#e8a430", "turkey", "türkiye", "rental"):
        assert forbidden not in text
```

- [ ] **Step 2: Run the test and prove it fails**

Run:

```bash
python3 -m pytest tests/test_towering_rig_contract.py -q
```

Expected: failures because `ToweringRig.tsx`, its registration and its props do not exist.

- [ ] **Step 3: Create the complete composition**

Create `remotion-shorts/src/ToweringRig.tsx`:

```tsx
import React from "react";
import {
  AbsoluteFill,
  Easing,
  Html5Video,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { DISPLAY, FontFaces, INTER, MONO } from "./GstBrand";

export type ToweringRigProps = {
  media: string;
  mediaKind: "video" | "image";
  headline: string;
  specLine1: string;
  specLine2: string;
  specLine3: string;
  price: string;
  sellerName: string;
  sellerLogo: string;
  phone: string;
  email: string;
  website: string;
  accent: string;
  accentDark: string;
};

const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };

const Beat: React.FC<{
  start: number;
  end: number;
  children: React.ReactNode;
  align?: "left" | "center";
}> = ({ start, end, children, align = "left" }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [start, start + 14, Math.max(start + 15, end - 12), end],
    [0, 1, 1, 0],
    clamp,
  );
  const y = interpolate(frame, [start, start + 18], [34, 0], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  return (
    <div
      style={{
        position: "absolute",
        left: 72,
        right: 72,
        top: 1090,
        textAlign: align,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      {children}
    </div>
  );
};

export const ToweringRig: React.FC<ToweringRigProps> = ({
  media,
  mediaKind,
  headline,
  specLine1,
  specLine2,
  specLine3,
  price,
  sellerName,
  sellerLogo,
  phone,
  email,
  website,
  accent,
  accentDark,
}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 449], [1, 1.055], {
    ...clamp,
    easing: Easing.inOut(Easing.quad),
  });
  const drift = interpolate(frame, [0, 449], [0, -22], clamp);
  const mediaOpacity = interpolate(frame, [390, 410], [1, 0.34], clamp);
  const endOpacity = interpolate(frame, [390, 408], [0, 1], clamp);
  const endY = interpolate(frame, [390, 414], [34, 0], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });

  const mediaStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "contain",
    transform: `translateY(${drift}px) scale(${scale})`,
    opacity: mediaOpacity,
  };

  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg,#0b0f0d,#111614)", color: "#fff" }}>
      <FontFaces />
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {mediaKind === "video" ? (
          <Html5Video src={staticFile(media)} muted style={mediaStyle} />
        ) : (
          <Img src={staticFile(media)} style={mediaStyle} />
        )}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg,rgba(8,12,10,.72) 0%,rgba(8,12,10,0) 28%,rgba(8,12,10,.18) 54%,rgba(8,12,10,.94) 82%,#0b0f0d 100%)",
        }}
      />

      <div style={{ position: "absolute", top: 178, left: 72, right: 72, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontFamily: MONO, fontSize: 26, letterSpacing: "0.14em" }}>
          <span style={{ color: accent }}>●</span> GST CRANES
        </div>
        <div style={{ backgroundColor: accent, borderRadius: 999, padding: "12px 22px", fontFamily: MONO, fontSize: 24, letterSpacing: "0.1em" }}>
          FOR SALE
        </div>
      </div>

      <Beat start={0} end={60}>
        <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 76, lineHeight: 0.98, letterSpacing: "-0.025em" }}>
          {headline}
        </div>
        <div style={{ width: 210, height: 8, borderRadius: 8, backgroundColor: accent, marginTop: 28 }} />
      </Beat>

      {[{ start: 60, end: 150, text: specLine1 }, { start: 150, end: 240, text: specLine2 }, { start: 240, end: 300, text: specLine3 }].map((beat) => (
        <Beat key={beat.start} start={beat.start} end={beat.end}>
          <div style={{ fontFamily: MONO, color: accent, fontSize: 24, letterSpacing: "0.14em", marginBottom: 18 }}>
            VERIFIED SPECIFICATION
          </div>
          <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 68, lineHeight: 1.04 }}>
            {beat.text}
          </div>
        </Beat>
      ))}

      <Beat start={300} end={390} align="center">
        <div style={{ display: "inline-block", background: `linear-gradient(135deg,${accentDark},${accent})`, borderRadius: 24, padding: "34px 52px 38px", boxShadow: "0 24px 80px rgba(0,0,0,.36)" }}>
          <div style={{ fontFamily: MONO, fontSize: 24, letterSpacing: "0.16em" }}>ASKING PRICE</div>
          <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 96, letterSpacing: "-0.035em", marginTop: 8 }}>{price}</div>
        </div>
      </Beat>

      <div style={{ position: "absolute", left: 72, right: 72, top: 910, opacity: endOpacity, transform: `translateY(${endY}px)` }}>
        <div style={{ background: "rgba(255,255,255,.97)", color: "#0f1511", borderRadius: 28, padding: "38px 42px", boxShadow: "0 24px 90px rgba(0,0,0,.4)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <Img src={staticFile(sellerLogo)} style={{ width: 112, height: 112, objectFit: "contain", borderRadius: 16 }} />
            <div>
              <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 66 }}>{sellerName}</div>
              <div style={{ fontFamily: MONO, color: accentDark, fontSize: 22, letterSpacing: "0.1em" }}>DIRECT SELLER</div>
            </div>
          </div>
          <div style={{ height: 1, backgroundColor: "#dce5df", margin: "28px 0" }} />
          <div style={{ fontFamily: INTER, fontWeight: 700, fontSize: 34, lineHeight: 1.55 }}>{phone}</div>
          <div style={{ fontFamily: INTER, fontWeight: 700, fontSize: 34, lineHeight: 1.55 }}>{email}</div>
          <div style={{ marginTop: 24, backgroundColor: accent, color: "#fff", borderRadius: 12, padding: "18px 22px", fontFamily: MONO, fontSize: 28, textAlign: "center", letterSpacing: "0.05em" }}>
            FULL LISTING · {website}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 4: Register the composition**

Add to `remotion-shorts/src/Root.tsx` imports:

```tsx
import { ToweringRig } from "./ToweringRig";
```

Add before the closing fragment:

```tsx
<Composition
  id="ToweringRig"
  component={ToweringRig}
  durationInFrames={450}
  fps={30}
  width={1080}
  height={1920}
  defaultProps={{
    media: "gkmex-cc2400-11200h-original.jpg",
    mediaKind: "image",
    headline: "TEREX DEMAG CC 2400-1",
    specLine1: "2007 · 400 T · 11,200 HOURS",
    specLine2: "84 M BOOM · 84 M LUFFING JIB",
    specLine3: "12 M FIXED JIB · 30 M SUPERLIFT MAST",
    price: "€1,250,000",
    sellerName: "Gkmex",
    sellerLogo: "seller_gkmex.png",
    phone: "+90 545 686 72 77",
    email: "gkm@gkmex.com",
    website: "gstcranes.com",
    accent: "#16A34A",
    accentDark: "#15803D",
  }}
/>
```

- [ ] **Step 5: Create exact render props**

Create `remotion-shorts/props/gkmex-cc2400-11200h-sale.json`:

```json
{
  "media": "gkmex-cc2400-11200h-motion.mp4",
  "mediaKind": "video",
  "headline": "TEREX DEMAG CC 2400-1",
  "specLine1": "2007 · 400 T · 11,200 HOURS",
  "specLine2": "84 M BOOM · 84 M LUFFING JIB",
  "specLine3": "12 M FIXED JIB · 30 M SUPERLIFT MAST",
  "price": "€1,250,000",
  "sellerName": "Gkmex",
  "sellerLogo": "seller_gkmex.png",
  "phone": "+90 545 686 72 77",
  "email": "gkm@gkmex.com",
  "website": "gstcranes.com",
  "accent": "#16A34A",
  "accentDark": "#15803D"
}
```

- [ ] **Step 6: Run tests and TypeScript validation**

Run:

```bash
python3 -m pytest tests/test_towering_rig_contract.py -q
cd remotion-shorts && npx tsc --noEmit
```

Expected: three pytest tests pass and TypeScript exits `0`.

- [ ] **Step 7: Commit only the composition contract**

Run:

```bash
git add \
  tests/test_towering_rig_contract.py \
  remotion-shorts/src/ToweringRig.tsx \
  remotion-shorts/src/Root.tsx \
  remotion-shorts/props/gkmex-cc2400-11200h-sale.json
git commit -m "feat: add CC2400 Towering Rig reel"
```

### Task 3: Publish the Gkmex marketplace listing idempotently

**Files:**
- Create remotely: production R2 photo object
- Create temporarily: `/tmp/gkmex-cc2400-2007.sql`
- Create remotely: one D1 `listings` row and one `listing_photos` row

- [ ] **Step 1: Upload and re-download the byte-identical photo**

Run from `/Users/gokmentanacar/projects/crane-rental-directory`:

```bash
SOURCE='/tmp/codex-remote-attachments/019f8f43-8787-7c80-8ca1-075d7ebc786f/A6A0E977-12FB-4F74-8934-BE209F54BFD4/1-Fotoğraf-1.jpg'
R2_KEY='listings/uploads/40cf02d8-29e0-49f9-8a00-5752d4860ac0/a1441a4a-95bf-4ef8-b662-5833120df730.jpg'
npx wrangler r2 object put "crane-directory-assets-prod/$R2_KEY" --remote --file="$SOURCE" --content-type=image/jpeg
npx wrangler r2 object get "crane-directory-assets-prod/$R2_KEY" --remote --file=/tmp/gkmex-cc2400-r2-verify.jpg
shasum -a 256 /tmp/gkmex-cc2400-r2-verify.jpg
```

Expected SHA-256: `0adcc6e659026147066364f3704336a54803e3cca96bb87c1512f250a67c5199`.

- [ ] **Step 2: Create guarded production SQL**

Create `/tmp/gkmex-cc2400-2007.sql` with:

```sql
INSERT INTO listings (
  id, slug, user_id, status, kind, brand, model, capacity_t, type, year,
  title, description, asking_price_eur, asking_price_currency,
  country, city, hours, running_hours, kms, mileage_km,
  identification_confidence, identification_source,
  created_at, updated_at, published_at,
  body_text, ai_summary,
  contact_phone, contact_company, contact_email, contact_website,
  brochure_year, brochure_hours, brochure_price_eur, brochure_price_poa,
  brochure_notes, condition, emission_standard, features_json,
  accept_offers, idempotency_key, brochure_locale
)
SELECT
  '4eea1e9b-4395-4703-932d-ae0df719f650',
  'terex-demag-cc-2400-1-400t-2007',
  '40cf02d8-29e0-49f9-8a00-5752d4860ac0',
  'published', 'sell', 'Terex Demag', 'CC 2400-1', 400, 'crawler_crane', 2007,
  'Terex Demag CC 2400-1 · 400 t · 2007',
  '2007 Terex Demag CC 2400-1 crawler crane with 400 t lifting capacity. Configuration includes an 84 m main boom, 84 m luffing jib, 12 m fixed jib and 30 m superlift mast. Recorded operating hours: 11,200. Offered by Gkmex at €1,250,000. Contact Gkmex directly to confirm the exact included equipment, inspection, service records, availability and transport details.',
  1250000, 'EUR',
  NULL, NULL, 11200, 11200, NULL, NULL,
  1.0, 'user_supplied',
  unixepoch(), unixepoch(), unixepoch(),
  '2007 Terex Demag CC 2400-1 crawler crane. 400 t capacity. 84 m main boom, 84 m luffing jib, 12 m fixed jib and 30 m superlift mast. Recorded operating hours: 11,200. Asking price: €1,250,000.',
  '2007 Terex Demag CC 2400-1 crawler crane offered by Gkmex with 400 t capacity and 11,200 recorded operating hours. Asking price: €1,250,000.',
  '+905456867277', 'Gkmex', 'gkm@gkmex.com', 'https://gkmex.com',
  2007, 11200, 1250000, 0,
  '84 m main boom · 84 m luffing jib · 12 m fixed jib · 30 m superlift mast.',
  'used', NULL,
  '["84 m main boom","84 m luffing jib","12 m fixed jib","30 m superlift mast"]',
  0, 'gkmex-cc2400-2007-organic-20260725', 'en'
WHERE NOT EXISTS (
  SELECT 1 FROM listings
  WHERE id='4eea1e9b-4395-4703-932d-ae0df719f650'
     OR slug='terex-demag-cc-2400-1-400t-2007'
);

INSERT INTO listing_photos (
  id, listing_id, r2_key, original_filename, width, height, bytes, position, created_at
)
SELECT
  'a1441a4a-95bf-4ef8-b662-5833120df730',
  '4eea1e9b-4395-4703-932d-ae0df719f650',
  'listings/uploads/40cf02d8-29e0-49f9-8a00-5752d4860ac0/a1441a4a-95bf-4ef8-b662-5833120df730.jpg',
  '1-Fotoğraf-1.jpg', 960, 1280, 311298, 0, unixepoch()
WHERE EXISTS (
  SELECT 1 FROM listings WHERE id='4eea1e9b-4395-4703-932d-ae0df719f650'
)
AND NOT EXISTS (
  SELECT 1 FROM listing_photos WHERE id='a1441a4a-95bf-4ef8-b662-5833120df730'
);
```

- [ ] **Step 3: Apply the SQL with the production D1 safety rules**

Run:

```bash
! rg -n "^(BEGIN|COMMIT|SAVEPOINT)\b" /tmp/gkmex-cc2400-2007.sql
npx wrangler d1 execute crane-directory-prod --remote --file=/tmp/gkmex-cc2400-2007.sql
```

Expected: first run creates one listing and one photo; resumed runs create no duplicate.

- [ ] **Step 4: Read back every locked field**

Run:

```bash
npx wrangler d1 execute crane-directory-prod --remote --command \
  "SELECT l.id,l.slug,l.user_id,l.status,l.kind,l.brand,l.model,l.capacity_t,l.type,l.year,
          l.hours,l.running_hours,l.asking_price_eur,l.asking_price_currency,
          l.country,l.city,l.condition,l.contact_company,l.contact_phone,l.contact_email,
          p.id AS photo_id,p.r2_key,p.width,p.height,p.bytes,p.position
   FROM listings l
   JOIN listing_photos p ON p.listing_id=l.id
   WHERE l.id='4eea1e9b-4395-4703-932d-ae0df719f650';"
```

Expected: exactly one row, owned by Gkmex, `published`, `sell`, `400`, `2007`, both hours fields `11200`, EUR `1250000`, correct photo metadata, and NULL country/city.

- [ ] **Step 5: Verify the public page**

Run:

```bash
curl -fsSL -o /tmp/gkmex-cc2400-listing.html \
  https://gstcranes.com/listing/terex-demag-cc-2400-1-400t-2007
rg -n "CC 2400-1|2007|400|11,200|84 m|12 m|30 m|1,250,000|Gkmex" /tmp/gkmex-cc2400-listing.html
```

Expected: HTTP success and all locked facts. Visually confirm the Gkmex seller card, exact photo and no invented location.

### Task 4: Generate restrained motion with one retry and a deterministic fallback

**Files:**
- Create: `remotion-shorts/public/gkmex-cc2400-11200h-original.jpg`
- Create temporarily: `remotion-shorts/public/gkmex-cc2400-11200h-motion-source.mp4`
- Create if accepted: `remotion-shorts/public/gkmex-cc2400-11200h-motion.mp4`

- [ ] **Step 1: Copy the byte-identical source into Remotion**

Run:

```bash
cp \
  '/tmp/codex-remote-attachments/019f8f43-8787-7c80-8ca1-075d7ebc786f/A6A0E977-12FB-4F74-8934-BE209F54BFD4/1-Fotoğraf-1.jpg' \
  remotion-shorts/public/gkmex-cc2400-11200h-original.jpg
shasum -a 256 remotion-shorts/public/gkmex-cc2400-11200h-original.jpg
```

Expected source hash: `0adcc6e659026147066364f3704336a54803e3cca96bb87c1512f250a67c5199`.

- [ ] **Step 2: Generate the five-second motion clip**

Run from `/Users/gokmentanacar/gst-cranes`:

```bash
set -a
source .env
set +a
python3 - <<'PY'
import pathlib
import urllib.request
import fal_client

source = pathlib.Path("remotion-shorts/public/gkmex-cc2400-11200h-original.jpg")
target = pathlib.Path("remotion-shorts/public/gkmex-cc2400-11200h-motion-source.mp4")
image_url = fal_client.upload_file(str(source))
result = fal_client.subscribe(
    "fal-ai/kling-video/v3/pro/image-to-video",
    arguments={
        "image_url": image_url,
        "duration": "5",
        "prompt": (
            "ABSOLUTE CONSTRAINT: preserve the exact red Terex Demag CC 2400-1 "
            "crawler crane, crawler tracks, counterweights, lattice boom, luffing jib, "
            "superlift mast, rope routing, hook system, jobsite, workers, proportions, "
            "paint, markings, lighting and camera direction from the input image. "
            "Create only a subtle stabilized upward camera push. Hoist lines may show "
            "extremely small natural tension movement and the hook may move no more "
            "than 0.3 metres in scene scale. All structural crane components remain "
            "perfectly rigid. Premium realistic industrial footage."
        ),
        "negative_prompt": (
            "morphing, warping, bending lattice, changed boom geometry, changed jib, "
            "changed superlift, changed tracks, changed counterweights, missing ropes, "
            "extra ropes, worker morphing, extra people, missing people, crane travel, "
            "slew, lifting a new load, orbit, dramatic pan, re-angle, invented equipment, "
            "changed markings, smoke, dust, generated audio"
        ),
    },
    with_logs=True,
)
urllib.request.urlretrieve(result["video"]["url"], target)
print(target)
PY
```

Expected: approximately five seconds of restrained motion.

- [ ] **Step 3: Inspect representative frames**

Run:

```bash
mkdir -p /tmp/gkmex-cc2400-motion-check
for second in 0 1 2 3 4; do
  ffmpeg -y -ss "$second" \
    -i remotion-shorts/public/gkmex-cc2400-11200h-motion-source.mp4 \
    -frames:v 1 "/tmp/gkmex-cc2400-motion-check/frame-${second}.png"
done
```

Open every frame. Reject if the lattice, rope routing, crawler, counterweights, workers, markings or jobsite deform.

- [ ] **Step 4: Make at most one lower-motion retry**

If the first clip is rejected, repeat Step 2 once with the prompt motion sentence replaced by:

```text
The camera is almost completely locked with a barely perceptible upward push. Freeze the hook and keep rope movement near zero.
```

If the retry fails, do not generate again. Change only these props:

```json
{
  "media": "gkmex-cc2400-11200h-original.jpg",
  "mediaKind": "image"
}
```

The Remotion-native 1.00→1.055 push and 22 px upward drift then provide deterministic motion while preserving every source pixel.

If either generated attempt passes the visual gate, stretch its restrained five-second motion over the complete Reel without looping:

```bash
ffmpeg -y \
  -i remotion-shorts/public/gkmex-cc2400-11200h-motion-source.mp4 \
  -vf "setpts=3.0*PTS" -an -r 30 \
  -c:v libx264 -pix_fmt yuv420p -crf 18 \
  remotion-shorts/public/gkmex-cc2400-11200h-motion.mp4
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  remotion-shorts/public/gkmex-cc2400-11200h-motion.mp4
```

Expected: approximately 15.0 seconds. This prevents a visible five-second loop seam.

### Task 5: Render, add silent AAC and visually verify the Reel

**Files:**
- Create: `output/gkmex-cc2400-11200h-caption.txt`
- Create: `remotion-shorts/output/gkmex-cc2400-11200h-sale-raw.mp4`
- Create: `remotion-shorts/output/gkmex-cc2400-11200h-sale.mp4`

- [ ] **Step 1: Create the exact English caption**

Create `output/gkmex-cc2400-11200h-caption.txt`:

```text
FOR SALE — Terex Demag CC 2400-1 crawler crane

400 t · 2007 · 11,200 hours
84 m main boom · 84 m luffing jib
12 m fixed jib · 30 m superlift mast

Asking price: €1,250,000

Direct seller: Gkmex
WhatsApp: +90 545 686 72 77
Email: gkm@gkmex.com
Website: gkmex.com

Full listing:
https://gstcranes.com/listing/terex-demag-cc-2400-1-400t-2007

#TerexDemag #CC2400 #CrawlerCrane #CraneForSale #UsedCranes #HeavyLift
```

- [ ] **Step 2: Assert brand and copy contracts**

Run:

```bash
rg -n "#16A34A|#15803D" \
  remotion-shorts/props/gkmex-cc2400-11200h-sale.json
! rg -ni "#E8A430|amber|Turkey|Türkiye|rental" \
  remotion-shorts/src/ToweringRig.tsx \
  remotion-shorts/props/gkmex-cc2400-11200h-sale.json \
  output/gkmex-cc2400-11200h-caption.txt
```

Expected: green values found; forbidden scan has no matches.

- [ ] **Step 3: Render 450 frames**

Run from `/Users/gokmentanacar/gst-cranes/remotion-shorts`:

```bash
npx remotion render src/index.ts ToweringRig \
  output/gkmex-cc2400-11200h-sale-raw.mp4 \
  --props=props/gkmex-cc2400-11200h-sale.json
```

Expected: 1080×1920 H.264 video, 450 frames at 30 fps.

- [ ] **Step 4: Add a silent AAC compatibility track**

Run:

```bash
ffmpeg -y \
  -i output/gkmex-cc2400-11200h-sale-raw.mp4 \
  -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
  -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart \
  output/gkmex-cc2400-11200h-sale.mp4
```

Expected: one H.264 video stream and one silent AAC audio stream.

- [ ] **Step 5: Verify media metadata**

Run:

```bash
ffprobe -v error \
  -show_entries stream=index,codec_name,codec_type,width,height,r_frame_rate \
  -show_entries format=duration \
  -of json \
  output/gkmex-cc2400-11200h-sale.mp4
```

Expected: H.264, AAC, 1080×1920, 30 fps and approximately 15.0 seconds.

- [ ] **Step 6: Extract and inspect all six beats**

Run:

```bash
mkdir -p /tmp/gkmex-cc2400-reel-check
for second in 1 3 6 9 11.5 14; do
  ffmpeg -y -ss "$second" \
    -i output/gkmex-cc2400-11200h-sale.mp4 \
    -frames:v 1 "/tmp/gkmex-cc2400-reel-check/frame-${second}.png"
done
```

Inspect every PNG. Confirm the exact model, year, capacity, hours, four configuration values, price, Gkmex logo/contact details, green accents, mobile-safe text and intact crane geometry.

### Task 6: Publish organically and prove paid campaigns stayed unchanged

**Files:**
- Read: `scripts/publish_asset.py`
- Create: `output/gkmex-cc2400-11200h-publish.log`
- Create temporarily: social read-backs and `/tmp/gkmex-cc2400-meta-campaigns-after.json`

- [ ] **Step 1: Publish to the exact authorized organic scope**

The user's current instruction already authorizes publication. Run from `/Users/gokmentanacar/gst-cranes`:

```bash
set -a
source .env
set +a
python3 scripts/publish_asset.py \
  --video remotion-shorts/output/gkmex-cc2400-11200h-sale.mp4 \
  --caption-file output/gkmex-cc2400-11200h-caption.txt \
  --targets fb,ig,linkedin \
  --story | tee output/gkmex-cc2400-11200h-publish.log
```

Expected final JSON keys: `fb_reel_video_id`, `fb_story`, `ig_reel`, `ig_story`, `linkedin`. Do not run any ad, boost, audience, budget or campaign script.

- [ ] **Step 2: Read back Facebook and Instagram posts**

Parse the final JSON in the publish log, then issue GET-only Graph requests:

```python
import json, os, re, requests
from pathlib import Path

text = Path("output/gkmex-cc2400-11200h-publish.log").read_text()
match = re.search(r'(\{\s*"fb_reel_video_id".*?\})\s*$', text, re.S)
if not match:
    raise SystemExit("publication JSON not found")
ids = json.loads(match.group(1))
token = os.environ["META_PAGE_ACCESS_TOKEN"]
graph = "https://graph.facebook.com/v21.0"
fb = requests.get(
    f"{graph}/{ids['fb_reel_video_id']}",
    params={"fields": "id,permalink_url,status,description", "access_token": token},
    timeout=30,
).json()
ig = requests.get(
    f"{graph}/{ids['ig_reel']}",
    params={"fields": "id,media_type,media_product_type,permalink,caption,timestamp", "access_token": token},
    timeout=30,
).json()
if "error" in fb or "error" in ig:
    raise SystemExit({"facebook": fb, "instagram": ig})
Path("/tmp/gkmex-cc2400-social-readback.json").write_text(
    json.dumps({"ids": ids, "facebook": fb, "instagram": ig}, indent=2, sort_keys=True)
)
print(json.dumps({"facebook": fb, "instagram": ig}, indent=2))
```

Expected: Facebook video data and permalink; Instagram `media_type=VIDEO`, Reel product type, permalink and exact caption.

- [ ] **Step 3: Verify the LinkedIn creation and public URL**

Read the `linkedin` UGC URN from the final publication JSON. Confirm the log contains `linkedin: 201`, build:

```python
public_url = f"https://www.linkedin.com/feed/update/{ids['linkedin']}"
```

Expected: public URL HTTP `200`. A LinkedIn REST GET may return `403` if the write token lacks read scope; `201` creation plus public URL `200` is sufficient.

- [ ] **Step 4: Capture the paid state after organic publishing**

Repeat Task 1 Step 5, writing to:

```text
/tmp/gkmex-cc2400-meta-campaigns-after.json
```

Then run:

```bash
cmp \
  /tmp/gkmex-cc2400-meta-campaigns-before.json \
  /tmp/gkmex-cc2400-meta-campaigns-after.json
```

Expected: exit `0`; no campaign ID, status or effective status changed.

### Task 7: Create the audit, run final verification and commit exact artifacts

**Files:**
- Create: `output/gkmex-cc2400-11200h-organic-result.json`
- Read: public listing and all organic publication read-backs

- [ ] **Step 1: Record verified identifiers and URLs**

After the read-backs succeed, run this from `/Users/gokmentanacar/gst-cranes` to build the audit from returned values:

```bash
python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

readback = json.loads(Path("/tmp/gkmex-cc2400-social-readback.json").read_text())
ids = readback["ids"]
facebook = readback["facebook"]
instagram = readback["instagram"]
props = json.loads(
    Path("remotion-shorts/props/gkmex-cc2400-11200h-sale.json").read_text()
)
linkedin_urn = ids["linkedin"]
payload = {
    "listing": {
        "id": "4eea1e9b-4395-4703-932d-ae0df719f650",
        "slug": "terex-demag-cc-2400-1-400t-2007",
        "url": "https://gstcranes.com/listing/terex-demag-cc-2400-1-400t-2007",
        "seller_user_id": "40cf02d8-29e0-49f9-8a00-5752d4860ac0",
        "photo_id": "a1441a4a-95bf-4ef8-b662-5833120df730",
        "source_sha256": "0adcc6e659026147066364f3704336a54803e3cca96bb87c1512f250a67c5199",
    },
    "reel": {
        "motion_asset": f"remotion-shorts/public/{props['media']}",
        "final_asset": "remotion-shorts/output/gkmex-cc2400-11200h-sale.mp4",
        "gst_green": "#16A34A",
        "paid_campaign_created": False,
        "paid_campaign_changed": False,
    },
    "organic_publications": {
        "facebook_reel_id": ids["fb_reel_video_id"],
        "facebook_reel_url": facebook["permalink_url"],
        "facebook_story_id": ids["fb_story"],
        "instagram_reel_id": ids["ig_reel"],
        "instagram_reel_url": instagram["permalink"],
        "instagram_story_id": ids["ig_story"],
        "linkedin_ugc_urn": linkedin_urn,
        "linkedin_public_url": f"https://www.linkedin.com/feed/update/{linkedin_urn}",
    },
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
Path("output/gkmex-cc2400-11200h-organic-result.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(payload, indent=2, sort_keys=True))
PY
```

- [ ] **Step 2: Run final consistency checks**

Run:

```bash
python3 -m pytest tests/test_towering_rig_contract.py -q
cd remotion-shorts && npx tsc --noEmit && cd ..
! rg -ni "#E8A430|amber|Turkey|Türkiye|rental" \
  remotion-shorts/src/ToweringRig.tsx \
  remotion-shorts/props/gkmex-cc2400-11200h-sale.json \
  output/gkmex-cc2400-11200h-caption.txt \
  output/gkmex-cc2400-11200h-organic-result.json
```

Expected: all tests pass, TypeScript exits `0`, and the forbidden-copy scan has no matches.

- [ ] **Step 3: Commit only the task-owned reproducibility artifacts**

Run:

```bash
git add \
  remotion-shorts/public/gkmex-cc2400-11200h-original.jpg \
  remotion-shorts/public/gkmex-cc2400-11200h-motion.mp4 \
  remotion-shorts/output/gkmex-cc2400-11200h-sale.mp4 \
  output/gkmex-cc2400-11200h-caption.txt \
  output/gkmex-cc2400-11200h-organic-result.json
git commit -m "content: publish Gkmex CC2400 organic reel"
```

Do not add unrelated dirty or untracked files.
