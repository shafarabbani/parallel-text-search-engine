# Parallel Text Search Engine — UTS Komputasi Paralel dan Terdistribusi

**Shafa Rabbani Fityatul Mukarramah (247006111020)** — Informatika, Universitas Siliwangi.
Tema: *"Parallel computing in our lives"*. Proyek: mencari beberapa keyword pada
banyak baris/file teks secara bersamaan dengan tiga pendekatan — **sequential**,
**multithread**, dan **multiprocessing** — lalu dibandingkan performanya.

## Instalasi

Prasyarat: **Python 3.10+** (disarankan 3.11+).

```bash
python -m pip install -r requirements.txt
```

Agar `python -m textsearch.cli` berjalan dari root proyek, tambahkan `src/` ke
`PYTHONPATH`:

```bash
# Windows (cmd)
set PYTHONPATH=src
# Windows (PowerShell)
$env:PYTHONPATH = "src"
# Linux/macOS
export PYTHONPATH=src
```

(Alternatif: `python -m pip install -e .`)

## Cara cepat

```bash
# 1. Generate dataset 1.000.000 baris (seed & keyword deterministik dari NPM)
python -m textsearch.dataset_gen --lines 1M --out data/corpus_1M.txt

# 2. Cari dengan tiga mode sekaligus (bandingkan + speedup/efisiensi)
python -m textsearch.cli --input data/corpus_1M.txt --mode all --workers 4

# 3. Demo VERSI BER-BUG (race condition pada counter bersama)
python -m textsearch.buggy_search --lines 200K --threads 8 --runs 10

# 4. Benchmark semua konfigurasi -> results/*.csv + system_info.json
python -m textsearch.benchmark --reps 3

# 5. Grafik PNG dari hasil benchmark -> figures/
python -m textsearch.plots

# 6. Unit test
python -m pytest tests -v
```

## Isi proyek

| Path | Keterangan |
|---|---|
| `TASK.md` | Instruksi tugas UTS (sumber requirements) |
| `src/textsearch/` | Seluruh kode sumber (lihat `DOKUMENTASI.md`) |
| `tests/` | Unit test pytest |
| `data/` | Dataset hasil generate (di-gitignore) |
| `results/` | `benchmark.csv`, `summary.csv`, `system_info.json`, `bug_evidence.csv` |
| `figures/` | Grafik PNG wajib + tambahan |
| `report/` | Laporan PDF akhir |
| `LAPORAN_UTS.md` | Sumber laporan (bagian A–D) |
| `DOKUMENTASI.md` | Dokumentasi lengkap seluruh kode (Fase 11) |

Detail implementasi, penjelasan tiap fungsi, bug, dan hasil percobaan:
baca **`DOKUMENTASI.md`**.
