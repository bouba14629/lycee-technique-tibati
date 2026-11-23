import base64
import os
import time
from collections import OrderedDict
from io import BytesIO
from pathlib import Path

import qrcode
from PIL import Image, ImageOps
from flask import abort, has_request_context, make_response, render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import joinedload

from app import app, ltt_url_for, student_photo_url
from models import Department, SchoolClass, Student
from utils import TERMS, annual_bulletin_data, bulletin_data, get_current_school_year


_QR_PAGE_CACHE = OrderedDict()
_QR_PAGE_CACHE_TTL = 60
_QR_PAGE_CACHE_MAX = 512


def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="ltt-bulletin-qr")


def bulletin_qr_token(student, term):
    return _serializer().dumps({"student_id": student.id, "term": term})


def bulletin_qr_url(student, term):
    # Le domaine public est stable pour que le QR reste lisible depuis un téléphone,
    # même lorsqu'un PDF est produit par un worker local.
    public_base = os.getenv("LTT_PUBLIC_URL", "https://lyceetech-njuwbcl2.manus.space").rstrip("/")
    token = bulletin_qr_token(student, term)
    if has_request_context():
        path = url_for("bulletin_qr_view", token=token)
    else:
        # Les exports batch peuvent être exécutés hors requête Flask.
        with app.test_request_context(base_url=public_base):
            path = url_for("bulletin_qr_view", token=token)
    return public_base + path


def _logo_path():
    packaged = Path(__file__).resolve().parent / "templates" / "pdf" / "bulletin_model" / "LOGOLTT.jpg"
    if packaged.is_file():
        return packaged
    return None


def _logo_image(size):
    path = _logo_path()
    if not path:
        return None
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            return image
    except Exception:
        app.logger.warning("Institution logo unavailable for QR", exc_info=True)
        return None


def _qr_logo_data_uri():
    path = _logo_path()
    if not path:
        return None
    try:
        with open(path, "rb") as logo_file:
            return "data:image/jpeg;base64," + base64.b64encode(logo_file.read()).decode("ascii")
    except OSError:
        return None


