# TASK.md — UTS Komputasi Paralel dan Terdistribusi
## Proyek: Parallel Text Search Engine

> **Instruksi untuk AI agent.** Baca seluruh dokumen ini sebelum menulis kode apa pun. Kerjakan berurutan sesuai **Fase 0–11**. Jangan melompati fase, dan jangan menandai pekerjaan selesai sebelum **Definition of Done (bagian 14)** terpenuhi semua.

---

## 1. Identitas Pemilik Proyek

| Field | Nilai |
|---|---|
| Nama | **Shafa Rabbani Fityatul Mukarramah** |
| NPM/NIM | **247006111020** |
| Mata Kuliah | Komputasi Paralel dan Terdistribusi (3 SKS) |
| Dosen | Rohmat Gunawan, M.T. |
| Program Studi | Informatika, Fakultas Teknik, Universitas Siliwangi |
| Tema UTS | "Parallel computing in our lives" (proyek hybrid computing, mini project individu) |
| Judul Proyek | **Parallel Text Search Engine** — mencari beberapa keyword pada banyak baris/file teks secara bersamaan |

Nama dan NPM **wajib tampil di output semua program yang bisa dijalankan** (CLI utama, versi bug, benchmark).

Format banner yang diwajibkan:

```
==============================================================
PARALLEL TEXT SEARCH ENGINE
By SHAFA RABBANI FITYATUL MUKARRAMAH (247006111020)
==============================================================
```

---

## 2. Tujuan & Ringkasan Deliverable

Membangun mesin pencari teks (hitung kemunculan beberapa keyword pada dataset besar) dengan **3 pendekatan** yang dibandingkan:

1. **Sequential** (baseline)
2. **Multithread** (`threading` / `ThreadPoolExecutor`)
3. **Multiprocessing** (`multiprocessing` / `ProcessPoolExecutor`)

Deliverable akhir (mengacu pada soal UTS):

| # | Deliverable | Bobot |
|---|---|---|
| A | Konsep & desain solusi (judul, deskripsi, solusi, arsitektur) | 20% |
| B | Implementasi kode: **versi ber-bug** + **versi final** | 40% |
| C | Hasil percobaan (min. 3 konfigurasi, tabel + 3 grafik) | 25% |
| D | Analisis & kesimpulan | 15% |
| — | Laporan PDF: `UTS_247006111020_Shafa_Rabbani_Fityatul_Mukarramah.pdf` | — |
| — | Seluruh file kode | — |
| — | Dokumentasi lengkap kode: `DOKUMENTASI.md` (Fase 11) | tambahan |

---

## 3. Aturan Kerja untuk AI Agent (WAJIB)

1. **Jangan memalsukan data.** Semua angka di tabel, grafik, dan analisis harus berasal dari hasil eksekusi nyata `benchmark`. Dilarang mengarang angka atau "memperkirakan".
2. **Bahasa:** komentar, docstring, pesan output CLI, laporan, dan dokumentasi ditulis dalam **Bahasa Indonesia**. Nama variabel/fungsi dalam bahasa Inggris.
3. **Python 3.10+**. Dependensi inti hanya **standard library**. Dependensi tambahan yang diizinkan: `matplotlib` (grafik), `pytest` (test), `psutil` (opsional, info hardware/memori). Catat semuanya di `requirements.txt`.
4. **Lintas platform (Windows/Linux/macOS).** Semua entry point multiprocessing wajib memakai `if __name__ == "__main__":` karena Windows memakai *spawn*. Fungsi worker harus *top-level* (bisa di-pickle).
5. **Kualitas kode:** type hints, docstring tiap fungsi/kelas publik, PEP 8, tanpa variabel global yang bisa diubah (kecuali di `buggy_search.py` secara sengaja).
6. **Jangan memuat seluruh dataset ke memory.** Baca per baris/per chunk secara streaming.
7. **Tiap fase diakhiri dengan menjalankan test yang relevan.** Perbaiki dulu sebelum lanjut.
8. Jika ada keputusan desain yang ambigu, pilih opsi paling sederhana yang memenuhi soal, lalu **catat alasannya** di `DOKUMENTASI.md`.
9. Bug sengaja di `buggy_search.py` **tidak boleh bocor** ke versi final.

---

## 4. Struktur Direktori Target

