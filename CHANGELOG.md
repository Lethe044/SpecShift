# Degisiklik Gecmisi

Bu proje [Semantic Versioning](https://semver.org/) prensiplerini takip eder.

## [1.0.0] - 2026-08-31

### Eklendi
- OpenAPI 3.x ve Swagger 2.0 spesifikasyonlarini dosya, URL veya git
  referansindan yukleme destegi.
- Path, operasyon, parametre, request body, response ve semalar dahil
  kapsamli yapisal diff motoru.
- Degisikliklerin breaking, warning ve info olarak baglama duyarli
  siniflandirilmasi (ayni degisiklik request'te ve response'ta farkli
  agirlikta degerlendirilir).
- `$ref` cozumleme ve `allOf` birlestirme destegi.
- Enum, format, nullable, required alan ve guvenlik semasi degisikliklerinin
  tespiti.
- Konsol (rich destekli renkli tablo), Markdown ve JSON rapor formatlari.
- Istege bagli yapay zeka destekli dogal dil ozeti (Groq, Gemini veya
  OpenAI uyumlu herhangi bir uc nokta), API anahtari olmadan calisan
  sablon tabanli fallback ozet ile birlikte.
- Slack ve Discord webhook bildirimleri.
- `specshift check` komutu ile CI/CD entegrasyonu: mevcut spesifikasyonu
  bir git referansiyla (branch, tag, commit) karsilastirip kirici
  degisiklik varsa build'i basarisiz kilma.
- `specshift watch` komutu ile canli bir API spesifikasyonunu periyodik
  olarak izleme ve degisiklikte otomatik bildirim gonderme.
- `.specshift.yml` yapilandirma dosyasi destegi ve `specshift init` komutu.
- GitHub Actions ile calisan CI ve PyPI yayin workflow'lari.
- Kapsamli test paketi ve iki ornek OpenAPI spesifikasyonu.
