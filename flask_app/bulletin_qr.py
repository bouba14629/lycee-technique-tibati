import base64
import os
from io import BytesIO

import qrcode
from flask import current_app, render_template, abort, url_for, make_response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import joinedload

from app import app
from models import Student, SchoolClass, Department
from utils import TERMS, bulletin_data, annual_bulletin_data, get_current_school_year


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="ltt-bulletin-qr")


def bulletin_qr_token(student, term):
    return _serializer().dumps({"student_id": student.id, "term": term})


def bulletin_qr_url(student, term):
    # Ne jamais encoder request.host dans le QR : pendant un export via le
    # worker Flask, ce host peut être localhost ou un port interne invisible
    # depuis le téléphone. Le domaine public peut être remplacé par
    # LTT_PUBLIC_URL lors d’un hébergement personnalisé.
    public_base = os.getenv("LTT_PUBLIC_URL", "https://lyceetech-njuwbcl2.manus.space").rstrip("/")
    path = url_for("bulletin_qr_view", token=bulletin_qr_token(student, term))
    return public_base + path


def bulletin_qr_payload(student, term, data=None, school_year=None):
    """Contenu lisible du QR, sans dépendre d’un hôte ou d’une route locale."""
    data = data or (annual_bulletin_data(student) if term == "Annuel" else bulletin_data(student, term=term)) or {}
    marks = data.get("decision_marks") or {}
    if marks.get("excluded"):
        decision = "Exclu(e)"
    elif marks.get("repeat_if_failure"):
        decision = f"Redouble la classe de {data.get('repeat_class_name') or '—'} si échec"
    elif marks.get("admitted"):
        decision = f"Admis(e) en classe de {data.get('next_class_name') or '—'}"
    else:
        decision = "—"
    photo = student.photo or "Non disponible"
    if str(photo).startswith("data:"):
        photo = "Photo disponible (image intégrée)"
    elif len(str(photo)) > 180:
        photo = "Photo disponible"
    dob = student.dob.strftime("%d/%m/%Y") if student.dob else "—"
    school_class = student.school_class.name if student.school_class else "—"
    average = data.get("overall_avg")
    return "\n".join([
        "BULLETIN - LT TIBATI",
        f"Noms et Prénoms : {student.full_name}",
        f"Date et lieu de naissance : {dob} à {student.birth_place or '—'}",
        f"Identifiant Unique : {student.matricule or '—'}",
        f"Photo : {photo}",
        f"Année Scolaire : {school_year or get_current_school_year()}",
        f"Classe : {school_class}",
        f"Moyenne : {average if average is not None else '—'}",
        f"DÉCISION DU CONSEIL DE CLASSE : {decision}",
    ])


def bulletin_qr_data_uri(student, term, data=None, school_year=None):
    """QR PNG détaillé embarqué directement dans le HTML/PDF."""
    try:
        code = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                             box_size=4, border=1)
        code.add_data(bulletin_qr_payload(student, term, data=data, school_year=school_year))
        code.make(fit=True)
        image = code.make_image(fill_color="#102F55", back_color="white")
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    except Exception:
        return None


@app.get("/bulletin/qr/<token>")
def bulletin_qr_view(token):
    try:
        payload = _serializer().loads(token, max_age=3600 * 24 * 410)
    except (BadSignature, SignatureExpired):
        abort(404)
    student = (Student.query.options(
        joinedload(Student.user),
        joinedload(Student.school_class).joinedload(SchoolClass.department).joinedload(Department.section),
    ).filter(Student.id == payload.get("student_id")).first())
    term = payload.get("term")
    if not student or term not in (*TERMS, "Annuel"):
        abort(404)
    school_year = get_current_school_year()
    data = annual_bulletin_data(student) if term == "Annuel" else bulletin_data(student, term=term)
    marks = data.get("decision_marks") or {}
    if marks.get("excluded"):
        decision_label = "Exclu(e)"
    elif marks.get("repeat_if_failure"):
        decision_label = f"Redouble la classe de {data.get('repeat_class_name') or '—'} si échec"
    elif marks.get("admitted"):
        decision_label = f"Admis(e) en classe de {data.get('next_class_name') or '—'}"
    else:
        decision_label = "Décision non renseignée pour cette période"
    from app import student_photo_url
    response = make_response(render_template(
        "bulletin_qr.html", student=student, data=data, term=term,
        school_year=school_year, photo_url=student_photo_url(student.photo),
        decision_label=decision_label,
    ))
    # Le token est signé et immuable ; un bref cache accélère les scans répétés
    # sans conserver une ancienne note plus longtemps que quelques secondes.
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=30"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
