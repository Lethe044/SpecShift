# SpecShift

[![CI](https://github.com/Lethe044/specshift/actions/workflows/ci.yml/badge.svg)](https://github.com/Lethe044/specshift/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/specshift.svg)](https://pypi.org/project/specshift/)
[![Python versions](https://img.shields.io/pypi/pyversions/specshift.svg)](https://pypi.org/project/specshift/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SpecShift, OpenAPI ve Swagger sozlesmelerindeki (contract) degisiklikleri
tespit eden, bu degisiklikleri breaking, warning ve info olarak siniflandiran
ve isterseniz dogal dilde ozetleyen bir komut satiri araci.

Bir API surumden surume degistiginde asil soru "ne degisti" degil, "bu
degisiklik beni kirar mi" sorusudur. SpecShift tam olarak bunu cevaplamak
icin yazildi: iki spesifikasyonu alir, aralarindaki her farki tek tek
degerlendirir ve hangisinin gercekten tehlikeli oldugunu soyler.

```
$ specshift diff examples/old_api.yaml examples/new_api.yaml

Bookstore API : 1.0.0 -> 2.0.0
13 kirici, 2 uyari, 3 bilgi degisiklik bulundu.

[BREAKING] DELETE /books/{bookId} :: HTTP metodu kaldirilmis
[BREAKING] GET /books > parametre 'category' :: 'category' parametresi artik zorunlu
[BREAKING] GET /books > yanit 200 > alan 'author' :: alan yanittan kaldirilmis
...

Sonuc: 13 kirici degisiklik nedeniyle bu guncelleme risklidir.
```

## Neden SpecShift

API'lerini surekli gelistiren her ekip er ya da gec ayni soruna carpar:
bir alan kaldirilir, bir parametre zorunlu hale gelir, bir enum degeri
silinir ve bunu fark eden kimse olmaz ta ki bir istemci production'da
patlayana kadar. Mevcut diff araclari genelde ham JSON farki gosterir ve
hangi degisikligin gercekten onemli oldugunu yorumlamayi size birakir.

SpecShift bunu yapmiyor. Her degisikligi baglamina gore degerlendiriyor:

- Bir alanin response'tan kaldirilmasi **kirici**dir, cunku istemciler ona
  guvenmis olabilir.
- Ayni alanin request body'den kaldirilmasi genelde **sadece bir uyaridir**,
  cunku gonderen istemciler etkilenmez, sadece artik dikkate alinmaz.
- Request'e yeni zorunlu bir alan eklemek **kiricidir**, ama response'a
  yeni bir alan eklemek sadece **bilgi amaclidir**.

Bu tur baglama duyarli kurallar SpecShift'in cekirdegini olusturuyor ve
tamamen ucretsiz, herhangi bir API anahtari gerektirmeden calisiyor. Yapay
zeka destekli dogal dil ozeti tamamen istege bagli bir ek katman.

## Ozellikler

- **Kapsamli yapisal diff**: path, HTTP metodu, parametre, request body,
  response, sema (schema) seviyesinde derinlemesine karsilastirma.
- **Baglam duyarli siniflandirma**: ayni degisiklik request ve response
  baglaminda farkli agirlikta degerlendirilir.
- **`$ref` cozumleme ve `allOf` birlestirme**: gercek dunya spesifikasyonlarinda
  yaygin olan referans ve kompozisyon kaliplarini dogru sekilde takip eder.
- **Enum, format, nullable ve guvenlik semasi degisikliklerinin tespiti**.
- **Ucretsiz calisir**: hicbir API anahtari veya ucretli servis gerektirmez.
- **Istege bagli AI ozeti**: Groq, Gemini free tier veya OpenAI uyumlu
  herhangi bir uc nokta ile dogal dilde ozet uretebilir. Anahtar yoksa
  sablon tabanli bir ozete otomatik olarak duser, hicbir zaman calismayi
  durdurmaz.
- **CI/CD entegrasyonu**: `specshift check` komutu, mevcut spesifikasyonu
  bir git dalindaki (branch) surumle karsilastirir ve kirici degisiklik
  varsa build'i basarisiz kilar.
- **Canli izleme**: `specshift watch` komutu, uzak bir API'nin spesifikasyonunu
  periyodik olarak kontrol eder ve degisiklikte Slack veya Discord'a bildirim
  gonderir.
- **Uc cikti formati**: renkli konsol tablosu, Markdown raporu (PR yorumlari
  icin idealdir) ve JSON (baska araclarla entegrasyon icin).

## Kurulum

```bash
pip install specshift
```

Renkli konsol ciktisi icin (istege bagli, olmadan da calisir):

```bash
pip install "specshift[pretty]"
```

Kaynak koddan kurulum:

```bash
git clone https://github.com/Lethe044/specshift.git
cd specshift
pip install -e .
```

## Hizli baslangic

Iki spesifikasyonu dogrudan karsilastirin:

```bash
specshift diff old_openapi.yaml new_openapi.yaml
```

URL'lerden de karsilastirabilirsiniz:

```bash
specshift diff https://api.example.com/v1/openapi.json https://api.example.com/v2/openapi.json
```

CI'da kullanmak icin repo'nuzda bir yapilandirma dosyasi olusturun:

```bash
specshift init
```

Bu, asagidakine benzer bir `.specshift.yml` uretir:

```yaml
spec_path: openapi.yaml
base_ref: main
fail_on: breaking
```

Ardindan CI pipeline'inizda:

```bash
specshift check
```

komutu, mevcut `openapi.yaml` dosyasini `main` dalindaki halinden farki
icin karsilastirir ve kirici bir degisiklik varsa cikis kodu 1 doner.

## Yapay zeka ozeti (istege bagli)

SpecShift, degisikliklerin dogal dilde ozetini uretmek icin ucretsiz
katmanli AI servislerini kullanabilir. Bunun icin herhangi bir odeme
gerekmez:

```bash
export GROQ_API_KEY="sizin-groq-anahtariniz"
specshift diff old.yaml new.yaml --ai
```

Groq yerine Google Gemini'nin ucretsiz katmanini da kullanabilirsiniz:

```bash
export GEMINI_API_KEY="sizin-gemini-anahtariniz"
specshift diff old.yaml new.yaml --ai --ai-provider gemini
```

Daha guclu (ucretli) modeller kullanmak isteyenler icin OpenAI uyumlu
herhangi bir uc noktayi da baglayabilirsiniz:

```bash
export SPECSHIFT_API_KEY="sizin-anahtariniz"
export SPECSHIFT_OPENAI_BASE_URL="https://api.openai.com/v1"
specshift diff old.yaml new.yaml --ai --ai-provider openai_compatible --ai-model gpt-4o-mini
```

Hicbir anahtar tanimli degilse `--ai` bayragi hala calisir, sadece agdan
sonuc beklemek yerine kural tabanli bir ozet uretir. Yani AI destegi bir
zorunluluk degil, sadece bir ek katmandir.

## Komutlar

### `specshift diff <eski> <yeni>`

Iki spesifikasyonu karsilastirir. `<eski>` ve `<yeni>` bir dosya yolu, bir
http(s) URL'si veya dogrudan JSON/YAML metni olabilir.

Faydali secenekler:

| Secenek | Aciklama |
|---|---|
| `--format console\|markdown\|json` | Cikti formati (varsayilan: console) |
| `--output <dosya>` | Ciktiyi bir dosyaya yazar |
| `--ai` | Dogal dil ozeti ekler |
| `--ai-provider groq\|gemini\|openai_compatible` | AI saglayicisini secer |
| `--fail-on breaking\|warning\|none` | Hangi seviyede cikis kodu 1 donecegini belirler |
| `--quiet` | Sadece ozet satirini yazdirir |

### `specshift check`

CI/CD icin tasarlanmistir. Mevcut spesifikasyon dosyasini, `.specshift.yml`
icinde tanimli bir git referansiyla (branch, tag veya commit) karsilastirir.

```bash
specshift check --spec openapi.yaml --base-ref origin/main
```

### `specshift watch <url>`

Uzak bir spesifikasyonu periyodik olarak kontrol eder, onceki anlik
goruntuyle karsilastirir ve fark bulunursa bildirim gonderir.

```bash
specshift watch https://api.example.com/openapi.json \
  --interval 600 \
  --slack-webhook "$SLACK_WEBHOOK_URL"
```

### `specshift init`

Ornek bir `.specshift.yml` dosyasi olusturur.

## GitHub Actions ile kullanim

Asagidaki workflow, her pull request'te API sozlesmenizi `main` dalindaki
halinden farkli olup olmadigini kontrol eder ve kirici bir degisiklik
varsa build'i basarisiz kilar:

```yaml
name: API Contract Check

on:
  pull_request:
    paths:
      - "openapi.yaml"

jobs:
  contract-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install specshift

      - run: specshift check --base-ref origin/${{ github.base_ref }}
```

AI destekli PR yorumlari eklemek isterseniz, `specshift check --ai --format
markdown --output report.md` ile bir Markdown raporu uretip bunu
`peter-evans/create-or-update-comment` gibi bir action ile PR'a
yorum olarak ekleyebilirsiniz.

## Yapilandirma dosyasi (`.specshift.yml`)

```yaml
spec_path: openapi.yaml
base_ref: main
fail_on: breaking

# istege bagli
ai_provider: groq
ai_model: llama-3.3-70b-versatile
slack_webhook: https://hooks.slack.com/services/...
discord_webhook: https://discord.com/api/webhooks/...
ignore_paths: []
```

## SpecShift ne zaman kirici (breaking) der

Asagidaki tablo, en yaygin senaryolarda hangi seviyenin uygulandigini
ozetliyor:

| Degisiklik | Request baglaminda | Response baglaminda |
|---|---|---|
| Alan kaldirildi | Uyari | Kirici |
| Yeni zorunlu alan eklendi | Kirici | Bilgi |
| Yeni istege bagli alan eklendi | Bilgi | Bilgi |
| Alan artik zorunlu degil | Bilgi | Kirici |
| Alan artik zorunlu | Kirici | Bilgi |
| Veri tipi degisti | Kirici | Kirici |
| Enum degeri kaldirildi | Kirici | Kirici |
| Endpoint veya metod kaldirildi | Kirici | Kirici |

## Diger araclarla karsilastirma

| | SpecShift | Ham JSON/YAML diff | oasdiff / openapi-diff benzeri araclar |
|---|---|---|---|
| Baglama duyarli siniflandirma | Evet | Hayir | Kismen |
| Dogal dil ozeti | Evet (istege bagli) | Hayir | Hayir |
| Ucretsiz kullanim | Tamamen ucretsiz | Ucretsiz | Genelde ucretsiz |
| CI entegrasyonu | Yerlesik (`check`) | Manuel | Degisken |
| Canli URL izleme | Yerlesik (`watch`) | Yok | Nadiren |

## Yol haritasi

Bu proje aktif olarak gelistirilmeye devam ediyor. Planlanan bazi basliklar:

- gRPC/Protobuf sozlesmeleri icin destek
- GraphQL sema diff'i
- GitHub PR'lara otomatik yorum eklemek icin resmi bir GitHub Action
- Web tabanli bir sonuc goruntuleyici
- Daha fazla semantik kural (path parametresi pattern degisiklikleri,
  content-type degisiklikleri gibi)

Bir ozellik onerisi olursa issue acmaktan cekinmeyin.

## Katkida bulunma

Katki rehberi icin [CONTRIBUTING.md](CONTRIBUTING.md) dosyasina bakabilirsiniz.
Hata bildirimleri, ozellik onerileri ve pull request'ler her zaman
hos karsilanir.

## Lisans

Bu proje [MIT lisansi](LICENSE) ile lisanslanmistir.
