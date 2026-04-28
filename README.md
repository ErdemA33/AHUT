# Epikriz Özetleme Projesi

## Kurulum

1. **Sanal ortam oluştur (önerilen):**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
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
