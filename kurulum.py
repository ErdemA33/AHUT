"""
Epikriz Projesi Kurulum Scripti
Bu scripti çalıştırınca tüm klasör yapısı ve gerekli dosyalar otomatik oluşur.

Kullanım:
    python kurulum.py

Sonra:
    cd epikriz_projesi
    pip install -r requirements.txt
    # .env dosyasına API key'ini yaz
    # epikrizler.xlsx dosyasını koy
    python epikriz_ozetle.py
"""

import os
import sys

# ===================== PROJE YAPISI =====================
PROJE_KLASORU = "epikriz_projesi"

DOSYALAR = {
    # Ana script
    "epikriz_ozetle.py": '''"""
Epikriz Özetleme Scripti
- Excel'den hasta_id ve epikriz okur
- OpenAI API ile özetler
- Sonuçları JSON'a kaydeder
- Yarıda kesilirse kaldığı yerden devam eder
"""

import os
import json
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from time import sleep
from datetime import datetime

# ===================== AYARLAR =====================
EXCEL_DOSYASI = "epikrizler.xlsx"
JSON_DOSYASI = "ozetler.json"
MODEL = "gpt-4o-mini"  # ucuz ve hızlı; daha kaliteli için "gpt-4o"
BEKLEME_SURESI = 0.5    # her istek arası saniye
MAX_TOKEN = 500         # özet uzunluğu sınırı
# ===================================================

# API key yükle
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("HATA: .env dosyasında OPENAI_API_KEY bulunamadı!")

client = OpenAI(api_key=api_key)


def ozet_yukle():
    """Var olan JSON dosyasını yükle, yoksa boş liste döndür."""
    if os.path.exists(JSON_DOSYASI):
        try:
            with open(JSON_DOSYASI, "r", encoding="utf-8") as f:
                veri = json.load(f)
            print(f"✓ Mevcut JSON yüklendi: {len(veri)} kayıt zaten işlenmiş.")
            return veri
        except json.JSONDecodeError:
            print("⚠ JSON dosyası bozuk, boş listeyle başlıyorum.")
            return []
    return []


def ozet_kaydet(veri):
    """JSON dosyasına güvenli şekilde kaydet (önce temp, sonra rename)."""
    temp_dosya = JSON_DOSYASI + ".tmp"
    with open(temp_dosya, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    # atomik replace - yazma sırasında program kesilse bile dosya bozulmaz
    os.replace(temp_dosya, JSON_DOSYASI)


def prompt_olustur(epikriz_metni):
    """Epikrizi özetletmek için prompt hazırla."""
    return f"""Sen tıbbi kayıtları düzenleyen uzman bir asistansın. Sana verilen epikriz metni 
düzensiz, kötü yazılmış veya eksik olabilir. Görevin:

1. Metni dikkatlice oku ve hastanın durumunu anla
2. Aşağıdaki başlıklar altında DÜZENLİ ve ANLAŞILIR bir özet çıkar:
   - Şikayet/Anamnez
   - Tanı
   - Tedavi
   - Sonuç/Öneriler

Eğer bir başlıkta bilgi yoksa "Belirtilmemiş" yaz. Tıbbi terimleri koru, 
ama cümleleri akıcı ve net hale getir.

EPİKRİZ METNİ:
{epikriz_metni}

ÖZET:"""


def epikriz_ozetle(epikriz_metni):
    """Tek bir epikrizi API'ye gönder ve özet al."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Sen deneyimli bir tıbbi sekreterssin ve epikrizleri düzenli özetlersin."},
                {"role": "user", "content": prompt_olustur(epikriz_metni)}
            ],
            temperature=0.3,
            max_tokens=MAX_TOKEN
        )
        return {
            "basarili": True,
            "ozet": response.choices[0].message.content.strip(),
            "kullanilan_token": response.usage.total_tokens
        }
    except Exception as e:
        return {
            "basarili": False,
            "hata": str(e)
        }


def main():
    print("=" * 60)
    print("EPİKRİZ ÖZETLEME PROGRAMI")
    print("=" * 60)

    # Excel'i oku
    if not os.path.exists(EXCEL_DOSYASI):
        print(f"HATA: {EXCEL_DOSYASI} bulunamadı!")
        return

    df = pd.read_excel(EXCEL_DOSYASI)
    print(f"✓ Excel okundu: {len(df)} satır")
    print(f"  Sütunlar: {df.columns.tolist()}")

    # Sütun isimlerini standartlaştır (A=hasta_id, B=epikriz)
    if len(df.columns) < 2:
        print("HATA: Excel'de en az 2 sütun olmalı (hasta_id, epikriz)!")
        return
    
    df.columns = ["hasta_id", "epikriz"] + list(df.columns[2:])

    # Mevcut özetleri yükle (kaldığı yerden devam için)
    sonuclar = ozet_yukle()
    islenmis_idler = {kayit["hasta_id"] for kayit in sonuclar}

    # İşlenecek satırları belirle
    kalan = df[~df["hasta_id"].astype(str).isin({str(i) for i in islenmis_idler})]
    print(f"  → {len(kalan)} kayıt işlenecek, {len(islenmis_idler)} kayıt atlanacak.")
    print("=" * 60)

    if len(kalan) == 0:
        print("✓ Tüm kayıtlar zaten işlenmiş!")
        return

    toplam_token = 0
    baslangic = datetime.now()

    try:
        for sayac, (idx, satir) in enumerate(kalan.iterrows(), start=1):
            hasta_id = satir["hasta_id"]
            epikriz = str(satir["epikriz"]) if pd.notna(satir["epikriz"]) else ""

            if not epikriz.strip():
                print(f"[{sayac}/{len(kalan)}] hasta_id={hasta_id} → BOŞ epikriz, atlandı.")
                sonuclar.append({
                    "hasta_id": hasta_id,
                    "ozet": None,
                    "durum": "bos_epikriz",
                    "tarih": datetime.now().isoformat()
                })
                ozet_kaydet(sonuclar)
                continue

            # API'ye gönder
            sonuc = epikriz_ozetle(epikriz)

            if sonuc["basarili"]:
                kayit = {
                    "hasta_id": hasta_id,
                    "ozet": sonuc["ozet"],
                    "durum": "basarili",
                    "token": sonuc["kullanilan_token"],
                    "tarih": datetime.now().isoformat()
                }
                toplam_token += sonuc["kullanilan_token"]
                print(f"[{sayac}/{len(kalan)}] hasta_id={hasta_id} bitti ({sonuc['kullanilan_token']} token)")
            else:
                kayit = {
                    "hasta_id": hasta_id,
                    "ozet": None,
                    "durum": "hata",
                    "hata": sonuc["hata"],
                    "tarih": datetime.now().isoformat()
                }
                print(f"[{sayac}/{len(kalan)}] hasta_id={hasta_id} HATA: {sonuc['hata']}")

            sonuclar.append(kayit)
            # Her kayıttan sonra JSON'a yaz - kesinti olursa kayıp olmaz
            ozet_kaydet(sonuclar)

            sleep(BEKLEME_SURESI)

    except KeyboardInterrupt:
        print("\\n\\n⚠ Program kullanıcı tarafından durduruldu.")
        print(f"  Şu ana kadar işlenen: {len(sonuclar)} kayıt")
        print(f"  Toplam token: {toplam_token}")
        print(f"  JSON kaydedildi: {JSON_DOSYASI}")
        print("  Tekrar çalıştırırsan kaldığı yerden devam eder.")
        return

    # Özet bilgi
    sure = (datetime.now() - baslangic).total_seconds()
    print("=" * 60)
    print("✓ TAMAMLANDI!")
    print(f"  Toplam kayıt: {len(sonuclar)}")
    print(f"  Bu çalışmada işlenen: {len(kalan)}")
    print(f"  Toplam token: {toplam_token}")
    print(f"  Tahmini maliyet: ~${toplam_token * 0.00000015:.4f} (gpt-4o-mini)")
    print(f"  Süre: {sure:.1f} saniye")
    print(f"  JSON: {JSON_DOSYASI}")
    print("=" * 60)


if __name__ == "__main__":
    main()
''',

    # Requirements
    "requirements.txt": '''openai>=1.0.0
pandas>=2.0.0
openpyxl>=3.1.0
python-dotenv>=1.0.0
''',

    # .env şablonu
    ".env": '''OPENAI_API_KEY=sk-proj-buraya_kendi_api_keyini_yaz
''',

    # .gitignore
    ".gitignore": '''.env
__pycache__/
*.pyc
ozetler.json
ozetler.json.tmp
epikrizler.xlsx
venv/
.venv/
''',

    # README
    "README.md": '''# Epikriz Özetleme Projesi

## Kurulum

1. **Sanal ortam oluştur (önerilen):**
   ```bash
   python -m venv venv
   # Windows:
   venv\\Scripts\\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

2. **Gerekli paketleri yükle:**
   ```bash
   pip install -r requirements.txt
   ```

3. **API key ayarla:**
   - `.env` dosyasını aç
   - `OPENAI_API_KEY` değerini kendi key'inle değiştir

4. **Excel dosyanı hazırla:**
   - Dosya adı: `epikrizler.xlsx`
   - A sütunu: hasta_id
   - B sütunu: epikriz metni

## Çalıştırma

```bash
python epikriz_ozetle.py
```

## Özellikler

- ✓ Her kayıttan sonra terminale "bitti" yazılır
- ✓ Her kayıttan sonra JSON'a otomatik kaydedilir
- ✓ Program yarıda kesilirse tekrar çalıştırınca kaldığı yerden devam eder
- ✓ Boş epikrizler atlanır, hata kaydedilir
''',
}


