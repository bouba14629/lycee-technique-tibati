import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-enroll-class-return.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User

with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.enroll.return", full_name="Proviseur Test", role="directeur", active=True)
    director.set_password("MotDePasseTest#2026")
    section = Section(name="Section Inscription", code="INS")
    db.session.add_all([director, section])
    db.session.flush()
    department = Department(name="Département Inscription", code="DINS", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    selected_class = SchoolClass(name="Classe Sélectionnée", code="SEL", level="Test", department_id=department.id)
    other_class = SchoolClass(name="Autre Classe", code="AUT", level="Test", department_id=department.id)
    db.session.add_all([selected_class, other_class])
    db.session.commit()

    app.config.update(TESTING=True)
    client = app.test_client()
    login = client.post("/login", data={"username": director.username, "password": "MotDePasseTest#2026"})
    assert login.status_code in (302, 303)

    form = client.get(f"/eleves/inscription?return_class_id={selected_class.id}")
    assert form.status_code == 200
    assert f'name="return_class_id" value="{selected_class.id}"'.encode() in form.data
    assert f'value="{selected_class.id}" selected'.encode() in form.data

    created = client.post("/eleves/inscription", data={
        "return_class_id": selected_class.id,
        "first_name": "Amina", "last_name": "Tibati", "matricule": "RET-2026-001",
        "sex": "F", "class_id": other_class.id, "status": "Inscrit",
    }, follow_redirects=False)
    assert created.status_code in (302, 303)
    assert created.headers["Location"].endswith(f"/eleves?class_id={selected_class.id}")
    assert Student.query.one().class_id == other_class.id

    duplicate = client.post("/eleves/inscription", data={
        "return_class_id": selected_class.id,
        "first_name": "Autre", "last_name": "Élève", "matricule": "RET-2026-001",
        "sex": "M", "class_id": selected_class.id, "status": "Inscrit",
    }, follow_redirects=False)
    assert duplicate.status_code in (302, 303)
    assert duplicate.headers["Location"].endswith(
        f"/eleves/inscription?return_class_id={selected_class.id}"
    )

print("STUDENT_ENROLL_CLASS_FILTER_RETURN_FEATURE_TEST_OK")
