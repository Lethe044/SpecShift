# Katkida Bulunma Rehberi

SpecShift'e katki gostermek istediğin icin tesekkurler. Bu belge, katki surecini
hem senin hem de proje bakimcilari icin daha kolay hale getirmek amaciyla
hazirlandi.

## Gelistirme ortamini kurma

```bash
git clone https://github.com/Lethe044/specshift.git
cd specshift
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Kurulumdan sonra CLI'nin calistigini dogrula:

```bash
specshift --version
specshift diff examples/old_api.yaml examples/new_api.yaml
```

## Testleri calistirma

```bash
pytest --cov=specshift --cov-report=term-missing
```

Yeni bir ozellik veya duzeltme eklerken mutlaka ilgili testleri de ekle.
`tests/test_differ.py` dosyasindaki mevcut testler, yeni bir kural eklerken
izlenecek deseni gosteriyor: kucuk, odakli bir OpenAPI parcasi olustur,
diff'i calistir ve beklenen severity/mesaji dogrula.

## Kod stili

- Python 3.9+ uyumlulugu korunmali.
- Fonksiyon ve degiskenler icin aciklayici isimler kullan.
- Yeni public fonksiyonlara docstring ekle.
- Mumkun oldugunca type hint kullan.
- Buyuk fonksiyonlari kucuk, test edilebilir parcalara bol.

## Yeni bir diff kurali eklemek

Diff motorunun cogu, `specshift/differ.py` icindeki kucuk, tek sorumluluklu
fonksiyonlardan olusuyor. Yeni bir kural eklerken:

1. Degisikligin hangi baglamda (request mi response mu) farkli agirlik
   tasidigini dusun. Ayni degisiklik request'te zararsizken response'ta
   kirici olabilir, ya da tam tersi.
2. `Severity.BREAKING`, `Severity.WARNING` veya `Severity.INFO` seviyelerinden
   en uygununu sec ve gerekcesini fonksiyon veya commit mesajinda kisaca acikla.
3. Hem pozitif hem negatif test senaryosu ekle (kural tetiklenmeli VE
   tetiklenmemesi gereken durumda tetiklenmemeli).

## Hata bildirme

Bir hata bulduysan, lutfen su bilgileri iceren bir issue ac:

- Kullandigin specshift surumu (`specshift --version`)
- Sorunu tetikleyen minimal bir OpenAPI ornegi (mumkunse)
- Beklenen davranis ve gozlemlenen davranis

## Pull request surumu

1. Repository'yi fork'la ve degisikliklerin icin yeni bir dal ac.
2. Degisikligini test kapsamiyla birlikte yap.
3. `pytest` calistirip tum testlerin gectiginden emin ol.
4. PR aciklamasinda ne degistigini ve neden gerekli oldugunu kisaca anlat.
5. CI yesile donene kadar geri bildirimlere yanit ver.

Kucuk duzeltmeler (yazim hatasi, dokumantasyon iyilestirmesi) icin de
PR acmaktan cekinme, her katki degerlidir.

## Davranis kurallari

Bu projede herkese saygili ve yapici bir iletisim bekleniyor. Yapici
elestiri her zaman hos karsilanir, kisisel elestiriler ve saygisiz dil
kabul edilmez.
