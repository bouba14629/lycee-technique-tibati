import os

os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from models import Department, Section, Subject, User, db


with app.app_context():
    db.drop_all()
    db.create_all()
    principal = User(username="proviseur.bulletin", full_name="Proviseur Bulletin", role="directeur", active=True)
    principal.set_password("Test#2026")
    section = Section(name="Section Bulletin", code="BUL")
    db.session.add_all([principal, section])
    db.session.flush()
    department = Department(name="Filière Bulletin", code="BUL", section_id=section.id)
    db.session.add(department)
    db.session.commit()
    department_id = department.id

    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur.bulletin", "password": "Test#2026"})
        assert login.status_code in (302, 303)
        structure = client.get("/directeur/structure")
        assert structure.status_code == 200
        assert b"Pr\xc3\xa9paration des bulletins" in structure.data
        created = client.post("/directeur/structure/matiere/nouvelle", data={
            "department_id": str(department_id), "name": "Atelier pratique", "coefficient": "4",
            "category": "Enseignements Professionnels Pratiques",
        })
        assert created.status_code in (302, 303)
        subject = Subject.query.filter_by(name="Atelier pratique").one()
        assert subject.coefficient == 4

print("BULLETIN_SETUP_FEATURE_TEST_OK")
