# Wrong Century

Etkileşimli POV hikâye serisi — her gün yeni bölüm, izleyici oyuyla dallanır.

- `media/` — yayına hazır bölümler (GitHub Pages ile herkese açık sunulur; Instagram'ın indirebilmesi için gerekli)
- `episodes.json` — bölüm ağacı (her bölümün A/B sonrası hangi bölüme gittiği + başlık/açıklama)
- `state.json` — yayınlananlar, oy sonuçları (bot günceller)
- `scripts/publish.py` — oy sayımı + Make üzerinden yayın
- `.github/workflows/daily.yml` — her gün 16:00 UTC

Webhook adresleri **Settings → Secrets → Actions** içinde: `MAKE_PUBLISH_HOOK`, `MAKE_COMMENTS_HOOK`.
