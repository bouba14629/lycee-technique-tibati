import base64
import os
from io import BytesIO

import qrcode
from flask import abort, render_template, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import joinedload

from app import app, student_photo_url
from models import Department, SchoolClass, Student
from utils import TERMS, annual_bulletin_data, bulletin_data, get_current_school_year


def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="ltt-bulletin-qr")


def bulletin_qr_token(student, term):
    return _serializer().dumps({"student_id": student.id, "term": term})


def bulletin_qr_url(student, term):
    # Le domaine public est stable pour que le QR reste lisible depuis un téléphone,
    # même lorsqu'un PDF est produit par un worker local.
    public_base = os.getenv("LTT_PUBLIC_URL", "https://lyceetech-njuwbcl2.manus.space").rstrip("/")
    path = url_for("bulletin_qr_view", token=bulletin_qr_token(student, term))
    return public_base + path


def bulletin_qr_data_uri(student, term):
    """Petit QR PNG embarqué directement dans le HTML/PDF."""
    try:
        code = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        code.add_data(bulletin_qr_url(student, term))
        code.make(fit=True)
        image = code.make_image(fill_color="#102F55", back_color="white")
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception:
        app.logger.exception("QR generation failed student_id=%s term=%s", getattr(student, "id", None), term)
        return None


def _decision_label(data):
    marks = data.get("decision_marks", {}) if isinstance(data, dict) else {}
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
        return "Exclu(e)" + (" — " + ", ".join(reasons) if reasons else "")
    if marks.get("admitted"):
        return "Admis(e) en classe de " + str(data.get("next_class_name") or "—")
    if marks.get("repeat_if_failure"):
        return "Redouble la classe de " + str(data.get("repeat_class_name") or "—") + " si échec"
    return "Décision en attente"


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
    }


@app.get("/bulletin/qr/<token>")
def bulletin_qr_view(token):
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
    data = annual_bulletin_data(student) if term == "Annuel" else bulletin_data(student, term=term)
    view_data = _qr_view_data(student, data, term)
    response = render_template("bulletin_qr.html", student=student, data=data, **view_data)
    # Les tokens restent signés et expirent; ce cache court accélère les scans répétés
    # sans conserver longtemps les informations scolaires dans un proxy.
    from flask import make_response
    result = make_response(response)
    result.headers["Cache-Control"] = "private, max-age=120, stale-while-revalidate=300"
    result.headers["X-Content-Type-Options"] = "nosniff"
    return result
