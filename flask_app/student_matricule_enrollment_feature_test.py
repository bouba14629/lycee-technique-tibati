import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-matricule-enrollment.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User

with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.matricule", full_name="Proviseur Test", role="directeur", active=True, must_change_password=False)
    director.set_password("MotDePasseTest#2026")
    section = Section(name="Industrielle", code="IND")
    db.session.add_all([director, section])
    db.session.flush()
    department = Department(name="Électricité", code="ELEQ", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="PREMIERE ANNEE ELEQ", level="1A", department_id=department.id)
    db.session.add(school_class)
    db.session.commit()

    app.config.update(TESTING=True)
    client = app.test_client()
    login = client.post("/login", data={"username": "proviseur.matricule", "password": "MotDePasseTest#2026"})
    assert login.status_code in (302, 303)
    form = client.get("/eleves/inscription")
    assert form.status_code == 200
    assert b'name="matricule"' in form.data
    assert b"Code unique officiel" in form.data

    created = client.post("/eleves/inscription", data={
        "first_name": "Amina", "last_name": "Tibati", "matricule": "ltt-2026-001",
        "sex": "F", "class_id": school_class.id, "status": "Inscrit",
    }, follow_redirects=True)
    assert created.status_code == 200
    student = Student.query.one()
    assert student.matricule == "LTT-2026-001"

    duplicate = client.post("/eleves/inscription", data={
        "first_name": "Autre", "last_name": "Élève", "matricule": "LTT-2026-001",
        "sex": "M", "class_id": school_class.id, "status": "Inscrit",
    }, follow_redirects=True)
    assert b"d\xc3\xa9j\xc3\xa0 utilis\xc3\xa9" in duplicate.data
    assert Student.query.count() == 1

print("STUDENT_MATRICULE_ENROLLMENT_FEATURE_TEST_OK")