```
uts-parallel-text-search/
├── TASK.md                      # (file ini)
├── README.md                    # cara cepat install & jalankan
├── DOKUMENTASI.md               # dokumentasi lengkap (dibuat di Fase 11)
├── LAPORAN_UTS.md               # sumber laporan A–D (dikonversi ke PDF)
├── requirements.txt
├── src/
│   └── textsearch/
│       ├── __init__.py
│       ├── identity.py          # konstanta NAMA, NPM, banner
│       ├── params.py            # parameter unik hasil turunan NPM
│       ├── dataset_gen.py       # generator dataset (streaming) + CLI
│       ├── matcher.py           # logika pencocokan keyword (dipakai semua mode)
│       ├── chunking.py          # pembagian file ke byte-range chunk
│       ├── sequential.py        # pendekatan 1
│       ├── threaded.py          # pendekatan 2
│       ├── multiproc.py         # pendekatan 3
│       ├── buggy_search.py      # VERSI BER-BUG (sengaja) + demo
│       ├── metrics.py           # speedup, efisiensi, throughput
│       ├── cli.py               # entry point: python -m textsearch.cli
│       ├── benchmark.py         # menjalankan semua konfigurasi → CSV
│       └── plots.py             # membuat grafik dari CSV
├── tests/
│   ├── conftest.py
│   ├── test_params.py
│   ├── test_dataset_gen.py
│   ├── test_matcher.py
│   ├── test_chunking.py
│   ├── test_search_equivalence.py
│   ├── test_buggy_vs_final.py
│   ├── test_metrics.py
│   └── test_cli.py
├── data/                        # dataset hasil generate (di-.gitignore)
├── results/                     # CSV hasil benchmark + system_info.json
├── figures/                     # grafik PNG
└── report/                      # PDF akhir
```

Tambahkan `.gitignore` untuk `data/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.

---

## 5. Fase 0 — Setup Proyek

- Buat struktur direktori pada bagian 4 beserta `__init__.py`.
- `requirements.txt`: `matplotlib`, `pytest`, `psutil` (opsional).
- Tambahkan `pyproject.toml` minimal atau `conftest.py` yang menambahkan `src/` ke `sys.path` agar `pytest` dan `python -m textsearch.cli` bisa jalan dari root.
- `identity.py` berisi:
  ```python
  NAMA = "SHAFA RABBANI FITYATUL MUKARRAMAH"
  NPM = "247006111020"
  JUDUL = "PARALLEL TEXT SEARCH ENGINE"
  def banner() -> str: ...   # mengembalikan banner 3 baris sesuai bagian 1
  ```

---

## 6. Fase 1 — Parameter Unik dari NPM (`params.py`)

Soal mensyaratkan "parameter ditentukan dari NIM". Implementasikan **deterministik**:

```python
@dataclass(frozen=True)
class ProjectParams:
    npm: str
    seed: int                 # int(npm)
    keywords: tuple[str, ...] # 5 keyword dipilih dari KEYWORD_POOL
