import os
import sys
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-card.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app, LTT_ASSETS
from models import db, Department, SchoolClass, Section, Student, User
from student_card_utils import card_token


def set_session(client, user):
    user.session_token = f"test-session-{user.id}"
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = user.role
        sess["name"] = user.full_name
        sess["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.card", full_name="Proviseur Test", role="directeur", active=True)
    director.set_password("MotDePasseTest#2026")
    student_user = User(username="eleve.card", full_name="Moussa Oumayatou", role="eleve", active=True)
    student_user.set_password("MotDePasseTest#2026")
    outsider = User(username="prof.card", full_name="Enseignant Hors Classe", role="enseignant", active=True)
    outsider.set_password("MotDePasseTest#2026")
    section = Section(name="Industriel", code="IND")
    db.session.add_all([director, student_user, outsider, section])
    db.session.flush()
    department = Department(name="Mécanique", code="MEC", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Deuxième année COME", level="Deuxième", department_id=department.id, school_year="2025-2026")
    db.session.add(school_class)
    db.session.flush()
    student = Student(user_id=student_user.id, matricule="240018072", first_name="Moussa", last_name="Oumayatou",
                      dob=date(2012, 1, 1), birth_place="Tibati", sex="M", class_id=school_class.id,
                      photo="/manus-storage/logo_10e20177.png", status="Inscrit")
    db.session.add(student)
    db.session.commit()

    client = app.test_client()
    set_session(client, director)
    preview = client.get(f"/eleves/{student.id}/carte")
    assert preview.status_code == 200, (preview.status_code, preview.data[:500])
    assert b"Carte scolaire" in preview.data
    assert student.matricule.encode() in preview.data
    assert b"data:image/png;base64" in preview.data
    assert b"/manus-storage/logo_10e20177.png" in preview.data
    assert b"card-cameroon-flag" in preview.data
    assert LTT_ASSETS["css/style.css"].startswith("/manus-storage/style_")
    printable_preview = preview.data.replace(
        b"</body>",
        b'<a href="https://manus.im" style="position:fixed;bottom:12px;right:12px">Made with Manus</a></body>',
    )
    with open("/tmp/ltt-student-card-print-preview.html", "wb") as preview_file:
        preview_file.write(printable_preview)

    verify = client.get(f"/cartes-scolaires/verifier/{card_token(student)}")
    assert verify.status_code == 200
    assert b"Carte scolaire valide" in verify.data
    invalid_verify = client.get("/cartes-scolaires/verifier/jeton-invalide")
    assert invalid_verify.status_code == 200
    assert b"Carte non valide" in invalid_verify.data

    pdf = client.get(f"/eleves/{student.id}/carte/telecharger.pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")
    with open("/tmp/ltt-student-card-export.pdf", "wb") as pdf_file:
        pdf_file.write(pdf.data)

    service_worker = client.get("/service-worker.js")
    assert service_worker.status_code == 200
    assert b"ltt-shell-v" in service_worker.data
    assert LTT_ASSETS["css/style.css"].encode() in service_worker.data

    student.photo = None
    db.session.commit()
    without_photo = client.get(f"/eleves/{student.id}/carte")
    assert without_photo.status_code == 200
    assert LTT_ASSETS["img/avatar_placeholder.png"].encode() in without_photo.data

    set_session(client, outsider)
    forbidden = client.get(f"/eleves/{student.id}/carte")
    assert forbidden.status_code == 403

print("STUDENT_CARD_FEATURE_TEST_OK")
