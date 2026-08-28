import base64
from io import BytesIO
from pathlib import Path
import tempfile

import qrcode
from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="ltt-student-card")


def card_school_year(student):
    return student.school_class.school_year if student.school_class and student.school_class.school_year else "Année en cours"


def card_validity(student):
    school_year = card_school_year(student)
    end_year = school_year.split("-")[-1] if "-" in school_year else school_year
    return f"Septembre {end_year}"


def card_token(student):
    return _serializer().dumps({"student_id": student.id, "school_year": card_school_year(student)})


def validate_card_token(token):
    try:
        return _serializer().loads(token, max_age=3600 * 24 * 410)
    except (BadSignature, SignatureExpired):
        return None


def card_verification_url(student):
    return url_for("student_card_verify", token=card_token(student), _external=True)


def _qr_bytes(value):
    code = qrcode.QRCode(version=None, box_size=8, border=2)
    code.add_data(value)
    code.make(fit=True)
    image = code.make_image(fill_color="#102F55", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def card_qr_data_uri(student):
    data = base64.b64encode(_qr_bytes(card_verification_url(student))).decode("ascii")
    return f"data:image/png;base64,{data}"


def card_qr_file(student):
    target = Path(tempfile.gettempdir()) / f"ltt-card-qr-{student.id}.png"
    target.write_bytes(_qr_bytes(card_verification_url(student)))
    return str(target)