```

- `KEYWORD_POOL`: minimal 12 kata (contoh: `error`, `warning`, `timeout`, `server`, `network`, `thread`, `process`, `cache`, `latency`, `database`, `kernel`, `request`).
- `derive_params(npm: str) -> ProjectParams`: `rng = random.Random(int(npm))`, `keywords = tuple(rng.sample(KEYWORD_POOL, 5))`.
- Hasil **harus identik** setiap dipanggil dengan NPM yang sama (diuji di `test_params.py`).
- Seed ini dipakai sebagai seed default generator dataset sehingga dataset proyek ini unik untuk NPM ini.

---

## 7. Fase 2 — Helper Generator Dataset (`dataset_gen.py`)

### 7.1 Kebutuhan

Sediakan helper yang **membuat dataset teks otomatis berdasarkan jumlah baris** yang dimasukkan pengguna, termasuk dataset besar (**1.000.000 baris atau lebih**).

Persyaratan wajib:

1. **Streaming ke file.** Dataset ditulis langsung ke disk per *batch* (default 50.000 baris). Dilarang menyimpan seluruh baris dalam list/string besar. Memory harus tetap kecil dan relatif konstan walau 1.000.000+ baris.
2. **Variasi keyword.** Keyword tidak muncul seragam. Gunakan tiga tingkat frekuensi:
   - *common* (≈ 5–10% baris),
   - *medium* (≈ 0,5–1% baris),
   - *rare* (≈ 0,01–0,05% baris).

   Distribusi tingkat frekuensi dialokasikan ke keyword hasil `derive_params` (dan keyword tambahan dari kolom pool jika perlu). Satu baris boleh berisi 0, 1, atau beberapa keyword, dan satu keyword boleh muncul **lebih dari sekali** dalam satu baris.
3. **Variasi teks.** Panjang baris acak (mis. 8–25 kata), kosakata filler minimal ±200 kata, dan sebagian baris berformat mirip log (mis. awalan `2026-10-02 13:45:10 [INFO]`, `[WARN]`, `[ERROR]`) agar dataset realistis. Sertakan sebagian kecil karakter non-ASCII (mis. `café`, `naïve`) untuk menguji decoding UTF-8.
4. **Decoy (pengecoh) untuk uji word-boundary.** Sertakan kata mirip keyword yang **tidak boleh** cocok, mis. `errors`, `terror`, `serverless` untuk keyword `error`/`server`. Filler dan decoy **tidak boleh** memuat keyword utuh sebagai kata terpisah. Validasi ini dengan `assert` saat modul di-import atau lewat fungsi `validate_vocabulary()`.
5. **Deterministik.** Seed yang sama + parameter sama ⇒ file identik byte-per-byte. Gunakan `random.Random(seed)` lokal (bukan global).
6. **Ground truth (manifest).** Saat menulis, hitung jumlah **baris yang cocok** dan **total kemunculan** tiap keyword **tanpa membaca ulang file**, lalu simpan ke `<output>.meta.json`:
   ```json
   {
     "lines": 1000000, "seed": 247006111020, "generated_at": "...",
     "keywords": ["..."],
     "ground_truth": {"error": {"lines": 0, "occurrences": 0}, "...": {}},
     "size_bytes": 0
   }
   ```
   Manifest ini dipakai test untuk memverifikasi kebenaran mesin pencari.
7. **Mode multi-file.** Opsi `--files N` membagi total baris ke N file (`part_0001.txt`, ...) di satu direktori, jumlah total baris tepat sama dengan `--lines`. Dipakai untuk percobaan variasi "jumlah file".
8. **Input angka fleksibel:** `--lines 1000000`, `--lines 1_000_000`, `--lines 1M`, `--lines 500K` semuanya valid. Input tidak valid (≤ 0, format salah) ⇒ error yang jelas.
9. **Progress** di stderr tiap N batch (mis. `[GEN] 250,000 / 1,000,000 baris`). Dapat dimatikan dengan `--quiet`.

### 7.2 API & CLI

```python
def generate_dataset(lines: int, output: str | Path, *, seed: int | None = None,
                     keywords: Sequence[str] | None = None, files: int = 1,
                     batch_size: int = 50_000, quiet: bool = True) -> DatasetInfo: ...

