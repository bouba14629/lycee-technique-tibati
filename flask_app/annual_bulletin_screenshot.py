from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import white, black

MODEL_PATH = Path(__file__).resolve().parent / "templates" / "pdf" / "annual_model" / "Bulletin_annuel_importe.pdf"
PAGE_W, PAGE_H = 595.92, 842.88
# Coordonnées haut de page du modèle importé : 6 + 4 + 8 + 2 lignes de matières.
ROW_TOPS = [286.3, 296.8, 308.0, 319.3, 329.8, 341.0,
            377.0, 388.3, 399.5, 410.6,
            446.8, 457.9, 468.5, 479.8, 490.3, 501.5,
            537.5, 548.8]


def _text(c, x, top, value, size=6.5, max_width=None):
    value = "—" if value is None or value == "" else str(value)
    if max_width:
        while len(value) > 1 and c.stringWidth(value, "Helvetica", size) > max_width:
            value = value[:-1]
        if value != str(value):
            value = value.rstrip() + "…"
    c.setFont("Helvetica", size)
    c.setFillColor(black)
    c.drawString(x, PAGE_H - top - size, value)


def _cover(c, x, top, width, height):
    c.setFillColor(white)
    c.rect(x, PAGE_H - top - height, width, height, stroke=0, fill=1)


def _overlay(student, data, school_year):
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(PAGE_W, PAGE_H))
    # Les cadres, logos, titres et bordures restent ceux du PDF importé.
    _cover(c, 445, 146, 108, 15)
    _text(c, 448, 149, student.full_name, 6.8, 102)
    _cover(c, 389, 174, 75, 15)
    _text(c, 390, 178, school_year, 6.5, 70)
    _cover(c, 88, 177, 150, 14)
    _text(c, 91, 179, student.full_name, 6.5, 142)
    _cover(c, 352, 189, 80, 14)
    _text(c, 354, 191, student.school_class.name, 6.5, 75)

    rows = [row for category in data.get("categories", []) for row in category.get("rows", [])]
    for top, row in zip(ROW_TOPS, rows):
        # Le texte de la matière est remplacé dans la cellule, sans toucher aux bordures.
        _cover(c, 16, top - 1, 204, 9.5)
        subject = row["course"].subject.name
        _text(c, 19, top, subject, 5.6, 198)
        for x, width, value in (
            (220, 43, row.get("annual")),
            (263, 37, (row.get("terms") or [None, None, None])[0]),
            (300, 35, (row.get("terms") or [None, None, None])[1]),
            (335, 33, (row.get("terms") or [None, None, None])[2]),
            (368, 32, row.get("coef")),
            (400, 31, row.get("points")),
            (431, 29, f"{row.get('rank')}e" if row.get("rank") else "—"),
        ):
            _cover(c, x + 1, top - 1, width - 2, 9.5)
            text = value if value is not None else "—"
            c.setFont("Helvetica", 5.7)
            text = str(text)
            c.drawCentredString(x + width / 2, PAGE_H - top - 7, text)

    # Valeurs de synthèse : les libellés et cadres restent ceux du modèle importé.
    _cover(c, 210, 587, 72, 11)
    _text(c, 214, 589, data.get("overall_points"), 6.2, 65)
    _cover(c, 430, 587, 40, 11)
    _text(c, 433, 589, data.get("class_avg"), 6.2, 36)
    _cover(c, 210, 599, 72, 11)
    _text(c, 214, 601, data.get("overall_avg"), 6.2, 65)
    _cover(c, 430, 599, 40, 11)
    _text(c, 433, 601, data.get("class_high"), 6.2, 36)
    _cover(c, 210, 610, 72, 11)
    _text(c, 214, 612, f"{data.get('rank') or '—'}/{data.get('class_size') or 0}", 6.2, 65)
    _cover(c, 430, 610, 40, 11)
    _text(c, 433, 612, data.get("class_low"), 6.2, 36)
    c.save()
    stream.seek(0)
    return stream


def render_annual_bulletins(students_data, school_year):
    writer = PdfWriter()
    for item in students_data:
        base = PdfReader(str(MODEL_PATH)).pages[0]
        overlay = PdfReader(_overlay(item["student"], item["data"], school_year)).pages[0]
        base.merge_page(overlay)
        writer.add_page(base)
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output
