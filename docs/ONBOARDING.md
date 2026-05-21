# Onboarding — GST Cranes Listing Automation

> Bu rehber `.understand-anything/knowledge-graph.json` + `domain-graph.json` üzerinden otomatik üretildi. Hedef: yeni katılan biri (operatör veya geliştirici) **1 saatte projeyi haritalandırması**.
>
> Snapshot tarihi: `2026-05-22` · Commit `b472ccd1`

> **NOT:** `CLAUDE.md` (kök, 209 satır) projenin **canlı operasyonel runbook**'udur — 11 NEVER kuralı, dispatch komutları, platform detayları orada. Bu onboarding ondan mimari + öğrenme-sırası tarafını ayırır. Üretimde bir şeye dokunmadan önce her ikisini de oku.

---

## 1. Proje Özeti

**gst-cranes** — GST Cranes uluslararası ikinci el mobil vinç ticareti için **çok-platformlu listeleme + sosyal medya otomasyon platformu**.

| Boyut | Değer |
|---|---|
| Analiz edilen dosya | 30 (21 Python script + 7 markdown doc + 2 config) |
| Diller | Python, Markdown, config |
| Framework yığını | Pillow (PIL), Playwright, Requests, python-dotenv, OpenAI SDK |
| Dış sistemler | Hercules AI, Machinery Line (machineryline.info), Meta Graph API (FB + IG Business), LinkedIn API (UGC + Marketing), OpenAI gpt-image-2, Adobe Firefly, Postmark, EAST text detection |
| Owner | Gokmen Tanacar |
| Yayın | `gstcranes.com` |
| Target markets | Avrupa, Asya, Afrika, Orta Doğu, Amerika (**Türkiye worldwide delivery'de geçmez**) |

### İki ana workflow

| Workflow | Trigger | Script chain |
|---|---|---|
| **A. Yeni Vinç Listeleme** | "Yeni vinç geldi" + foto + bilgiler.txt | `vinc-yayinla.py` → `gorsel-hazirla.py` → `compose_openai_*` → `hercules-upload.py` + `machineryline-upload.py` + `sosyal-medya-post.py` |
| **B. Daily Marketing** | "Sabah postunu at" / "Story at" / "LTM 1090 satıldı" | `site-taraci.py` → `icerik-uretici.py --type sale\|buy\|sold\|wanted` → `yayin-motoru.py --platform all` |

---

## 2. Mimari Katmanlar (8)

| # | Katman | Dosya | İçerik |
|---|---|---:|---|
| 1 | **Dokümantasyon ve Setup** | 5 | `CLAUDE.md` (209 satır operasyonel runbook) + `ADOBE_SETUP.md` + `SOCIAL_SETUP.md` + `COWORK_INTEGRATION.md` + `.env.example` |
| 2 | **Strateji ve Redesign Notları (superpowers)** | 3 | `2026-04-14-social-media-post-redesign` (986 satır plan + 113 satır spec) + `2026-04-15-operations-dashboard-design` spec |
| 3 | **Yayın Orchestrator** | 2 | `vinc-yayinla.py` (400 satır uçtan uca) + `requirements.txt` |
| 4 | **Broşür ve Görsel Üretim (OpenAI gpt-image-2 + PIL)** | 7 | 3 OpenAI composer (variants/gptimage2/story_b) + 2 deprecated PIL fallback (pil_premium/style_a) + `gorsel-hazirla.py` (630 satır photo prep) + `icerik-uretici.py` (439 satır content) |
| 5 | **Marketplace Upload Adapter'ları** | 2 | `hercules-upload.py` (518 satır) + `machineryline-upload.py` (623 satır) — Playwright tabanlı |
| 6 | **Sosyal Medya Yayın** | 5 | `sosyal-medya-post.py` (**979 satır — repo'nun en büyüğü**) + `yayin-motoru.py` (489 satır) + `post-gorsel.py` + `linkedin-ads.py` + `mail-blast.py` |
| 7 | **LinkedIn OAuth ve Token Yönetimi** | 3 | `get_linkedin_advertising_token` (r_ads/rw_ads) + `get_linkedin_share_token` (w_member_social) + `refresh_linkedin_advertising_token` (60g TTL) |
| 8 | **Yardımcı ve Bakım (Utility)** | 3 | `site-taraci.py` (envanter scraper) + `log-temizle.py` + `test_env.py` |

---

## 3. Anahtar Kavramlar

### 3.1 KURAL'lar (Project Constitution)

#### KURAL #10 — GST brand color `#E8A430` (amber)
Kırmızı YASAK. `compose_openai_*` script'lerinde **B stili (amber)** default — KURAL #10 amber palet B varyantında uygulanır. SOLD badge yeşili korunur (istisna).

#### KURAL #12 — Image input preserve (CRITICAL PHOTO RULES)
`compose_openai_gptimage2.py` ve `compose_openai_variants.py` prompt'larında **"CRITICAL PHOTO RULES" bloğu** zorunlu:
```
1. The input image is the EXACT crane that must appear. Use it AS-IS — DO NOT redraw, change angle, alter the crane.
2. The crane has: [specific description].
3. ALL parts MUST be visible (cab + all axles + boom + jib). DO NOT crop.
4. DO NOT generate a different crane from training data.
```
Yoksa Gemini gibi başka vinç çiziyor (2026-05-17 travması). PIL composite fallback (`compose_pil_premium.py`) hazır.

#### Worldwide delivery'de Türkiye geçmez
Tüm caption/email/post text'inde "Türkiye" geçemez — hedef pazar olarak Avrupa/Asya/Afrika/Orta Doğu/Amerika gösterilir.

#### Tüm post text İngilizce
Türkçe içerik YASAK. WhatsApp template ve email blast hariç tüm sosyal medya posts İngilizce. `icerik-uretici.py` zaten İngilizce caption üretir.

### 3.2 11 NEVER Rule (CLAUDE.md Bölüm 8)

Aşağıdakileri **explicit user confirmation OLMADAN** yapma:

1. **Publish or post** — explicit user "ok"/"at"/"paylaş"/"yolla" demeden yayınlama
2. **Delete** any file, listing, or message
3. **Mention Turkey** in "worldwide delivery" context
4. **Share customer contact info** with third parties
5. **Omit WhatsApp +32 483 56 64 65** from any post/listing
6. **Send LinkedIn DMs or connection requests** automatically
7. **Like or comment** on social media automatically

> Kısa onay: "ok", "at", "yolla", "paylaş", "tamam", "yaw", "devam" = explicit confirmation.

### 3.3 OpenAI gpt-image-2 Broşür Pipeline (2026-05-17 ⭐)

Bu pipeline 2026-05-17'de eski PIL/HTML template approach'ı yerine geçti — owner "Gemini başka vinç çizdi, OpenAI ile devam et" dedi.

```
yeni-vinc/<crane>/photo.jpg + bilgiler.txt
   ↓
gorsel-hazirla.py (Adobe Firefly + EAST text detection)
   ↓ (watermark/text removed photo)
compose_openai_variants.py
   ↓ (parallel 3 calls to gpt-image-2)
   ├── Stil A (koyu) — Sotheby's catalogue look
   ├── Stil B (amber #E8A430) ⭐ default — Orange pill boxes
   └── Stil C (beyaz) — Bold block magazine
   ↓
Owner picks (genelde B)
   ↓
compose_openai_story_b.py
   ↓ (1080×1920 amber story)
PNG → JPG conversion
   ↓
Ready for publish (FB/IG/LinkedIn post + story)
```

**Maliyet:** ~$0.95/vinç (5 image × $0.19 high quality gpt-image-2 / image).

### 3.4 Marketplace Upload Pattern (Playwright + Chrome Profile)

`hercules-upload.py` ve `machineryline-upload.py` farklı pattern'ler kullanır:

#### Hercules AI (518 satır)
- CLAUDE for Chrome ile prompt + form fill
- AI başlık + açıklama generation
- Photo upload
- Generation tamamlanma polling loop (Hercules AI içerik üretir)
- Sonra publish butonu

#### Machinery Line / machineryline.info (623 satır)
- Pure Playwright (no AI)
- **2026-05-17 kalıcı fix** — sonraki her vinçte tüm alanlar otomatik:
  - `v--body_model` (görünür model field) + `v--model` (hidden) ikisi de fill
  - `v--protivoves_kg` (counterweight, ton×1000)
  - `v--kilometrag` (mileage km)
  - `v--udlinitel_strely_m` (jib m extract from "70m Luffing jib")
  - `v--main_boom_length` + `v--spec_vysota_podjema` (lifting height)

> **Local-only:** Hercules + Machinery Line **sadece local Mac'te** çalışır (Chrome profili `~/.gst-chrome-profiles/` gerekli). Cloud/Dispatch'ten çalışmaz.

### 3.5 LinkedIn OAuth Token Lifecycle

LinkedIn 3 token kullanır:

| Token | Scope | Süre | Kullanan |
|---|---|---|---|
| Share Token | `w_member_social` + `r_liteprofile` | ~60 gün | `sosyal-medya-post.py` (kişisel paylaşım) |
| Advertising Token | `r_ads` + `rw_ads` | ~60 gün | `linkedin-ads.py` |
| Refresh Token | — | ~365 gün | `refresh_linkedin_advertising_token.py` |

**Renewal target: 2026-07-12** (CLAUDE.md memory note). Refresh script `.env`'deki `LINKEDIN_ACCESS_TOKEN` değerini günceller.

### 3.6 Daily Marketing Workflow B (Dispatch Pattern)

CLAUDE.md "11. Dispatch / Uzaktan Erişim" — telefondan Türkçe komut → Claude doğru scripti çalıştırır:

| Kullanıcı der | Sen yaparsın |
|---|---|
| "Sabah postunu at" | `site-taraci.py` → `icerik-uretici.py --type sale` → preview → onay → `yayin-motoru.py --platform all` |
| "We buy postu at" | `icerik-uretici.py --type buy` → preview → onay → yayınla |
| "LTM 1090 satıldı Almanya'ya" | `icerik-uretici.py --type sold --crane "Liebherr LTM 1090" --country Germany` |
| "LTM 1230-5 arıyoruz" | `icerik-uretici.py --type wanted --crane "Liebherr LTM 1230-5"` |
| "Story at" | Story görseli üret → `yayin-motoru.py --platform facebook,instagram --story` |
| "Sadece LinkedIn" | `yayin-motoru.py --platform linkedin` |
| "Sadece machineryline'a at" | `machineryline-upload.py` |
| "Her yere koy" | Hercules + ML + FB + IG + LinkedIn sırayla |
| "Bu resmi direkt koy" / "Firefly'a yollama" | `gorsel-hazirla.py --skip-firefly` |
| "Envanteri güncelle" | `site-taraci.py` |
| "Son paylaşımları göster" | `data/paylasilan.json` oku, son 10'u listele |

**Akıllı davranış kuralları:**
- Marka kısaltmalarını tanı: **LTM = Liebherr, GMK = Grove, ATF = Tadano, AC/CC = Demag**
- Belirsiz komutta sor: "Hangi vinci?" / "Hangi platformlara?"
- Hata olunca 3 kez aynı şeyi deneme — farklı yol öner
- Her zaman venv aktif et: `cd ~/gst-cranes && source .venv/bin/activate`

### 3.7 Roboflow Vision Sub-Project (Ayrı)

`roboflow-crane-ai/` (28 file) bu repo'da ama **ayrı bir sub-project** — vinç tanıma vision modeli. **2026-05-21 Roboflow disaster** (16,867 → 116 image WIPE) sonrası recovery audit'i var (memory: `reference_roboflow_recovery_audit.md` + `feedback_roboflow_search_isnt_class_filter.md`).

`/understand` analizinde **hariç tutuldu** — ayrı `/understand` çağrısı gerektirir.

---

## 4. Rehberli Tur (12 Adım)

| # | Başlık | Anahtar dosyalar |
|---|---|---|
| 1 | **Genel Bakış ve CLAUDE.md Runbook** | `CLAUDE.md`, `requirements.txt`, `.env.example` |
| 2 | **Strateji ve Redesign Notları (superpowers)** | 986 satır plan + 2 spec |
| 3 | **Setup Kılavuzları — Adobe Firefly, Sosyal Medya, Cowork** | `ADOBE_SETUP.md`, `SOCIAL_SETUP.md`, `COWORK_INTEGRATION.md` |
| 4 | **Yayın Orchestrator — vinc-yayinla.py** | `scripts/vinc-yayinla.py` |
| 5 | **Photo Prep — gorsel-hazirla.py** | `scripts/gorsel-hazirla.py` (630 satır) |
| 6 | **OpenAI gpt-image-2 Broşür Pipeline (3 stil + story)** | `compose_openai_{variants, gptimage2, story_b}.py` |
| 7 | **Deprecated PIL/HTML Fallback Composer'ları** | `compose_pil_premium.py`, `compose_style_a.py`, `post-gorsel.py` |
| 8 | **İçerik Üretici — icerik-uretici.py** | `scripts/icerik-uretici.py` (439 satır) |
| 9 | **Marketplace Upload Adapter'ları — Hercules + Machinery Line** | `hercules-upload.py`, `machineryline-upload.py` |
| 10 | **Sosyal Medya Yayın — Facebook + Instagram + LinkedIn** | `sosyal-medya-post.py` (979), `yayin-motoru.py` (489), `linkedin-ads.py`, `mail-blast.py` |
| 11 | **LinkedIn OAuth ve Token Yönetimi** | 3 LinkedIn token script |
| 12 | **Envanter Scraper ve Bakım Script'leri** | `site-taraci.py`, `log-temizle.py`, `test_env.py` |

---

## 5. İş Domainleri (9)

| Domain | Akış | Tipik akışlar |
|---|---:|---|
| **Vinç Listeleme Orchestrator (E2E)** | 2 | Yeni vinç uçtan uca yayın, pipeline adımı (step runner) |
| **Broşür ve Görsel Üretim (OpenAI gpt-image-2)** | 4 | 3-stil broşür gen, Story B amber, photo prep (EAST + Firefly), legacy HTML template |
| **Marketplace Upload Adapter'ları** | 2 | Hercules AI upload, Machinery Line upload (v--body_model fix) |
| **Sosyal Medya Yayın (FB/IG/LinkedIn)** | 2 | Multi-platform paralel yayın, daily marketing post |
| **İçerik Üretimi (Caption + Hashtag + CTA)** | 1 | Caption + WhatsApp CTA üretimi |
| **LinkedIn OAuth ve Token Yönetimi** | 3 | Advertising token OAuth, Share token OAuth, 60g refresh |
| **Site Tarama ve Envanter** | 1 | Envanter tarama + diff (added/removed) |
| **LinkedIn Ads ve Email Outreach** | 2 | LinkedIn sponsored campaign, Postmark email blast |
| **Bakım ve Yardımcı (Maintenance)** | 2 | Log temizleme, env doğrulama |

> Detaylı flow + step ağacı için: dashboard'a bak (`/understand-anything:understand-dashboard`)

---

## 6. Dosya Haritası

### Complex (12 dosya)

**Strateji:**
- `docs/superpowers/plans/2026-04-14-social-media-post-redesign.md` (986 satır) — **Repo'nun en büyük dokümanı**. compose_openai pipeline'ının 3-stil teknik yol haritası.

**Scripts:**
- `scripts/sosyal-medya-post.py` (**979 satır — repo'nun en büyük dosyası**) — Facebook + Instagram (Graph API + browser fallback) + LinkedIn (Marketing API + browser fallback) multi-platform helper
- `scripts/gorsel-hazirla.py` (630 satır) — Photo prep: Adobe Firefly generative_remove + EAST text detection mask + web/social export
- `scripts/machineryline-upload.py` (623 satır) — Playwright + 2026-05-17 kalıcı fix (body_model + protivoves_kg + kilometrag + udlinitel_strely_m)
- `scripts/hercules-upload.py` (518 satır) — Hercules AI Playwright + AI generation polling
- `scripts/yayin-motoru.py` (489 satır) — Daily marketing low-level publisher (FB + IG + LinkedIn post/story, dry-run)
- `scripts/icerik-uretici.py` (439 satır) — 4 content type (sale/buy/sold/wanted), template render + OpenAI fallback
- `scripts/site-taraci.py` (424 satır) — gstcranes.com Playwright scraper + envanter.json diff
- `scripts/vinc-yayinla.py` (400 satır) — Uçtan-uca orchestrator (dry-run + skip-images + only-steps)
- `scripts/compose_openai_variants.py` (256 satır) — 3 stil A/B/C tek dosyadan
- `scripts/post-gorsel.py` (259 satır) — Legacy HTML template + Playwright screenshot
- `scripts/compose_pil_premium.py` (327 satır) — **DEPRECATED PIL fallback** (OpenAI öncesi)

**Doc:**
- `CLAUDE.md` (209 satır) — Operasyonel runbook

### Moderate (8 dosya)
- 3 OpenAI komposer (gptimage2, story_b, style_a)
- 3 LinkedIn OAuth token script
- `SOCIAL_SETUP.md`, 2 superpowers spec
- `linkedin-ads.py` (root, 68 satır LinkedIn Ads CLI)

### Simple (5 dosya)
- `.env.example`, `requirements.txt`
- `ADOBE_SETUP.md`, `COWORK_INTEGRATION.md`
- `mail-blast.py`, `log-temizle.py`, `test_env.py`

---

## 7. Karmaşıklık Hotspot'ları

### En kritik 8 dosya

| Dosya | Tip | Neden dikkat |
|---|---|---|
| `CLAUDE.md` | docs | **209 satır 11 NEVER kuralı** — ihlal eden komutlar para/itibar yakabilir |
| `scripts/sosyal-medya-post.py` | code (979) | Repo'nun en büyük dosyası, 5 platform helper + browser fallback'ler |
| `scripts/machineryline-upload.py` | code (623) | **v--field-name kalıcı fix** — DOM selector değişirse upload bozulur. Yeni vinçte test et |
| `scripts/gorsel-hazirla.py` | code (630) | Adobe Firefly + EAST text detection — Adobe credentials gerekli |
| `scripts/hercules-upload.py` | code (518) | Hercules AI polling loop — 2-3 dakika beklenir, timeout edilirse incomplete listing |
| `scripts/yayin-motoru.py` | code (489) | Daily marketing kalbı — `--dry-run` ile test et önce |
| `scripts/icerik-uretici.py` | code (439) | OpenAI tabanlı, fallback_text fail-safe — type=sold/wanted için specific scenario |
| `scripts/vinc-yayinla.py` | code (400) | Orchestrator — `--only-steps` ile parça parça koş |

### Dikkat noktaları

- **`.env` gitignored** — Meta long-lived page token + LinkedIn share/advertising tokens + OpenAI API key + Adobe Firefly + Postmark + Convex burada. Yeni gelen sahipten `.env.example` template ile ister.
- **Hercules + Machineryline LOCAL-ONLY** — Chrome profili `~/.gst-chrome-profiles/{hercules,machineryline}/`. Cloud Dispatch'ten bu ikisi çalışmaz, kullanıcıya bildir.
- **LinkedIn token 60g TTL** — 2026-07-12 öncesi `refresh_linkedin_advertising_token.py` çalıştır. `LINKEDIN_ACCESS_TOKEN` env'i otomatik update edilir.
- **Adobe Firefly token cache** — `.adobe-token-cache.json` gitignored, expires; expired olunca `gorsel-hazirla.py` yeni token alır.
- **EAST text detection model** — `scripts/frozen_east_text_detection.pb` gitignored ama gerekli (yaklaşık 100MB). Yeni clone'da indirilmesi gerekir (OpenCV repo'sundan).
- **`--dry-run` zorunlu** — Yeni vinçte ilk denemede ALWAYS `vinc-yayinla.py --dry-run` ile preview göster. KURAL #1 NEVER publish without confirmation.
- **Marka kısaltma confusion:** LTM = Liebherr, GMK = Grove, ATF/GR = Tadano (NOT GMK), AC/CC = Demag (NOT Liebherr LTM). icerik-uretici.py'de brand-aware logic.

---

## 8. Geliştirme / Operasyon Başlangıcı

### Gerekli araçlar

- Python ≥ 3.10
- `venv` (already at `.venv/`)
- Playwright Chromium + Chrome profilleri (Hercules, Machineryline için local-only)
- Adobe Firefly Services API erişimi (gorsel-hazirla.py için)
- Meta Business + Instagram Business + LinkedIn Developer hesapları

### İlk kurulum

```bash
cd ~/gst-cranes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# .env'i hazırla
cp .env.example .env
# .env'i sahipten al — Meta token, LinkedIn token, OpenAI key, Adobe, Postmark
```

### Sık kullanılan komutlar

```bash
# Daima venv aktif et
cd ~/gst-cranes && source .venv/bin/activate

# ── Crane Listing Pipeline ──
python scripts/vinc-yayinla.py                          # Full pipeline (sorar her adımda)
python scripts/vinc-yayinla.py --dry-run                # Preview only
python scripts/vinc-yayinla.py --only hercules,social   # Specific steps
python scripts/vinc-yayinla.py --skip-images            # Görsel üretimi atla (var olanları kullan)

# ── Daily Marketing ──
python scripts/site-taraci.py                           # Envanteri güncelle
python scripts/icerik-uretici.py --type sale             # Sonraki vinç (envanterden)
python scripts/icerik-uretici.py --type sale --crane "Liebherr LTM 1350-6.1"
python scripts/icerik-uretici.py --type buy              # "We Buy" postu
python scripts/icerik-uretici.py --type sold --crane "Liebherr LTM 1090-2" --country Germany
python scripts/icerik-uretici.py --type wanted --crane "Liebherr LTM 1230-5"

# ── Yayın ──
python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "..."
python scripts/yayin-motoru.py --platform facebook,instagram --image output/story.jpg --story
python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "..." --dry-run

# ── OpenAI Broşür (yeni vinç için) ──
python scripts/compose_openai_variants.py --crane <crane-id> --style all  # 3 stil A/B/C
python scripts/compose_openai_story_b.py --crane <crane-id>               # Story 1080×1920

# ── LinkedIn Token Bakım ──
python scripts/get_linkedin_share_token.py                # İlk kez veya 60g sonra
python scripts/refresh_linkedin_advertising_token.py      # Refresh (60g öncesi)

# ── Yardımcı ──
python scripts/log-temizle.py --max-age 30 --delete       # 30g+ logları sil
python scripts/test_env.py                                # .env doğrula
python scripts/site-taraci.py                             # Envanter diff
```

### Sabah Rutini (Morning Routine)

CLAUDE.md Bölüm 6'da:

```bash
# 1. Envanteri güncelle
python scripts/site-taraci.py

# 2. Sonraki vincin postunu üret
python scripts/icerik-uretici.py --type sale
# → ./output/post.jpg + ./output/post-text.txt üretir

# 3. Owner'a göster (görsel + text preview)
# 4. Onay bekle ("ok"/"at"/"paylaş")

# 5. Yayınla
python scripts/yayin-motoru.py --platform all --image output/post.jpg --text "$(cat output/post-text.txt)"

# 6. (Öğleden sonra) "We Buy" postu üret + yayınla
python scripts/icerik-uretici.py --type buy
# → onay → yayınla
```

### Yeni Vinç Ekleme Akışı

```bash
# 1. Klasör oluştur (kebab-case)
mkdir -p yeni-vinc/liebherr-ltm-1350-6-1

# 2. bilgiler.txt yaz
cat > yeni-vinc/liebherr-ltm-1350-6-1/bilgiler.txt <<EOF
brand = Liebherr
model = LTM 1350-6.1
year = 2019
capacity_tons = 350
boom_length_m = 70
operating_hours = 8500
price_eur = 1450000
origin_country = Germany
notes = 70m main + 60m luffing jib
EOF

# 3. Foto ekle
cp ~/Downloads/ltm1350-*.jpg yeni-vinc/liebherr-ltm-1350-6-1/

# 4. Owner'a sor: "Firefly ile temizleyeyim mi, direkt mi kullanalım?"
#    - "Firefly ile temizle" → gorsel-hazirla.py normal
#    - "Direkt koy" → gorsel-hazirla.py --skip-firefly

# 5. Tüm pipeline'ı çalıştır
python scripts/vinc-yayinla.py
# Veya parça parça:
python scripts/vinc-yayinla.py --only hercules,machineryline
python scripts/vinc-yayinla.py --only social
```

---

## 9. Sonraki Adım Önerileri

Yeni geldin? Şu sırayla:

1. **`CLAUDE.md`'i baştan sona oku** (209 satır) — 11 NEVER kuralı, dispatch komutları, platform detayları.
2. **`requirements.txt` + `.env.example` tara** — Bağımlılıklar + gereken secret'lar.
3. **Bir vinç klasörü incele** — `yeni-vinc/<eski-vinc>/bilgiler.txt` formatını gör.
4. **`vinc-yayinla.py`'ı oku** (400 satır) — Orchestrator pattern'i.
5. **`compose_openai_variants.py`'ı oku** — KURAL #10 amber + KURAL #12 image preserve prompt'larını anla.
6. **`machineryline-upload.py`'ya bak** — Playwright form-fill pattern + 2026-05-17 kalıcı fix.
7. **`sosyal-medya-post.py`'ı tara** (979 satır — uzun ama parça parça oku) — multi-platform yayın patterns.
8. **Bir dry-run yap** — `python scripts/vinc-yayinla.py --dry-run` ile mevcut bir vinçle test.
9. **memory'ye git:**
   - `~/.claude/projects/-Users-gokmentanacar/memory/project_gst_automation.md` — multi-platform listing
   - `~/.claude/projects/-Users-gokmentanacar/memory/project_gst_marketing.md` — sosyal medya
   - `~/.claude/projects/-Users-gokmentanacar/memory/project_gst_content_playbook.md` — kanıt-bazlı content (25 rakip, 5 archetype, her yeni vinçte default)
   - `~/.claude/projects/-Users-gokmentanacar/memory/session_handoff_2026-05-17-openai-gptimage2-pipeline.md` — OpenAI pipeline teknik detay
   - `~/.claude/projects/-Users-gokmentanacar/memory/feedback_gst_brand_color.md` — KURAL #10
   - `~/.claude/projects/-Users-gokmentanacar/memory/feedback_image_input_preserve.md` — KURAL #12
   - `~/.claude/projects/-Users-gokmentanacar/memory/feedback_gst_post_delete_policy.md` — satılan post silme YASAK, SOLD caption ekle

---

## 10. Roboflow Vision Sub-Project

`roboflow-crane-ai/` (28 file) bu repo içinde ayrı bir sub-project — vinç tanıma vision modeli. **Bu /understand analizinin scope'unda DEĞİL** — ayrı `/understand` çağrısı gerekli.

İlgili memory dosyaları:
- `project_roboflow.md` — vision model pipeline, prod v4 71.6%, backlog
- `reference_roboflow_recovery_audit.md` — **2026-05-21 disaster** (16,867 → 116 image WIPE) recovery audit
- `feedback_roboflow_search_isnt_class_filter.md` — Roboflow `proj.search(prompt=)` class filter DEĞİL (vector similarity)

---

## 11. Referanslar

- Knowledge graph: `.understand-anything/knowledge-graph.json` (112 node, 151 edge)
- Domain graph: `.understand-anything/domain-graph.json` (9 domain, 19 flow, 78 step)
- Fingerprint: `.understand-anything/fingerprints.json`
- Meta: `.understand-anything/meta.json`
- Dashboard: `/understand-anything:understand-dashboard`
- Diff analizi: `/understand-anything:understand-diff` (PR/branch için)
- Tek dosya açıklama: `/understand-anything:understand-explain <path>`

---

**Hoş geldin!** Bu proje **GST Cranes'in günlük marketing ve listing otomasyonunun kalbi**. Bir post yanlış gönderilirse veya yanlış platforma giderse kurumsal itibar etkilenir. KURAL'lara dikkat, `--dry-run` kullan, dokümantasyona güven, soru için Gokmen (owner).