def parse_line_count(text: str) -> int: ...      # "1M" -> 1_000_000
def iter_batches(...) -> Iterator[str]: ...      # generator, bukan list
```

```bash
python -m textsearch.dataset_gen --lines 1M --out data/corpus_1M.txt
python -m textsearch.dataset_gen --lines 500K --files 10 --out data/multi_500K/
python -m textsearch.dataset_gen --lines 10000 --out data/small.txt --seed 42
```

Default `seed` = `derive_params(NPM).seed`, default `keywords` = `derive_params(NPM).keywords`.

CLI juga menampilkan banner (nama + NPM), jumlah baris, ukuran file, waktu generate, dan ringkasan ground truth.

### 7.3 Verifikasi manual setelah dibuat
- Generate 1.000.000 baris, catat ukuran file dan waktu.
- Ukur memory puncak (mis. `psutil` / `tracemalloc`) dan catat bahwa tetap rendah. Cantumkan di dokumentasi.

---

## 8. Fase 3 — Inti Pencarian

### 8.1 Semantik pencarian (HARUS sama untuk ketiga pendekatan)

- **Case-insensitive.**
- **Whole word** (batas kata): `error` cocok pada `Error:` dan `ERROR`, **tidak** pada `errors`/`terror`. Gunakan regex `\b(?:kw1|kw2|...)\b` dengan `re.IGNORECASE` yang dikompilasi **sekali** per worker; keyword di-`re.escape`.
- Hasil per keyword: `lines` (jumlah baris yang memuat keyword) dan `occurrences` (total kemunculan).
- Tambahan: `total_lines` dan `total_bytes` yang diproses.
- Simpan juga **maksimal K baris contoh** (default K=5, nomor baris + teks terpotong) per keyword untuk ditampilkan di output. Nomor baris global harus benar walau diproses paralel (gunakan hitungan baris per chunk lalu offset, atau cukup laporkan *byte offset*; pilih salah satu dan dokumentasikan).
- Dekode baris: `bytes.decode("utf-8", errors="replace")`.

### 8.2 `matcher.py`

- `compile_pattern(keywords) -> re.Pattern`
- `match_line(pattern, line) -> Counter` atau struktur setara
- `SearchResult` (dataclass) dengan metode `merge(other)` yang bersifat **asosiatif dan komutatif** sehingga hasil worker dapat digabung dengan urutan apa pun.

### 8.3 `chunking.py` — pembagian pekerjaan

Pekerjaan dibagi menjadi **task berupa byte-range** `(path, start, end)`, bukan dengan membaca semua baris:

```python
@dataclass(frozen=True)
class Chunk: path: str; start: int; end: int
def make_chunks(paths: Sequence[Path], n_chunks: int) -> list[Chunk]: ...
def process_chunk(chunk: Chunk, keywords: Sequence[str]) -> SearchResult: ...
```

**Aturan kepemilikan baris (kritis, jangan salah):**
- Sebuah baris dimiliki oleh chunk yang memuat **offset awal baris** tersebut.
- Pada `process_chunk`: buka file mode **biner**. Jika `start > 0`, `seek(start - 1)` lalu `readline()` satu kali dan buang (ini menyelesaikan baris yang dimulai di chunk sebelumnya; jika byte di `start-1` adalah `\n`, baris yang mulai tepat di `start` tetap diproses). Lalu loop: `pos` dilacak manual (`pos += len(line)`); berhenti ketika `pos >= end` atau EOF.
- Jangan ada baris yang hilang atau terhitung dua kali. Chunk tidak boleh overlap dan gabungannya harus menutup seluruh file.
- Kasus tepi yang wajib ditangani: file kosong, 1 baris, tanpa newline di akhir, jumlah worker > jumlah baris, beberapa file dengan ukuran sangat berbeda, `n_chunks` ≤ 0 ⇒ error.
- Untuk mode multi-file: chunk dibuat per file (dan file besar dipecah lagi) sehingga total chunk ≈ `n_chunks × faktor_granularitas`. Granularitas default: **4 chunk per worker** untuk mengurangi *load imbalance*. Faktor ini dapat dikonfigurasi dan jadi variabel eksperimen opsional.

### 8.4 Tiga pendekatan

| Modul | Fungsi utama | Catatan |
|---|---|---|
| `sequential.py` | `search_sequential(paths, keywords) -> RunReport` | 1 chunk penuh per file, tanpa pool |
| `threaded.py` | `search_threaded(paths, keywords, n_threads) -> RunReport` | `ThreadPoolExecutor`; tiap thread punya `SearchResult` lokal; hasil digabung di thread utama |
| `multiproc.py` | `search_multiprocess(paths, keywords, n_procs) -> RunReport` | `ProcessPoolExecutor` atau `multiprocessing.Pool`; kirim hanya `Chunk` + keyword (ringan), kembalikan `SearchResult` kecil |

`RunReport` berisi: `mode`, `workers`, `elapsed_sec` (pakai `time.perf_counter`), `result`, `chunks`, `per_worker_times` (opsional, untuk analisis load imbalance), `total_lines`, `total_bytes`.

Setiap worker mencetak log bergaya contoh soal, **thread-safe** (`print` dikunci atau gunakan `logging`):

```
Thread-1 mulai bekerja
[MULAI] chunk 3/16 (offset 0–5,242,880)
...
```
Log ini dapat dimatikan (`verbose=False`) saat benchmark agar tidak mengganggu pengukuran.

---

## 9. Fase 4 — Versi Ber-Bug (`buggy_search.py`)

Wajib ada **minimal satu** bug komputasi paralel yang **nyata dan dapat didemonstrasikan**. Implementasikan:

### Bug utama: Race Condition pada penghitung bersama (wajib)
- Beberapa thread menaikkan penghitung global/bersama (mis. `shared_counts[kw] += 1` atau `total_matches += 1`) **tanpa lock**.
- Agar bug muncul konsisten di CPython (karena GIL), buat operasi *read-modify-write* eksplisit dengan celah yang memungkinkan *context switch*, misalnya:
  ```python
  tmp = shared["error"]
  time.sleep(0)          # atau sys.setswitchinterval(1e-6) di demo
  shared["error"] = tmp + 1
  ```
  Jelaskan di komentar bahwa tanpa celah ini bug lebih jarang muncul, tetapi tetap *benar secara teori* ada.
- Demo: jalankan N kali (mis. 10) pada dataset kecil, tampilkan **nilai ground truth vs nilai hasil bug**, jumlah *lost update*, dan persentase run yang salah.

### Bug sekunder (opsional, sangat dianjurkan): Load Imbalance
- Versi ber-bug membagi pekerjaan **statis berdasarkan jumlah file** (atau chunk besar tunggal per worker) pada dataset multi-file dengan ukuran file tidak seragam, sehingga satu worker jauh lebih lama.
- Ukur dan tampilkan `per_worker_times` untuk memperlihatkan ketimpangan.

### Keluaran demo
`python -m textsearch.buggy_search --lines 200K --threads 8 --runs 10` menampilkan banner (nama + NPM), jumlah thread, hasil per run, serta ringkasan bukti bug. Simpan juga bukti ke `results/bug_evidence.csv` dan potongan outputnya akan dikutip di laporan (Bagian B — "Code with Bug").

> Keputusan: `buggy_search.py` **berdiri sendiri** dan tidak diimpor oleh modul final.

---

## 10. Fase 5 — Versi Final & Penyelesaian Bug

Di versi final (`threaded.py`, `multiproc.py`), selesaikan bug dengan pendekatan yang **dibandingkan**:

1. **Local accumulation + merge (reduce)** — tiap worker memakai penghitung lokal, digabung di akhir. *Ini default final* karena tanpa kontensi.
2. **`threading.Lock`** pada penghitung bersama — implementasikan sebagai varian pembanding (`--sync lock`) untuk mengukur **Synchronization Overhead**.

Perbaiki juga load imbalance dengan chunk lebih kecil dari jumlah worker (dynamic scheduling lewat antrean tugas pool).

Hasil final harus **identik** dengan baseline sequential dan dengan ground truth manifest, di semua konfigurasi.

---

## 11. Fase 6 — CLI Utama (`cli.py`)

```bash
python -m textsearch.cli --input data/corpus_1M.txt --mode sequential
python -m textsearch.cli --input data/corpus_1M.txt --mode thread --workers 8
python -m textsearch.cli --input data/multi_500K/ --mode process --workers 4
python -m textsearch.cli --input data/corpus_1M.txt --mode all --workers 4   # bandingkan ketiganya
```

Opsi: `--input` (file atau direktori), `--mode {sequential,thread,process,all}`, `--workers N`, `--keywords a,b,c` (default dari `derive_params`), `--sync {merge,lock}`, `--verbose/--quiet`, `--samples K`, `--json` (output mesin).

Output **wajib** memuat (sesuai soal):
- Banner **nama + NPM**
- **Jumlah thread/process** yang digunakan
- **Waktu total eksekusi**
- Throughput (baris/detik dan MB/detik); Speedup & Efisiensi bila `--mode all`

Contoh format akhir:

```
==============================================================
PARALLEL TEXT SEARCH ENGINE
By SHAFA RABBANI FITYATUL MUKARRAMAH (247006111020)
==============================================================
Dataset         : data/corpus_1M.txt (1,000,000 baris, 78.4 MB)
Keyword         : error, server, cache, kernel, timeout
Mode            : multiprocessing
Jumlah process  : 4
Process-1 mulai bekerja
...
SEMUA PENCARIAN SELESAI
Keyword   | Baris cocok | Total kemunculan
error     |      61,204 |           63,011
...
Waktu total     : 1.23 detik
Throughput      : 813,008 baris/detik
Speedup         : 3.41x   Efisiensi: 85.2%
==============================================================
```

`metrics.py`: `speedup(t_seq, t_par)`, `efficiency(speedup, workers)`, `throughput(lines, seconds)`. Tangani pembagian nol dan nilai tidak valid dengan error/nilai yang terdefinisi jelas.

---

## 12. Fase 7 — Benchmark (`benchmark.py`) & Fase 8 — Grafik (`plots.py`)

### 12.1 Desain percobaan (min. 3 konfigurasi per variasi, sesuai soal)

| Variasi | Nilai yang diuji (minimal) |
|---|---|
| Jumlah thread | 1, 2, 4, 8, 16 |
| Jumlah process | 1, 2, 4, 8 (sesuaikan dengan `os.cpu_count()`; tambahkan nilai = jumlah core) |
| Jumlah data | 100.000, 500.000, 1.000.000 baris |
| Jumlah file (opsional) | 1, 10, 50 file dengan total baris tetap |

Prosedur:
- Generate dataset sekali (seed tetap), dipakai ulang oleh semua percobaan.
- **Warm-up** 1 kali (tidak dicatat) untuk menstabilkan cache file OS.
- Ulangi **minimal 3 kali** tiap konfigurasi; catat `median` (utama), `min`, `mean`, `stdev`.
- Verifikasi hasil tiap run == ground truth; jika berbeda, tandai `correct=False` di CSV dan hentikan dengan peringatan.
- Simpan `results/benchmark.csv` (kolom: `mode, workers, lines, files, run, elapsed_sec, correct`) dan `results/summary.csv` (agregat + speedup + efisiensi).
- Simpan `results/system_info.json`: OS, versi Python, CPU model, jumlah core fisik/logis, RAM, tipe penyimpanan bila diketahui.
- Banner nama + NPM tampil di awal benchmark. Tambahkan opsi `--quick` (data kecil) untuk uji cepat.

### 12.2 Grafik (matplotlib, backend `Agg`, simpan PNG di `figures/`)

Wajib 3 grafik sesuai soal:
1. **Waktu vs Jumlah Thread** (`time_vs_threads.png`) — bandingkan juga garis baseline sequential.
2. **Waktu vs Jumlah Process** (`time_vs_processes.png`)
3. **Speedup vs Konfigurasi** (`speedup_vs_config.png`) — thread dan process dalam satu grafik, sertakan garis speedup ideal.

Tambahan yang dianjurkan: waktu vs jumlah data; bar chart bug vs final (Lock vs merge).
Setiap grafik wajib: judul, label sumbu + satuan, legenda, dan keterbacaan baik (ukuran ≥ 8×5 inci, dpi ≥ 150).

---

## 13. Unit Testing (pytest) — dikerjakan sejak Fase 1, bukan di akhir

Jalankan: `pytest -v`. Semua test harus **cepat** (dataset kecil via `tmp_path`, total suite idealnya < 60 detik) dan **tidak flaky**. Test yang wajib ada:

**`test_params.py`**
- `derive_params` deterministik; 5 keyword unik dari pool; NPM berbeda ⇒ (hampir pasti) hasil berbeda; NPM non-numerik ⇒ error jelas.

**`test_dataset_gen.py`**
- Jumlah baris file **tepat** = `--lines` (uji 1, 10, 1.000, 10.000).
- Seed sama ⇒ file identik (bandingkan hash); seed beda ⇒ file berbeda.
- Variasi keyword: tiap keyword muncul ≥ 1 kali pada dataset cukup besar, dan frekuensi tidak seragam (common > medium > rare).
- Manifest `.meta.json` ada dan **ground truth sama** dengan hitung naif independen (regex sederhana pada dataset kecil).
- Tidak ada keyword utuh pada filler/decoy (`validate_vocabulary`).
- `parse_line_count`: `"1M"`, `"500K"`, `"1_000_000"`, `"1000"` valid; `"abc"`, `"0"`, `"-5"` ⇒ `ValueError`.
- Mode `--files N`: jumlah file benar, total baris tepat, tidak ada file kosong tak terduga.
- Streaming: `iter_batches` adalah generator (`inspect.isgenerator`), ukuran batch dihormati, dan `batch_size` kecil menghasilkan file yang sama dengan `batch_size` besar.
- File berhasil dibaca sebagai UTF-8.

**`test_matcher.py`**
- Case-insensitive; **word-boundary** (`errors`, `terror` tidak cocok); beberapa kemunculan dalam satu baris menambah `occurrences` tetapi hanya +1 `lines`; keyword mengandung karakter regex spesial aman (`re.escape`); baris kosong; Unicode; `merge` bersifat komutatif & asosiatif.

**`test_chunking.py`** (parametrize `n_chunks` ∈ {1, 2, 3, 7, 64, > jumlah baris})
- Chunk tidak overlap dan menutup seluruh ukuran file.
- Gabungan baris yang diproses semua chunk == seluruh baris file (tidak hilang, tidak dobel).
- Kasus: file kosong, 1 baris, tanpa newline akhir, baris sangat panjang yang melintasi banyak batas chunk, batas chunk tepat di `\n`, beberapa file.
- `n_chunks <= 0` ⇒ `ValueError`.

**`test_search_equivalence.py`**
- `sequential == threaded == multiprocess` (dan `lock` == `merge`) pada beberapa dataset dan jumlah worker (1, 2, 4, 8).
- Hasil sama dengan ground truth manifest.
- Jalankan versi final berulang (mis. 20×) ⇒ hasil selalu sama (bukti bug hilang).
- Worker > jumlah baris tidak crash.

**`test_buggy_vs_final.py`**
- Versi final selalu benar. Untuk versi ber-bug: tes yang mengonfirmasi **mekanisme bug ada** secara andal, misalnya menjalankan banyak ulangan dengan celah *context switch* dan menegaskan hasil ≤ ground truth (tidak pernah lebih) serta *marker* `xfail(strict=False)`/`skipif` bila pada mesin tertentu tidak muncul. **Jangan membuat test yang sesekali gagal acak.**
- Tes bahwa `buggy_search` tidak diimpor oleh modul final.

**`test_metrics.py`**
- Rumus speedup/efisiensi/throughput benar; pembagian nol & nilai negatif ditangani.

**`test_cli.py`** (via `subprocess` atau `main(argv)`)
- Output memuat **"SHAFA RABBANI FITYATUL MUKARRAMAH"** dan **"247006111020"**, jumlah thread/process, dan "Waktu total".
- Argumen salah (mode tak dikenal, input tidak ada, workers ≤ 0) ⇒ exit code ≠ 0 dengan pesan jelas.
- `--json` menghasilkan JSON valid.

Target cakupan: ≥ 85% pada modul inti (`matcher`, `chunking`, `dataset_gen`, `metrics`) — ukur dengan `pytest --cov` bila `pytest-cov` tersedia.

---

## 14. Fase 9 — Laporan UTS (`LAPORAN_UTS.md` → PDF)

Susun sesuai template soal. Isi hanya dengan data nyata dari percobaan.

- **Sampul:** Nama, NPM, mata kuliah, dosen, tanggal.
- **A. Konsep dan Desain Solusi (20%)**
  - Judul & deskripsi singkat Parallel Text Search Engine.
  - Deskripsi solusi (bandingkan Sequential, Multithread, Multiprocessing; jelaskan chunking by byte-range, aturan kepemilikan baris, merge hasil).
  - Arsitektur sistem: diagram alir (Mermaid atau gambar matplotlib → PNG) dengan tahap: *Dataset/Input → Chunking & Task Split → Worker Pool (Thread/Process 1..N: baca chunk, match regex, hitung lokal) → Merge/Reduce → Metrics & Report*.
- **B. Implementasi Kode (40%)**
  - *Code with Bug:* potongan kode bug + penjelasan jenis bug + bukti output (ground truth vs hasil salah).
  - *Final Code:* potongan kode final + penjelasan perbaikan + output yang menampilkan **NPM & Nama, jumlah thread/process, waktu total, throughput/speedup/efisiensi**.
- **C. Hasil Percobaan (25%)**: tabel tiap variasi (thread, process, jumlah data/file), 3 grafik wajib, info spesifikasi mesin.
- **D. Analisis & Kesimpulan (15%)**:
  - Perbedaan performa antar konfigurasi.
  - Faktor paling berpengaruh (I/O vs CPU vs komunikasi/serialisasi antar proses) — **dukung dengan data**, termasuk dampak **GIL** pada multithread CPU-bound, overhead *spawn*/pickling pada multiprocessing, dan pengaruh page cache.
  - Kesimpulan umum + keterbatasan percobaan.
- **Konversi PDF** ke `report/UTS_247006111020_Shafa_Rabbani_Fityatul_Mukarramah.pdf` memakai alat yang tersedia (mis. `pandoc`, atau skrip `reportlab`/`weasyprint`). Bila tidak ada alat konversi di lingkungan, hasilkan `LAPORAN_UTS.md` yang rapi lalu beri tahu pengguna cara mengekspor ke PDF.

---

## 15. Fase 10 — Verifikasi Akhir

Jalankan dan pastikan lolos:
1. `pytest -v` (semua hijau).
2. Generate dataset 1.000.000 baris → berhasil, memory rendah, ground truth tertulis.
3. CLI untuk ketiga mode pada dataset 1M → hasil identik dengan ground truth.
4. Demo bug menunjukkan hasil salah; versi final benar.
5. Benchmark penuh selesai, CSV + 3 grafik tersedia.
6. Semua output program menampilkan **nama + NPM**.
7. Tidak ada angka di laporan yang tidak bersumber dari `results/`.

---

## 16. Fase 11 — DOKUMENTASI LENGKAP (WAJIB, SETELAH SEMUA SELESAI)

Setelah **seluruh pekerjaan di atas selesai dan terverifikasi**, buat **file markdown baru bernama `DOKUMENTASI.md`** di root proyek. Dokumentasi ini harus **lengkap** dan bisa dipahami oleh orang yang belum pernah melihat kode. Wajib memuat:

1. **Ringkasan proyek** — tujuan, identitas (nama, NPM), tema, ringkasan hasil utama.
2. **Struktur direktori lengkap** — tree seluruh file dan folder (kecuali `data/` berukuran besar), dengan **satu baris deskripsi untuk setiap file**.
3. **Penjelasan setiap file kode** secara berurutan. Untuk **setiap modul**:
   - tujuan modul dan hubungannya dengan modul lain,
   - **setiap kelas dan fungsi**: tanda tangan (parameter + tipe), return, tujuan, cara kerja langkah demi langkah, kasus tepi yang ditangani, kompleksitas bila relevan,
   - **potongan kode penting yang dikutip lalu dijelaskan baris demi baris** (terutama: `process_chunk` dan aturan kepemilikan baris, `generate_dataset` dan streaming per batch, race condition di `buggy_search`, mekanisme merge/lock),
   - alasan keputusan desain (mengapa regex word-boundary, mengapa byte-range chunk, mengapa 4 chunk/worker, mengapa merge vs lock).
4. **Diagram alur/arsitektur** (Mermaid) beserta penjelasan alur data dari input sampai laporan.
5. **Penjelasan bug** — jenis bug, di mana letaknya, mengapa terjadi (termasuk peran GIL), bukti, dan bagaimana tiap solusi memperbaikinya.
6. **Penjelasan generator dataset** — format baris, tingkat frekuensi keyword, decoy, manifest ground truth, cara memastikan memory efisien (sertakan hasil ukuran memori nyata).
7. **Penjelasan unit test** — tiap file test, apa yang diuji, dan mengapa; cara menjalankan; hasil `pytest` terakhir (ringkasan pass/fail dan cakupan).
8. **Panduan penggunaan** — instalasi, contoh perintah untuk generator, CLI (tiap mode), benchmark, plot, demo bug, dan test. Sertakan contoh output nyata.
9. **Hasil benchmark ringkas** — tabel utama dan rujukan ke grafik (`figures/…`), spesifikasi mesin.
10. **Keterbatasan & pekerjaan lanjutan** — hal yang belum dicakup dan ide pengembangan.
11. **Pemetaan ke soal UTS** — tabel yang memetakan setiap butir soal (A, B, C, D, output wajib, file yang dikumpulkan) ke file/bagian yang memenuhinya.
12. **Glosarium** singkat (race condition, GIL, speedup, efisiensi, throughput, load imbalance, chunk, dll.).

Dokumentasi tidak boleh berupa daftar nama file saja; tiap kode harus **dijelaskan fungsinya dan cara kerjanya**. Setelah selesai, laporkan ke pengguna ringkasan: apa yang dibuat, hasil test, hasil benchmark utama, dan hal yang perlu ditinjau manual (mis. konversi PDF bila tidak otomatis).

---

## 17. Definition of Done (Checklist)

- [ ] Struktur proyek sesuai bagian 4; `requirements.txt` dan `README.md` ada
- [ ] `params.py` menurunkan parameter dari NPM 247006111020 secara deterministik
- [ ] Generator dataset: streaming ke file, variasi keyword, decoy, deterministik, manifest ground truth, `--files`, sukses untuk 1.000.000 baris
- [ ] Tiga pendekatan: sequential, multithread, multiprocessing — hasil identik dengan ground truth
- [ ] `buggy_search.py` memuat minimal 1 bug paralel yang terbukti lewat demo
- [ ] Versi final menyelesaikan bug (merge default + varian Lock untuk perbandingan)
- [ ] Semua output menampilkan **nama + NPM**, jumlah thread/process, waktu total, throughput/speedup/efisiensi
- [ ] Benchmark ≥ 3 konfigurasi per variasi (thread, process, jumlah data), ≥ 3 pengulangan, CSV tersimpan
- [ ] 3 grafik wajib tersedia (waktu vs thread, waktu vs process, speedup vs konfigurasi)
- [ ] Unit test lengkap (bagian 13), seluruhnya lulus, tidak flaky
- [ ] `LAPORAN_UTS.md` (A–D) selesai; PDF `UTS_247006111020_Shafa_Rabbani_Fityatul_Mukarramah.pdf` dibuat atau instruksi ekspor diberikan
- [ ] **`DOKUMENTASI.md` dibuat dengan lengkap sesuai Fase 11**
- [ ] Tidak ada data hasil yang dipalsukan
