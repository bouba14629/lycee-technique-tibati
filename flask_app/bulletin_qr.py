"""Accès sécurisé aux bulletins depuis un QR code.

Le QR ne contient jamais de note ni de donnée scolaire : il transporte seulement
un jeton signé identifiant l'élève, la période et l'année scolaire courante.
"""

import os
from urllib.parse import quote, urlsplit

from flask import abort, current_app, has_request_context, redirect, request, send_file, session, url_for
from itsdangerous import BadSignature, URLSafeSerializer

from models import AppSetting, BulletinApproval, Student, User, db
from utils import TERMS, TERM_ORDINALS, TERM_SEQUENCES, annual_bulletin_data, bulletin_data


QR_SALT = "bulletin-qr-v1"
QR_PATH = "/bulletins/qr/"
DEFAULT_PUBLIC_BASE_URL = "https://lt-tibati.com"
PUBLIC_HOSTS = frozenset(
    {
        "lt-tibati.com",
        "www.lt-tibati.com",
        "lttibati.com",
        "www.lttibati.com",
        "lyceetech-njuwbcl2.manus.space",
    }
)


def _serializer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=QR_SALT)


def _current_school_year_without_write():
    """Retourne l'année courante sans créer de réglage en base.

    ``utils.get_current_school_year`` initialise le réglage manquant et committe;
    une consultation via QR doit rester strictement sans écriture.
    """
    setting = AppSetting.query.first()
    return setting.current_school_year if setting and setting.current_school_year else "2025-2026"


def _safe_public_base_url():
    """Choisit une origine publique sans faire confiance à un Host arbitraire."""
    configured = os.getenv("LTT_PUBLIC_BASE_URL", "").strip()
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        # Une valeur de configuration invalide ne doit jamais être transformée
        # en URL utilisable par injection : on retombe sur l'origine canonique.
        return DEFAULT_PUBLIC_BASE_URL

    if not has_request_context():
        return DEFAULT_PUBLIC_BASE_URL
    host_header = request.headers.get("X-Forwarded-Host") or request.host
    host_header = host_header.split(",", 1)[0].strip().lower()
    try:
        parsed_host = urlsplit(f"//{host_header}")
        hostname = parsed_host.hostname
        port = parsed_host.port
    except ValueError:
        hostname, port = None, None
    if hostname in PUBLIC_HOSTS and port in (None, 443):
        return f"https://{hostname}"
    return DEFAULT_PUBLIC_BASE_URL


def build_bulletin_qr_url(student, data, school_year=None, term=None):
    """Construit l'URL publique signée d'un bulletin.

    ``data`` est accepté pour permettre aux renderers individuel et groupé de
    partager exactement le même appel; il n'est volontairement jamais sérialisé.
    """
    del data
    if student is None or getattr(student, "id", None) is None:
        raise ValueError("student must be a persisted Student")
    selected_term = term or "Annuel"
    if selected_term not in (*TERMS, "Annuel"):
        raise ValueError("invalid bulletin term")
    selected_year = school_year or _current_school_year_without_write()
    payload = {"s": int(student.id), "t": selected_term, "y": str(selected_year)}
    token = _serializer().dumps(payload)
    return f"{_safe_public_base_url()}{QR_PATH}{quote(token, safe='')}"


def _login_redirect():
    """app.login n'accepte comme retour que le chemin local d'un QR."""
    return redirect(url_for("login", next=request.path))


def _authorized_for_student(user, student):
    if not user:
        return False
    if user.role == "directeur":
        return True
    if user.role == "censeur":
        from utils import user_scoped_class_ids

        scoped_ids = user_scoped_class_ids(user)
        return scoped_ids is None or student.class_id in scoped_ids
    if user.role == "eleve":
        return student.user_id == user.id
    if user.role == "parent":
        return bool(user.parent_profile and any(child.id == student.id for child in user.parent_profile.children))
    return False


def _bulletin_qr_access(token):
    try:
        payload = _serializer().loads(token)
    except (BadSignature, TypeError, ValueError):
        abort(404)

    if not isinstance(payload, dict) or set(payload) != {"s", "t", "y"}:
        abort(404)
    try:
        student_id = int(payload["s"])
    except (TypeError, ValueError):
        abort(404)
    term = payload["t"]
    token_year = payload["y"]
    if term not in (*TERMS, "Annuel") or not isinstance(token_year, str) or not token_year:
        abort(404)

    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    if token_year != str(_current_school_year_without_write()):
        abort(410)

    if not session.get("user_id"):
        return _login_redirect()
    user = db.session.get(User, session["user_id"])
    if not _authorized_for_student(user, student):
        abort(403)

    if user.role in {"eleve", "parent"}:
        # Ne pas contourner la remise/validation ni ouvrir un nouveau droit
        # d'export : ces comptes gardent leur parcours de consultation actuel.
        from eleve_routes import _render_bulletin
        return _render_bulletin(student, term=term, viewer=user.role)

    from pdf_utils import get_student_photo_source, render_pdf

    approval = BulletinApproval.query.filter_by(
        class_id=student.class_id, term=term, status="Validé"
    ).first()
    photo_path = get_student_photo_source(student)
    common = {
        "student": student,
        "school_year": token_year,
        "approval": approval,
        "student_photo_path": photo_path,
        "photo_available": bool(photo_path),
    }
    if term == "Annuel":
        data = annual_bulletin_data(student)
        if not data:
            abort(404)
        pdf = render_pdf("pdf/bulletin_annual_pdf.html", data=data, **common)
        filename = f"Bulletin_annuel_{student.matricule}.pdf"
    else:
        data = bulletin_data(student, term=term)
        if not data:
            abort(404)
        seq_a, seq_b = TERM_SEQUENCES[term]
        common.update(
            {
                "data": data,
                "term": term,
                "TERM_SEQ_A": seq_a,
                "TERM_SEQ_B": seq_b,
                "term_ordinal": TERM_ORDINALS.get(term, ""),
                "bulletin_ref": f"{student.matricule}-T{TERMS.index(term) + 1}-{token_year}",
            }
        )
        pdf = render_pdf("pdf/bulletin_pdf.html", **common)
        filename = f"Bulletin_{student.last_name}_{student.first_name}_{term}.pdf".replace(" ", "_")
    if not pdf:
        abort(500)
    return send_file(pdf, mimetype="application/pdf", as_attachment=False, download_name=filename)


def register_bulletin_qr_routes(app):
    """Enregistre la route une seule fois sur l'application Flask donnée."""
    if "bulletin_qr_access" not in app.view_functions:
        app.add_url_rule(
            "/bulletins/qr/<token>",
            endpoint="bulletin_qr_access",
            view_func=_bulletin_qr_access,
            methods=["GET"],
        )
    return app
