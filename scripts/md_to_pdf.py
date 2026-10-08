"""Konversi LAPORAN_UTS.md -> PDF dengan reportlab (Plotpalus).

Mendukung subset markdown yang dipakai laporan: heading (#..####), paragraf,
list, tabel pipe, blok kode fenced, gambar ``![alt](path)``, teks tebal
``**...**`` dan kode inline ``...``. Menangani path relatif terhadap root proyek.

Pakai: ``python scripts/md_to_pdf.py LAPORAN_UTS.md report/UTS_....pdf``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]

# Font DejaVu (bawaan matplotlib) agar karakter Indonesia/UTF-8 (— é •) tampil.
try:
    import matplotlib

    _fontdir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(_fontdir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_fontdir / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Mono", str(_fontdir / "DejaVuSansMono.ttf")))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu", boldItalic="DejaVu-Bold")
    FON, FON_B, FON_M = "DejaVu", "DejaVu-Bold", "DejaVu-Mono"
except Exception:  # pragma: no cover
    FON, FON_B, FON_M = "Helvetica", "Helvetica-Bold", "Courier"


def gaya():
    ss = getSampleStyleSheet()
    for st in ss.byName.values():
        if getattr(st, "fontName", None) in ("Helvetica", "Helvetica-Bold"):
            st.fontName = FON_B if st.fontName == "Helvetica-Bold" else FON
    ss.add(ParagraphStyle("SelTabel", parent=ss["Normal"], fontSize=8, leading=10))
    ss["Code"].fontName = FON_M
    ss["Code"].fontSize = 7.5
    ss["Code"].leading = 9.5
    ss.add(ParagraphStyle("Judul2", parent=ss["Heading2"], spaceBefore=14))
    return ss


def inline_md(teks: str) -> str:
    """Konversi **bold** dan `code` ke markup reportlab (escape HTML dulu)."""
    t = (teks.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", rf"<font face='{FON_M}'>\1</font>", t)
    return t


def parse_table(rows: list[str]) -> Table:
    data = []
    ss = gaya()
    for i, baris in enumerate(rows):
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", baris):
            continue
        sel = [Paragraph(inline_md(c.strip()), ss["SelTabel"])
               for c in baris.strip().strip("|").split("|")]
        data.append(sel)
    tbl = Table(data, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.88, 0.9, 0.93)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def build(md_path: Path, out_pdf: Path) -> None:
    ss = gaya()
    story = []
    lines = md_path.read_text(encoding="utf-8").splitlines()
    i = 0
    in_code: list[str] = []
    tabel: list[str] = []
    while i < len(lines):
        baris = lines[i]
        if baris.startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(in_code), ss["Code"]))
                in_code = []
            i += 1
            continue
        if in_code:
            in_code.append(baris)
            i += 1
            continue
        if baris.strip().startswith("|"):
            tabel.append(baris)
            i += 1
            continue
        if tabel:
            story.append(parse_table(tabel))
            story.append(Spacer(1, 6))
            tabel = []
        m = re.match(r"^(#{1,4})\s+(.*)$", baris)
        if m:
            lvl = len(m.group(1))
            style = {1: "Title", 2: "Heading1", 3: "Judul2", 4: "Heading3"}[lvl]
            story.append(Paragraph(inline_md(m.group(2)), ss[style]))
            i += 1
            continue
        img = re.match(r"^\s*!\[(.*?)\]\((.*?)\)\s*$", baris)
        if img:
            p = (ROOT / img.group(2).replace("\\", "/")).resolve()
            if p.is_file():
                lebar = min(17 * cm, 17 * cm)
                story.append(Image(str(p), width=lebar, height=lebar * 0.62))
            else:
                story.append(Paragraph(f"[gambar tidak ditemukan: {p}]", ss["Normal"]))
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", baris):
            teks = re.sub(r"^\s*[-*]\s+", "• ", baris)
            story.append(Paragraph(inline_md(teks), ss["Normal"]))
            i += 1
            continue
        if baris.strip() == "---":
            story.append(Spacer(1, 10))
            i += 1
            continue
        if not baris.strip():
            story.append(Spacer(1, 5))
            i += 1
            continue
        # paragraf: gabung baris non-kosong beruntun
        par = [baris]
        while i + 1 < len(lines) and lines[i + 1].strip() \
                and not re.match(r"^(#{1,4}\s|```|\s*[-*]\s|\||!\[)", lines[i + 1]):
            i += 1
            par.append(lines[i])
        story.append(Paragraph(inline_md(" ".join(par)), ss["BodyText"]))
        i += 1
    if tabel:
        story.append(parse_table(tabel))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_pdf), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title="Laporan UTS Komputasi Paralel dan Terdistribusi",
        author="Shafa Rabbani Fityatul Mukarramah",
    )
    doc.build(story)
    print(f"PDF dibuat: {out_pdf}")


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "LAPORAN_UTS.md")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else ROOT / "report" / "UTS_247006111020_Shafa_Rabbani_Fityatul_Mukarramah.pdf")
    build(src, dst)
