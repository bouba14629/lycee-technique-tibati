import base64
from io import BytesIO

import qrcode
from flask import current_app, render_template, abort, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import app
from models import Student
from utils import TERMS, bulletin_data, annual_bulletin_data, get_current_school_year


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="ltt-bulletin-qr")


def bulletin_qr_token(student, term):
    return _serializer().dumps({"student_id": student.id, "term": term})


def bulletin_qr_url(student, term):
    return url_for("bulletin_qr_view", token=bulletin_qr_token(student, term), _external=True)


def bulletin_qr_data_uri(student, term):
    """Petit QR PNG embarqué directement dans le HTML/PDF."""
    try:
        code = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                             box_size=4, border=1)
        code.add_data(bulletin_qr_url(student, term))
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
    student = Student.query.get(payload.get("student_id"))
    term = payload.get("term")
    if not student or term not in (*TERMS, "Annuel"):
        abort(404)
    data = annual_bulletin_data(student) if term == "Annuel" else bulletin_data(student, term=term)
    return render_template("bulletin_qr.html", student=student, data=data, term=term,
                           school_year=get_current_school_year())
