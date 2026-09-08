import os
os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-isolated-bulletin_setup_feature_test.sqlite"
os.environ["LTT_ENV"] = "development"


os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from models import Department, SchoolClass, Section, Subject, User, db


with app.app_context():
    db.drop_all()
    db.create_all()
    principal = User(username="proviseur.bulletin", full_name="Proviseur Bulletin", role="directeur", active=True)
    principal.set_password("Test#2026")
    section = Section(name="Section Bulletin", code="BUL")
    censeur = User(username="censeur.bulletin", full_name="Censeur Bulletin", role="censeur", active=True, section=section)
    censeur.set_password("Test#2026")
    db.session.add_all([principal, censeur, section])
    db.session.flush()
    department = Department(name="Filière Bulletin", code="BUL", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Classe Bulletin", code="BUL-1", level="1A", department_id=department.id)
    db.session.add(school_class)
    db.session.commit()
    class_id = school_class.id

    with app.test_client() as client:
        login = client.post("/login", data={"username": "censeur.bulletin", "password": "Test#2026"})
        assert login.status_code in (302, 303)
        structure = client.get("/directeur/structure")
        assert structure.status_code == 200
        assert b"Ajouter une mati\xc3\xa8re ou un tronc commun" in structure.data
        created = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"classe:{class_id}", "name": "Atelier pratique", "coefficient": "4",
            "category": "Enseignements Professionnels Pratiques",
        })
        assert created.status_code in (302, 303)
        subject = Subject.query.filter_by(name="Atelier pratique").one()
        assert subject.coefficient == 4

print("BULLETIN_SETUP_FEATURE_TEST_OK")
