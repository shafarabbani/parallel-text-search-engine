"""Generator dataset teks (streaming) + CLI ``python -m textsearch.dataset_gen``.

Karakteristik penting (lihat TASK.md bagian 7):
    1. **Streaming ke disk per batch** — tidak ada list berisi seluruh baris;
       memory relatif konstan walau 1.000.000+ baris.
    2. **Variasi frekuensi keyword** tiga tingkat: *common* (~5-10% baris),
       *medium* (~0,5-1% baris), *rare* (~0,01-0,05% baris).
    3. **Variasi teks**: panjang baris acak 8-25 kata, kosakata filler
       >200 kata, sebagian baris berformat log ``2026-10-02 13:45:10 [INFO]``,
       dan sebagian kecil kata non-ASCII (``café``, ``naïve``) untuk menguji
       decoding UTF-8.
    4. **Decoy**: kata mirip keyword (``errors``, ``terror``, ``serverless``)
       yang TIDAK boleh cocok — melatih word-boundary. Filler/decoy divalidasi
       tidak memuat keyword utuh (``validate_vocabulary``).
    5. **Deterministik**: ``random.Random(seed)`` lokal; seed + parameter sama
       ⇒ file identik byte-per-byte.
    6. **Manifest ground truth** ditulis ke ``<output>.meta.json`` tanpa
       membaca ulang file (dihitung saat menulis).
    7. **Mode multi-file** ``--files N`` membagi total baris ke N file
       ``part_XXXX.txt`` dengan total baris tepat sama.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Iterator, Sequence

from textsearch.identity import NPM, banner
from textsearch.matcher import compile_pattern, match_line
from textsearch.params import KEYWORD_POOL, ProjectParams, derive_params

# ---------------------------------------------------------------------------
# Kosakata filler (>= 200 kata). TIDAK ADA satu pun kata pool keyword
# (error, warning, timeout, ...) di sini — divalidasi validate_vocabulary().
# ---------------------------------------------------------------------------
FILLER_WORDS: tuple[str, ...] = (
    "alpha", "beta", "gamma", "delta", "gateway", "node", "cluster", "packet",
    "payload", "header", "footer", "module", "package", "library", "service",
    "container", "image", "volume", "disk", "partition", "sector", "block",
    "byte", "bit", "stream", "buffer", "queue", "stack", "heap", "array",
    "list", "tree", "graph", "hash", "index", "table", "row", "column",
    "field", "record", "entry", "value", "token", "session", "account",
    "admin", "role", "group", "policy", "rule", "filter", "query", "command",
    "script", "binary", "runtime", "compiler", "linker", "loader", "driver",
    "device", "port", "cable", "switch", "router", "bridge", "tunnel",
    "channel", "signal", "noise", "ratio", "scale", "metric", "gauge",
    "sensor", "reading", "sample", "corpus", "archive", "backup", "snapshot",
    "restore", "journal", "ledger", "invoice", "receipt", "order", "shipment",
    "warehouse", "depot", "station", "terminal", "console", "display",
    "screen", "monitor", "keyboard", "printer", "scanner", "camera",
    "speaker", "battery", "charger", "adapter", "plug", "outlet", "uptime",
    "downtime", "window", "panel", "dialog", "button", "label", "menu",
    "toolbar", "sidebar", "layout", "margin", "canvas", "sprite", "shader",
    "vertex", "pixel", "vector", "matrix", "tensor", "scalar", "integer",
    "float", "double", "string", "char", "struct", "enum", "trait", "object",
    "class", "method", "function", "closure", "lambda", "callback", "promise",
    "event", "listener", "handler", "dispatcher", "scheduler", "worker",
    "job", "task", "pipeline", "stage", "phase", "cycle", "tick", "clock",
    "timer", "alarm", "pulse", "beacon", "anchor", "bridge", "harbor",
    "meadow", "forest", "valley", "canyon", "ridge", "summit", "glacier",
    "prairie", "lagoon", "harvest", "orchard", "pasture", "copper", "silver",
    "golden", "bronze", "marble", "granite", "quartz", "amber", "ivory",
    "ebony", "crimson", "scarlet", "indigo", "violet", "emerald", "sapphire",
    "opalescent", "turquoise", "magenta", "cerulean", "vermilion", "azure",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december", "morning",
    "afternoon", "evening", "night", "midnight", "dawn", "dusk", "twilight",
    "autumn", "winter", "springtime", "breeze", "thunder", "rainfall",
    "snowfall", "sunshine", "cloud", "storm", "mist", "frost", "ember",
    "lantern", "candle", "beacon", "compass", "map", "atlas", "atlas",
    "globe", "orbit", "comet", "meteor", "nebula", "quasar", "pulsar",
    "galaxy", "cosmos", "eclipse", "horizon", "meridian", "equator",
    "polar", "tropic", "latitude", "longitude", "altitude", "depth",
    "breadth", "width", "height", "length", "mass", "weight", "density",
    "gravity", "magnet", "charge", "current", "voltage", "circuit",
    "resistor", "capacitor", "diode", "transistor", "chipset", "motherboard",
    "bandwidth", "throughput", "band", "station", "studio", "theatre",
    "concert", "orchestra", "melody", "rhythm", "tempo", "chorus", "verse",
    "bridge", "lyrics", "album", "single", "track", "record", "cassette",
    "vinyl", "digital", "analog", "signal", "modem", "antenna", "frequency",
    "amplitude", "wavelength", "spectrum", "bandwidth", "channel",
)

# Kata non-ASCII untuk menguji decoding UTF-8.
ACCENT_WORDS: tuple[str, ...] = ("café", "naïve", "résumé", "façade", "jalapeño")

# Tingkat frekuensi target per posisi keyword (lihat docstring modul).
# Index 0-1 => common, 2-3 => medium, 4 => rare.
FREQUENCY_RATES: tuple[float, ...] = (0.075, 0.055, 0.009, 0.006, 0.00035)
FREQUENCY_TIERS: tuple[str, ...] = ("common", "common", "medium", "medium", "rare")

# Level log yang dipakai pada prefix bergaya log — sengaja TIDAK memakai
# "[ERROR]" agar tidak memalsukan pencocokan keyword (word-boundary).
LOG_LEVELS: tuple[str, ...] = ("INFO", "WARN", "DEBUG", "TRACE", "CRIT", "FATAL")

_SUFFIX_DECOY = ("s", "ed", "ing", "less", "ful", "ish", "y", "es")
_PREFIX_DECOY = ("re", "un", "pre", "non", "anti", "over")


def build_decoys(keywords: Sequence[str]) -> dict[str, list[str]]:
    """Bangkitkan kata pengecoh (decoy) per keyword yang tidak boleh cocok.

    Contoh: ``error`` -> ``errors``, ``reerror``, ``errorless``; keyword
    mana pun + sufiks/prefiks. Bentuk gabungan tetap satu kata sehingga
    regex ``\\bkeyword\\b`` tidak cocok — inilah gunanya decoy.
    """
    decoy: dict[str, list[str]] = {}
    for kw in keywords:
        k = kw.lower()
        daftar = [k + s for s in _SUFFIX_DECOY] + [p + k for p in _PREFIX_DECOY]
        # decoy khusus bergaya contoh soal (terror, serverless sudah tercakup
        # pola prefiks/sufiks secara generik)
        decoy[k] = daftar
    return decoy


DECOY_POOL: dict[str, list[str]] = build_decoys(KEYWORD_POOL)


def validate_vocabulary(keywords: Sequence[str] | None = None) -> None:
    """Validasi: filler & decoy tidak memuat keyword utuh sebagai kata.

    Args:
        keywords: Keyword yang diperiksa; default seluruh ``KEYWORD_POOL``.

    Raises:
        AssertionError: bila ada filler/decoy yang memuat keyword utuh.
    """
    periksa = tuple(k.lower() for k in (keywords or KEYWORD_POOL))
    pola = compile_pattern(periksa)
    for w in set(FILLER_WORDS):
        assert not pola.search(w), f"filler '{w}' memuat keyword utuh"
    for kw, daftar in DECOY_POOL.items():
        for d in daftar:
            assert not pola.search(d), f"decoy '{d}' memuat keyword utuh"


# Dijalankan saat import sesuai syarat TASK.md bagian 7.4.
validate_vocabulary()


def parse_line_count(text: str) -> int:
    """Ubah input jumlah baris fleksibel menjadi integer.

    Format valid: ``"1000"``, ``"1_000_000"``, ``"1M"``, ``"500K"`` (K=10^3,
    M=10^6, kasus huruf bebas).

    Args:
        text: string input dari CLI.

    Returns:
        int: jumlah baris (> 0).

    Raises:
        ValueError: format salah, bukan bilangan, atau hasilnya <= 0.
    """
    if not isinstance(text, str):
        raise ValueError(f"Input harus string, diterima {type(text)}")
    bersih = text.strip().replace("_", "")
    if not bersih:
        raise ValueError("Input jumlah baris kosong")
    pengali = 1
    akhiran = bersih[-1].upper()
    if akhiran == "K":
        pengali, bersih = 1_000, bersih[:-1]
    elif akhiran == "M":
        pengali, bersih = 1_000_000, bersih[:-1]
    if not bersih.isdigit():
        raise ValueError(f"Format jumlah baris tidak valid: {text!r}")
    nilai = int(bersih) * pengali
    if nilai <= 0:
        raise ValueError(f"Jumlah baris harus > 0, diterima: {text!r}")
    return nilai


@dataclass
class DatasetInfo:
    """Ringkasan hasil pembuatan dataset (dikembalikan generate_dataset)."""

    lines: int
    paths: list[Path]
    size_bytes: int
    seed: int
    keywords: tuple[str, ...]
    ground_truth: dict[str, dict[str, int]]
    meta_path: Path
    elapsed_sec: float
    tiers: dict[str, str] = field(default_factory=dict)


def meta_path_for(output: str | Path) -> Path:
    """Tentukan lokasi manifest ground truth untuk sebuah output."""
    p = Path(output)
    if str(output).endswith(("/", "\\")) or p.is_dir():
        return p / "dataset.meta.json"
    return Path(str(p) + ".meta.json")


def find_meta(input_path: str | Path) -> Path:
    """Cari manifest untuk dataset yang sudah ada (file atau direktori).

    Raises:
        FileNotFoundError: manifest tidak ditemukan di lokasi wajar.
    """
    p = Path(input_path)
    if p.is_dir():
        kandidat = [p / "dataset.meta.json", *sorted(p.glob("*.meta.json"))]
        for k in kandidat:
            if k.is_file():
                return k
        raise FileNotFoundError(f"Manifest (.meta.json) tidak ada di {p}")
    sidecar = Path(str(p) + ".meta.json")
    if sidecar.is_file():
        return sidecar
    raise FileNotFoundError(f"Manifest tidak ditemukan: {sidecar}")


def _bagi_rata(total: int, n: int) -> list[int]:
    """Pecah ``total`` menjadi ``n`` bagian integer yang selisih maksimal 1."""
    dasar, sisa = divmod(total, n)
    return [dasar + (1 if i < sisa else 0) for i in range(n)]


class _PembuatBaris:
    """Mesin pembangkit satu baris dataset (stateless terhadap file).

    Memakai satu :class:`random.Random` lokal agar deterministik.
    """

    def __init__(self, seed: int, keywords: Sequence[str]) -> None:
        self.rng = Random(seed)
        self.keywords = [k.lower() for k in keywords]
        n = len(self.keywords)
        self.rates = list(FREQUENCY_RATES[:n]) if n <= 5 else list(FREQUENCY_RATES)
        # bila keyword > 5, pola tiga tingkat diulang proporsional
        while len(self.rates) < n:
            self.rates.append(FREQUENCY_RATES[len(self.rates) % len(FREQUENCY_RATES)])
        self.decoys = build_decoys(self.keywords)

    def _waktu_log(self) -> str:
        rng = self.rng
        return (
            f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d} "
            f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:"
            f"{rng.randint(0, 59):02d} [{rng.choice(LOG_LEVELS)}]"
        )

    def one_line(self) -> str:
        """Hasilkan SATU baris teks dataset (tanpa newline)."""
        rng = self.rng
        jumlah_kata = rng.randint(8, 25)
        kata = [rng.choice(FILLER_WORDS) for _ in range(jumlah_kata)]

        # 1) injeksi keyword sesuai tingkat frekuensinya (boleh >1 kemunculan)
        for kw, p in zip(self.keywords, self.rates):
            while rng.random() < p:
                posisi = rng.randint(0, len(kata))
                kata.insert(posisi, kw)
                p = p * 0.25          # peluang kemunculan kedua/berikutnya
            # kadang keyword ditulis dengan gaya log "Error:" / "ERROR"
        # 2) sisipkan decoy (~2% baris) untuk melatih word-boundary
        if rng.random() < 0.02 and self.decoys:
            kw = rng.choice(self.keywords)
            posisi = rng.randint(0, len(kata))
            kata.insert(posisi, rng.choice(self.decoys[kw]))
        # 3) kata non-ASCII (~1% baris)
        if rng.random() < 0.01:
            posisi = rng.randint(0, len(kata) - 1)
            kata[posisi] = rng.choice(ACCENT_WORDS)

        teks = " ".join(kata)
        # 4) ~30% baris diberi prefix bergaya log
        if rng.random() < 0.30:
            teks = f"{self._waktu_log()} {teks}"
        return teks


def iter_batches(sumber: Iterator[str], batch_size: int) -> Iterator[str]:
    """Generator yang mengelompokkan baris menjadi batch berupa satu string.

    Bukan list — pemanggil tetap streaming. ``batch_size`` hanya mengatur
    FREKUENSI tulis, tidak mengubah isi byte file.
    """
    if batch_size <= 0:
        raise ValueError("batch_size harus > 0")
    wadah: list[str] = []
    for baris in sumber:
        wadah.append(baris + "\n")
        if len(wadah) >= batch_size:
            yield "".join(wadah)
            wadah = []
    if wadah:
        yield "".join(wadah)


def generate_dataset(
    lines: int,
    output: str | Path,
    *,
    seed: int | None = None,
    keywords: Sequence[str] | None = None,
    files: int = 1,
    batch_size: int = 50_000,
    quiet: bool = True,
) -> DatasetInfo:
    """Bangkitkan dataset teks streaming sesuai kebutuhan Fase 2.

    Args:
        lines: jumlah baris total (mis. 1_000_000).
        output: path file tunggal (mis. ``data/corpus.txt``) ATAU direktori
            untuk mode multi-file (mis. ``data/multi/``).
        seed: seed RNG; default seed dari NPM proyek.
        keywords: daftar keyword; default 5 keyword turunan NPM.
        files: jumlah file (>= 1). Nama part: ``part_0001.txt``, ...
        batch_size: jumlah baris per sekali tulis.
        quiet: False ⇒ progress ke stderr tiap batch.

    Returns:
        DatasetInfo: termasuk ground truth dan path manifest.

    Raises:
        ValueError: lines <= 0, files <= 0, atau batch_size <= 0.
    """
    if lines <= 0:
        raise ValueError(f"lines harus > 0, diterima: {lines}")
    if files <= 0:
        raise ValueError(f"files harus > 0, diterima: {files}")
    if batch_size <= 0:
        raise ValueError(f"batch_size harus > 0, diterima: {batch_size}")

    p: ProjectParams = derive_params(NPM)
    seed = p.seed if seed is None else seed
    keywords = tuple(k.lower() for k in (keywords or p.keywords))

    pembuat = _PembuatBaris(seed, keywords)
    pola = compile_pattern(keywords)

    out = Path(output)
    multi = files > 1 or str(output).endswith(("/", "\\"))
    if multi:
        out.mkdir(parents=True, exist_ok=True)
        nama_parts = [out / f"part_{i + 1:04d}.txt" for i in range(files)]
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        nama_parts = [out]

    per_file = _bagi_rata(lines, len(nama_parts))
    ground: dict[str, list[int]] = {kw: [0, 0] for kw in keywords}
    mulai = _time.perf_counter()

    idx_file = 0
    sisa_file = per_file[0]
    fh = open(nama_parts[0], "w", encoding="utf-8", newline="\n")
    batch = 0
    ditulis = 0
    try:
        for _ in range(lines):
            if sisa_file == 0:
                fh.close()
                idx_file += 1
                sisa_file = per_file[idx_file]
                fh = open(nama_parts[idx_file], "w", encoding="utf-8", newline="\n")
            baris = pembuat.one_line()
            fh.write(baris + "\n")
            sisa_file -= 1
            ditulis += 1
            # ground truth dihitung SEKALI per baris dengan matcher yang sama
            for kw, n in match_line(pola, baris).items():
                c = ground.setdefault(kw, [0, 0])
                c[0] += 1          # lines: baris ini memuat kw
                c[1] += n          # occurrences: n kemunculan di baris ini
            if ditulis % batch_size == 0:
                fh.flush()
                batch += 1
                if not quiet:
                    print(
                        f"[GEN] {ditulis:,} / {lines:,} baris",
                        file=sys.stderr, flush=True,
                    )
    finally:
        fh.close()

    elapsed = _time.perf_counter() - mulai
    size = sum(f.stat().st_size for f in nama_parts)
    tiers = {
        kw: FREQUENCY_TIERS[i % len(FREQUENCY_TIERS)]
        for i, kw in enumerate(keywords)
    }
    ground_truth = {kw: {"lines": v[0], "occurrences": v[1]} for kw, v in ground.items()}
    meta = meta_path_for(output)
    if multi:
        meta.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "lines": lines,
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keywords": list(keywords),
        "tiers": tiers,
        "ground_truth": ground_truth,
        "size_bytes": size,
        "files": [str(f.name) for f in nama_parts],
        "batch_size": batch_size,
    }
    meta.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return DatasetInfo(
        lines=lines,
        paths=nama_parts,
        size_bytes=size,
        seed=seed,
        keywords=keywords,
        ground_truth=ground_truth,
        meta_path=meta,
        elapsed_sec=elapsed,
        tiers=tiers,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point CLI generator dataset.

    Returns:
        int: 0 sukses; != 0 bila argumen tidak valid.
    """
    print(banner())
    ap = argparse.ArgumentParser(
        prog="textsearch.dataset_gen",
        description="Generator dataset teks streaming (seed & keyword default dari NPM).",
    )
    ap.add_argument("--lines", required=True, help="Jumlah baris, mis. 1M, 500K, 1_000_000")
    ap.add_argument("--out", required=True, help="File output atau direktori (mode multi-file)")
    ap.add_argument("--files", type=int, default=1, help="Jumlah file (multi-file)")
    ap.add_argument("--seed", type=int, default=None, help="Seed RNG (default: dari NPM)")
    ap.add_argument("--batch-size", type=int, default=50_000, help="Baris per sekali tulis")
    ap.add_argument("--quiet", action="store_true", help="Tanpa progress")
    args = ap.parse_args(argv)

    try:
        lines = parse_line_count(args.lines)
        info = generate_dataset(
            lines,
            args.out,
            seed=args.seed,
            files=args.files,
            batch_size=args.batch_size,
            quiet=args.quiet,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"Baris dibuat   : {info.lines:,}")
    print(f"File           : {', '.join(str(p) for p in info.paths)}")
    print(f"Ukuran         : {info.size_bytes / 2**20:,.1f} MB")
    print(f"Waktu generate : {info.elapsed_sec:.2f} detik")
    print(f"Manifest       : {info.meta_path}")
    print("Ground truth   :")
    for kw, v in info.ground_truth.items():
        tier = info.tiers.get(kw, "?")
        print(f"  {kw:<10} [{tier:<6}] lines={v['lines']:,} occurrences={v['occurrences']:,}")
    print(banner())
    return 0


if __name__ == "__main__":
    sys.exit(main())
