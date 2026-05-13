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
- **LinkedIn API** — Personal profile posting (token expires ~60 days, renew by 2026-07-12 via `scripts/get_linkedin_share_token.py`)
- Chrome profiles at `~/.gst-chrome-profiles/` (hercules, machineryline)

## 11. Dispatch / Uzaktan Erişim (claude.ai/code)

Bu proje Claude Code Dispatch ile telefondan veya herhangi bir cihazdan yönetilebilir. Kullanıcı doğal dilde Türkçe komut verir, Claude doğru scripti doğru parametrelerle çalıştırır.

### Kullanıcı ne derse ne yaparsın

| Kullanıcı der | Sen yaparsın |
|---------------|-------------|
| "Sabah postunu at" | `site-taraci.py` → `icerik-uretici.py --type sale` → önizleme göster → onay bekle → `yayin-motoru.py --platform all` |
| "We buy postu at" | `icerik-uretici.py --type buy` → önizleme → onay → paylaş |
| "LTM 1090 satıldı" veya "LTM 1090 satıldı Almanya'ya" | `icerik-uretici.py --type sold --crane "Liebherr LTM 1090" --country Germany` → önizleme → onay → paylaş |
| "LTM 1230-5 arıyoruz" | `icerik-uretici.py --type wanted --crane "Liebherr LTM 1230-5"` → önizleme → onay → paylaş |
| "Story at" | Story görseli üret → `yayin-motoru.py --platform facebook,instagram --story` |
| "At" / "Paylaş" / "Ok" / "Yolla" | Son hazırlanan içeriği yayınla (onay budur) |
| "Sadece machineryline'a at" | `machineryline-upload.py` — sadece ML |
| "Sadece LinkedIn" | `yayin-motoru.py --platform linkedin` |
| "Sadece Facebook'a at" | `yayin-motoru.py --platform facebook` |
| "Her yere koy" | Hercules + ML + FB + IG + LinkedIn — hepsini sırayla çalıştır |
| "Bu resmi direkt koy" / "Firefly'a yollama" | `gorsel-hazirla.py --skip-firefly` — Firefly'ı atla |
| "Firefly ile temizle" | `gorsel-hazirla.py` — normal çalıştır |
| "Envanteri güncelle" | `site-taraci.py` |
| "Son paylaşımları göster" | `data/paylasilan.json` oku, son 10 paylaşımı listele |
| "Şu vincin postunu hazırla" | `icerik-uretici.py --type sale --crane "..."` → görselleri ve metni göster |

### Yeni Vinç Ekleme (Uzaktan)

Kullanıcı resim yükleyip bilgileri yazınca:
1. `yeni-vinc/` altında klasör oluştur (brand-model formatında, küçük harf, tire ile)
2. `bilgiler.txt` dosyasını yaz (kullanıcının verdiği bilgilerle)
3. Resimleri klasöre kaydet
4. Kullanıcıya sor: "Firefly ile temizleyeyim mi, direkt mi kullanalım?"
5. Onaya göre `gorsel-hazirla.py` çalıştır veya atla
6. "Her yere koy" denirse `vinc-yayinla.py` çalıştır
7. Belirli platform istenirse sadece o scripti çalıştır

### Akıllı Davranış Kuralları

- **Marka kısaltmalarını tanı:** LTM = Liebherr, GMK = Grove, ATF = Tadano, AC/CC = Demag
- **Belirsiz komutlarda sor:** "Hangi vinci?" / "Hangi platformlara?"
- **Kısa onayları tanı:** "ok", "at", "yolla", "paylaş", "tamam", "yaw", "devam" = onay
- **Hata olunca:** Açıkla, log göster, çözüm öner — aynı hatayı 3 kez deneme, farklı yol öner
- **Her zaman venv aktif et:** `cd ~/gst-cranes && source .venv/bin/activate` sonra script çalıştır
- **Sonuçları göster:** Hangi platforma atıldı, URL varsa paylaş, hata varsa bildir

### Platform Detayları

| Platform | Script | Yöntem | Notlar |
|----------|--------|--------|--------|
| Facebook post + story | `yayin-motoru.py` | Meta Graph API | Kalıcı token, sorun çıkmaz |
| Instagram post + story | `yayin-motoru.py` | Meta Graph API | Kalıcı token, sorun çıkmaz |
| LinkedIn post | `yayin-motoru.py` | LinkedIn API | Token 2026-06-13'e kadar geçerli |
| Hercules | `hercules-upload.py` | Playwright (Chrome profil) | Sadece local bilgisayarda çalışır |
| Machinery Line | `machineryline-upload.py` | Playwright (Chrome profil) | Sadece local bilgisayarda çalışır |
| gstcranes.com | Hercules üzerinden otomatik | — | Hercules yayınlayınca siteye düşer |

**NOT:** Hercules ve Machinery Line sadece local bilgisayarda çalışır (Chrome profili gerekli). Cloud/Dispatch'ten bu ikisi çalışmaz, kullanıcıya bildir.

## 12. Self-Update Policy

When new rules or templates are provided during a session ("from now on use X"), this CLAUDE.md file will be updated immediately and the change will be summarized to the user.