def bulletin_qr_data_uri(student, term):
    """Petit QR PNG autonome, avec le logo de l'établissement au centre."""
    try:
        code = qrcode.QRCode(
            version=None,
            # H permet de masquer une partie du code par le logo tout en restant lisible.
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=4,
            border=2,
        )
        code.add_data(bulletin_qr_url(student, term))
        code.make(fit=True)
        image = code.make_image(fill_color="#102F55", back_color="white").convert("RGBA")
        logo = _logo_image(max(24, image.width // 5))
        if logo:
            pad = max(3, image.width // 80)
            plate_size = max(logo.width, logo.height) + (pad * 2)
            x = (image.width - plate_size) // 2
            y = (image.height - plate_size) // 2
            plate = Image.new("RGBA", (plate_size, plate_size), "white")
            plate.alpha_composite(logo, ((plate_size - logo.width) // 2, (plate_size - logo.height) // 2))
            image.alpha_composite(plate, (x, y))
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception:
        app.logger.exception("QR generation failed student_id=%s term=%s", getattr(student, "id", None), term)
        return None


def _decision_label(data):
    marks = data.get("decision_marks", {}) if isinstance(data, dict) else {}
    work_marks = data.get("work_marks", {}) if isinstance(data, dict) else {}
    competency_labels = []
    if work_marks.get("travail_insuffisant"):
        competency_labels.append("Compétences non acquises")
    if work_marks.get("bon_travail"):
        competency_labels.append("Compétences moyennement acquises")
    if work_marks.get("travail_passable"):
        competency_labels.append("Compétences bien acquises")
    if work_marks.get("assez_bon_travail"):
        competency_labels.append("Compétences très bien acquises")
    mention_labels = []
    if work_marks.get("tableau_honneur"):
        mention_labels.append("Tableau d'Honneur")
    if work_marks.get("encouragements"):
        mention_labels.append("Encouragements")
    if work_marks.get("felicitations"):
        mention_labels.append("Félicitations")
    competency_decision = " · ".join(mention_labels + competency_labels)
    if marks.get("excluded"):
        reasons = []
        if marks.get("insolvency"):
            reasons.append("Insolvabilité")
        if marks.get("resigning"):
            reasons.append("Démissionnaire")
        if marks.get("cannot_triplicate"):
            reasons.append("Ne peut tripler")
        if marks.get("conduct"):
            reasons.append("Conduite")
        if marks.get("competencies_not_acquired"):
            reasons.append("Compétences non acquises")
        label = "Exclu(e)" + (" — " + ", ".join(reasons) if reasons else "")
        return label + (" · " + competency_decision if competency_decision else "")
    if marks.get("admitted"):
        label = "Admis(e) en classe de " + str(data.get("next_class_name") or "—")
        return label + (" · " + competency_decision if competency_decision else "")
    if marks.get("repeat_if_failure"):
        label = "Redouble la classe de " + str(data.get("repeat_class_name") or "—") + " si échec"
        return label + (" · " + competency_decision if competency_decision else "")
    return competency_decision or "Décision en attente"


def _qr_view_data(student, data, term):
    school_class = student.school_class
    return {
        "full_name": student.full_name,
        "birth_date": student.dob.strftime("%d/%m/%Y") if student.dob else "—",
        "birth_place": student.birth_place or "—",
        "matricule": student.matricule or "—",
        "photo_url": student_photo_url(student.photo) if student.photo else None,
        "school_year": get_current_school_year(),
        "class_name": school_class.name if school_class else "—",
        "average": data.get("overall_avg") if isinstance(data, dict) else None,
        "rank": data.get("rank_label") or data.get("rank") if isinstance(data, dict) else None,
        "decision": _decision_label(data),
        "term": term,
        "institution_name": "Lycée Technique de Tibati",
        "institution_logo_url": ltt_url_for("static", filename="img/logo.png"),
        "qr_image": bulletin_qr_data_uri(student, term),
    }


def _cached_page(token):
    item = _QR_PAGE_CACHE.get(token)
    if not item:
        return None
    created, html = item
    if time.monotonic() - created > _QR_PAGE_CACHE_TTL:
        _QR_PAGE_CACHE.pop(token, None)
        return None
    _QR_PAGE_CACHE.move_to_end(token)
    return html


def _cache_page(token, html):
    _QR_PAGE_CACHE[token] = (time.monotonic(), html)
    _QR_PAGE_CACHE.move_to_end(token)
    while len(_QR_PAGE_CACHE) > _QR_PAGE_CACHE_MAX:
        _QR_PAGE_CACHE.popitem(last=False)


def _qr_student_from_token(token):
    try:
        payload = _serializer().loads(token, max_age=3600 * 24 * 410)
    except (BadSignature, SignatureExpired):
        abort(404)
    term = payload.get("term")
    if term not in (*TERMS, "Annuel"):
        abort(404)
    student = (Student.query.options(
        joinedload(Student.school_class).joinedload(SchoolClass.department).joinedload(Department.section)
    ).filter(Student.id == payload.get("student_id")).first())
    if not student:
        abort(404)
    return student, term


@app.get("/bulletin/qr/<token>")
def bulletin_qr_view(token):
    cached = _cached_page(token)
    if cached:
        result = make_response(cached)
        result.headers["X-QR-Page-Cache"] = "HIT"
        result.headers["Cache-Control"] = "private, max-age=300, stale-while-revalidate=600"
        result.headers["X-Content-Type-Options"] = "nosniff"
        return result
    student, term = _qr_student_from_token(token)
    data = annual_bulletin_data(student) if term == "Annuel" else bulletin_data(student, term=term)
    view_data = _qr_view_data(student, data, term)
    html = render_template("bulletin_qr.html", student=student, data=data, **view_data)
    _cache_page(token, html)
    result = make_response(html)
    result.headers["X-QR-Page-Cache"] = "MISS"
    result.headers["Cache-Control"] = "private, max-age=300, stale-while-revalidate=600"
    result.headers["X-Content-Type-Options"] = "nosniff"
    return result
