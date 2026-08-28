import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-alphabetical-list.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User


with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.alpha", full_name="Proviseur Test", role="directeur", active=True, must_change_password=False)
    director.set_password("MotDePasseTest#2026")
    section = Section(name="Industrielle", code="IND")
    db.session.add_all([director, section])
    db.session.flush()
    department = Department(name="Électricité", code="ELEQ", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="PREMIERE ANNEE ELEQ", level="1A", department_id=department.id)
    db.session.add(school_class)
    db.session.flush()
    db.session.add_all([
        Student(first_name="Zoé", last_name="Zouma", matricule="LTT-Z-001", sex="F", class_id=school_class.id, status="Inscrit"),
        Student(first_name="Amina", last_name="Alpha", matricule="LTT-A-001", sex="F", class_id=school_class.id, status="Inscrit"),
        Student(first_name="Boris", last_name="Alpha", matricule="LTT-A-002", sex="M", class_id=school_class.id, status="Inscrit"),
    ])
    db.session.commit()

    app.config.update(TESTING=True)
    client = app.test_client()
    assert client.post("/login", data={"username": "proviseur.alpha", "password": "MotDePasseTest#2026"}).status_code in (302, 303)
    page = client.get("/eleves")
    assert page.status_code == 200
    assert page.data.index(b"Amina") < page.data.index(b"Boris") < page.data.index(b"Zo\xc3\xa9")
    assert client.get("/eleves/export.xlsx").status_code == 200
    assert client.get("/eleves/export.pdf").status_code == 200

print("STUDENT_ALPHABETICAL_LIST_FEATURE_TEST_OK")