def main():
    print("=" * 60)
    print("EPİKRİZ PROJESİ KURULUM")
    print("=" * 60)

    # Klasörü oluştur
    if os.path.exists(PROJE_KLASORU):
        cevap = input(f"⚠ '{PROJE_KLASORU}' klasörü zaten var. Üzerine yazılsın mı? (e/h): ")
        if cevap.lower() != "e":
            print("İptal edildi.")
            sys.exit(0)
    else:
        os.makedirs(PROJE_KLASORU)
        print(f"✓ Klasör oluşturuldu: {PROJE_KLASORU}/")

    # Dosyaları oluştur
    for dosya_adi, icerik in DOSYALAR.items():
        dosya_yolu = os.path.join(PROJE_KLASORU, dosya_adi)
        with open(dosya_yolu, "w", encoding="utf-8") as f:
            f.write(icerik)
        print(f"  ✓ {dosya_adi} oluşturuldu")

    print("=" * 60)
    print("✓ KURULUM TAMAMLANDI!")
    print("=" * 60)
    print()
    print("Sıradaki adımlar:")
    print(f"  1. cd {PROJE_KLASORU}")
    print("  2. python -m venv venv")
    print("  3. venv\\Scripts\\activate         (Windows)")
    print("     source venv/bin/activate       (Linux/Mac)")
    print("  4. pip install -r requirements.txt")
    print("  5. .env dosyasını aç ve OPENAI_API_KEY yaz")
    print("  6. epikrizler.xlsx dosyasını klasöre koy")
    print("  7. python epikriz_ozetle.py")
    print()


if __name__ == "__main__":
    main()
