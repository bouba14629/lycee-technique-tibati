import os
from pathlib import Path

TEST_DB = Path("/tmp/ltt-student-certificate-route.sqlite")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LTT_ENV"] = "development"

from app import app
from models import db, User, Student


app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with app.app_context():
    db.drop_all()
    db.create_all()
    principal = User(username="proviseur.cert", role="directeur", full_name="Proviseur Test", active=True)
    principal.set_password("Proviseur#2026")
    student_user = User(username="eleve.cert", role="eleve", full_name="Amina Test", active=True)
    student_user.set_password("Eleve#2026")
    db.session.add_all([principal, student_user])
    db.session.flush()
    student = Student(user_id=student_user.id, matricule="CERT-001", first_name="Amina", last_name="Test")
    db.session.add(student)
    db.session.commit()

with app.test_client() as client:
    login = client.post("/login", data={"username": "eleve.cert", "password": "Eleve#2026"})
    assert login.status_code in (302, 303)
    response = client.get("/eleve/certificat-scolarite")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")

print("STUDENT_CERTIFICATE_ROUTE_FEATURE_TEST_OK")
