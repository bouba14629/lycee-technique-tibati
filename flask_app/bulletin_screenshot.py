"""Rendu groupé par superposition sur le PDF officiel fourni.
Le fond n'est jamais reconstruit : logo, cadres, formes et proportions proviennent
exclusivement du modèle PDF importé. Seules les zones de données sont recouvertes
à l'intérieur des cellules puis alimentées par bulletin_data().
"""
import os
from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "templates" / "pdf" / "bulletin_model"
TEMPLATE = MODEL_DIR / "Bulletin_PREMIERE_ACA_v7.pdf"
PAGE_W, PAGE_H = A4

# Coordonnées mesurées sur Bulletin_PREMIERE_ACA_v7.pdf (origine en haut).
GROUP_ROW_STARTS = [219.615920, 327.591166, 411.937257, 531.642687]
GROUP_CAPACITY = [6, 4, 7, 2]
GROUP_TOTAL_TOPS = [293.609588, 377.956515, 497.661641, 558.723432]
VALUE_X = (169.0, 215.0, 251.0, 288.0, 316.0, 343.0, 379.0, 587.0)


def _top_y(top, height=8):
    return PAGE_H - top - height


def _fmt(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _white_cell(c, x1, x2, top, height=10.5):
    c.setFillColorRGB(1, 1, 1)
    c.rect(x1 + .65, PAGE_H - top - height + .55, x2 - x1 - 1.3, height - 1.1, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)


def _text(c, text, x, top, size=6.2, bold=False, align="left", color=(0, 0, 0)):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColorRGB(*color)
    y = _top_y(top, size + 1)
    if align == "center": c.drawCentredString(x, y, str(text))
    elif align == "right": c.drawRightString(x, y, str(text))
    else: c.drawString(x, y, str(text))
    c.setFillColorRGB(0, 0, 0)


def _overlay_student(student, data, school_year, term_ordinal, approval=None):
    out = BytesIO(); c = canvas.Canvas(out, pagesize=A4)
    # Fond strictement inchangé : le modèle PDF est fusionné ensuite.
    # Métadonnées élève : seules les valeurs variables sont masquées.
    for x1, x2, top in [(66, 153, 134.25), (68, 130, 142.8), (32, 60, 151.36), (66, 105, 159.92), (48, 67, 168.47),
                        (368, 406, 134.25), (343, 398, 142.8), (344, 370, 151.36), (384, 455, 159.92), (484, 556, 122.72)]:
        _white_cell(c, x1, x2, top, 9)
    _text(c, student.full_name, 67, 134.25, 6.4, bold=True)
    _text(c, student.dob.strftime('%d/%m/%Y') if student.dob else '—', 68, 142.8, 6.0)
    _text(c, student.sex or '—', 32, 151.36, 6.0)
    _text(c, student.matricule or '—', 67, 159.92, 6.0)
    _text(c, 'Oui' if student.is_repeater else 'Non', 49, 168.47, 6.0)
    _text(c, school_year, 368, 134.25, 6.0)
    _text(c, student.school_class.name if student.school_class else '—', 343, 142.8, 6.0)
    _text(c, len(student.school_class.students) if student.school_class else 0, 344, 151.36, 6.0)
    principal = student.school_class.homeroom_teacher.user.formal_name if student.school_class and student.school_class.homeroom_teacher else '—'
    _text(c, principal, 384, 159.92, 6.0)
    _text(c, student.full_name, 484, 122.72, 5.6, bold=True)
    # Titre et section (le logo et sa position restent ceux du PDF source).
    _white_cell(c, 195, 400, 78.5, 16)
    _text(c, f"BULLETIN DU {term_ordinal.upper()} TRIMESTRE", 297.5, 79.0, 13.2, bold=True, align="center")
    section = student.school_class.department.section.name.upper().replace('SECTION ', '') if student.school_class and student.school_class.department and student.school_class.department.section else ''
    _white_cell(c, 170, 442, 100.5, 13)
    _text(c, f"SECTION {section}", 306, 100.7, 8.8, bold=True, align="center", color=(11/255,37/255,69/255))

    # Matières et notes : la grille du fond est conservée, les cellules sont seulement remplies.
    categories = data.get('categories', [])
    for gi, cat in enumerate(categories[:4]):
        start = GROUP_ROW_STARTS[gi]
        for ri, row in enumerate(cat.get('rows', [])[:GROUP_CAPACITY[gi]]):
            top = start + ri * 11.73
            _white_cell(c, 9, 169, top, 10.7)
            _text(c, f"{row['course'].subject.name} ({row['course'].teacher.user.formal_name})", 11, top + .5, 5.2)
            vals = [row.get('notes_trim'), row.get('eval_a'), row.get('eval_b'), row.get('coef'), row.get('points'), f"{row.get('rank')}e" if row.get('rank') else '—', row.get('appreciation') or '']
            for j, value in enumerate(vals):
                x1, x2 = VALUE_X[j], VALUE_X[j+1]
                _white_cell(c, x1, x2, top, 10.7)
                text = _fmt(value)
                if j == 6: _text(c, text, x1 + 2, top + .5, 5.1, color=(98/255,98/255,98/255))
                else: _text(c, text, (x1+x2)/2, top + .5, 5.8, align='center', color=(198/255,40/255,40/255) if isinstance(value,(int,float)) and value < 10 else (0,0,0))
        total_top = GROUP_TOTAL_TOPS[gi]
        _white_cell(c, 220, 316, total_top, 10.5); _text(c, _fmt(cat.get('total_points')), 220, total_top + .4, 5.7, align='right')
        _white_cell(c, 353, 587, total_top, 10.5); _text(c, f"{_fmt(cat.get('moyenne'))} — {cat.get('pending_count', 0)} en attente" if cat.get('moyenne') is not None else f"— — {cat.get('pending_count', 0)} en attente", 355, total_top + .4, 5.7)

    # Synthèse : les valeurs se substituent aux valeurs d'exemple, sans toucher aux cadres.
    profile = [(data.get('overall_points'), data.get('class_avg')), (data.get('overall_coef'), data.get('highest_avg')), (data.get('overall_avg'), data.get('lowest_avg')), (f"{data.get('rank') or '—'}/{data.get('class_size', 0)}", f"{data.get('nb_above_10', 0)}/{data.get('class_size', 0)}"), (data.get('overall_eval_a_avg'), f"{data.get('success_rate', '—')}%"), (data.get('overall_eval_b_avg'), '')]
    for i, (left, right) in enumerate(profile):
        top = 594.46 + i * 10.78
        _white_cell(c, 190, 221, top, 9.5); _text(c, _fmt(left), 195, top + .3, 5.8, align='center')
        _white_cell(c, 480, 510, top, 9.5); _text(c, _fmt(right), 485, top + .3, 5.8, align='center')
    # Discipline/absence du modèle : heures déjà normalisées par le dataset bulletin.
    for top, value in [(675.1, data.get('absences_justified_hours', 0) + data.get('absences_non_justified_hours', 0)), (686.2, f"{data.get('absences_justified_days', 0) + data.get('absences_non_justified_days', 0)} (Just. {data.get('absences_justified_days', 0)} / Non just. {data.get('absences_non_justified_days', 0)})"), (697.3, len(data.get('exclusions', [])))]:
        _white_cell(c, 440, 540, top, 9.5); _text(c, _fmt(value), 445, top + .3, 5.5)
    c.showPage(); c.save(); out.seek(0); return out


def model_for_class(class_name):
    name = (class_name or '').upper()
    if 'ACA' in name and ('PREMIERE' in name or '1A' in name):
        return MODEL_DIR / 'Bulletin_PREMIERE_ACA_v7.pdf'
    if 'STT' in name and ('PREMIERE' in name or '1A' in name):
        return MODEL_DIR / 'Bulletin_PREMIERE_STT.pdf'
    if 'COME' in name and ('PREMIERE' in name or '1A' in name):
        return MODEL_DIR / 'Bulletin_PREMIERE_COME.pdf'
    return None


def render_grouped_screenshot(students_data, school_year, term_ordinal, approval=None, template_path=None):
    writer = PdfWriter()
    template_path = Path(template_path or TEMPLATE)
    for item in students_data:
        # Recharger le fond pour chaque page : pypdf peut partager des objets
        # indirects après merge_page, ce qui ferait réapparaître le premier élève.
        base = PdfReader(str(template_path)).pages[0]
        overlay = PdfReader(_overlay_student(item['student'], item['data'], school_year, term_ordinal, approval)).pages[0]
        base.merge_page(overlay)
        writer.add_page(base)
    out = BytesIO(); writer.write(out); out.seek(0); return out


def matches_template_layout(students_data):
    return all(
        len(item['data'].get('categories', [])) == 4
        and [len(cat.get('rows', [])) for cat in item['data']['categories']] == GROUP_CAPACITY
        for item in students_data
    )
