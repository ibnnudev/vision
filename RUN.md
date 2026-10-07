# Menjalankan Vision Fraud Detection

Panduan ini menggunakan virtual environment yang sudah tersedia di folder `env/`.

## 1. Masuk ke folder project

```bash
cd /Users/ibnnu/work/vision
```

## 2. Aktifkan virtual environment

macOS/Linux:

```bash
source env/bin/activate
```

Jika dependency belum lengkap:

```bash
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" pillow imagehash python-multipart rapidfuzz requests opencv-python-headless
```

## 3. Jalankan API

```bash
PYTHONPATH=vision_app uvicorn main:app --host 127.0.0.1 --port 8000
```

API tersedia di:

- `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Demo UI: `http://127.0.0.1:8000/demo`

Biarkan terminal ini tetap berjalan. Buka terminal kedua untuk command berikut.

## 4. Cek server

```bash
curl http://127.0.0.1:8000/health
```

## 5. Seed image original

Seed `brio.png`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload/seed \
  -F listing_id=seed-brio \
  -F model="honda brio 2021" \
  -F price=175000000 \
  -F image=@images/brio.png
```

Seed `avanza.jpg`:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload/seed \
  -F listing_id=seed-avanza \
  -F model="toyota avanza 2020" \
  -F price=190000000 \
  -F image=@images/avanza.jpg
```

Seed menyimpan perceptual hash dan original image blob yang dipakai untuk
matching SIFT + RANSAC.

## 6. Deteksi image normal

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload/detect \
  -F user_id=test-user \
  -F listing_title="Honda Brio 2021" \
  -F price=175000000 \
  -F description="mobil kondisi baik" \
  -F images=@images/brio.png
```

## 7. Deteksi fraud berisiko tinggi

Contoh ini mengaktifkan tiga sinyal:

- image duplicate,
- harga jauh di bawah baseline,
- pola komunikasi mencurigakan.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload/detect \
  -F user_id=test-user \
  -F listing_title="Toyota Avanza 2020" \
  -F price=100000000 \
  -F description="transfer dulu jangan ketemu" \
  -F images=@images/avanza.jpg
```

## 8. Endpoint JSON

```bash
curl -X POST http://127.0.0.1:8000/api/v1/fraud-detect/listings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "listing_title": "Toyota Avanza 2020",
    "price": 100000000,
    "description": "transfer dulu jangan ketemu",
    "image_base64_list": []
  }'
```

## 9. Lihat audit dan statistik

```bash
curl http://127.0.0.1:8000/audit
curl http://127.0.0.1:8000/stats
```

## 10. Menjalankan validation suite

Perintah ini menyiapkan module dan menjalankan validation suite bawaan:

```bash
python vision.py validate
```

Jika module belum dibuat atau ingin menulis ulang module dari launcher:

```bash
python vision.py setup
```

## 11. Menghentikan server

Jika server berjalan di foreground, tekan:

```text
Ctrl+C
```

Atau jika server dijalankan menggunakan launcher:

```bash
python vision.py stop
```

## Konfigurasi matching

Nilai default dapat diubah melalui environment variable sebelum server dijalankan:

```bash
export VISION_SIFT_MIN_INLIERS=8
export VISION_SIFT_RATIO=0.75
export VISION_HAMMING_THRESHOLD=10
export VISION_IMAGE_MATCH_MARGIN=6
```

Contoh menjalankan dengan konfigurasi tersebut:

```bash
PYTHONPATH=vision_app uvicorn main:app --host 127.0.0.1 --port 8000
```
