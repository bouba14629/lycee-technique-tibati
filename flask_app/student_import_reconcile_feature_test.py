import os
from io import BytesIO

DB = "/tmp/ltt-student-import-reconcile.sqlite"
if os.path.exists(DB):
    os.remove(DB)
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

from app import app
from models import Department, SchoolClass, Section, Student, User, db


def login_founder(client):
    login = client.post("/login", data={"username": "proviseur", "password": os.environ["LTT_INITIAL_ADMIN_PASSWORD"]})
    assert login.status_code in (302, 303), login.data[:300]
    changed = client.post("/premiere-connexion", data={
        "password": "NouveauMotDePasse#2026",
        "confirmation": "NouveauMotDePasse#2026",
    })
    assert changed.status_code in (302, 303), changed.data[:300]


with app.app_context():
    db.drop_all()
    db.create_all()
    founder = User(username="proviseur", role="directeur", full_name="Proviseur Test", active=True)
    founder.set_password(os.environ["LTT_INITIAL_ADMIN_PASSWORD"])
    db.session.add(founder)
    db.session.flush()
    section = Section(name="Section réconciliation", code="REC")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Filière réconciliation", code="REC", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="1A REC", code="REC-1A", level="1A", department_id=department.id)
    db.session.add(school_class)
    db.session.flush()
    class_id = school_class.id
    department_id = department.id

    for full_name, matricule in (("Paul MBOG", "REC-001"), ("Jeanne NKOA", "REC-002")):
        user = User(username=full_name.lower().replace(" ", "."), role="eleve", full_name=full_name, active=True)
        user.set_password("AncienMotDePasse#2026")
        db.session.add(user)
        db.session.flush()
        first, last = full_name.split(" ", 1)
        db.session.add(Student(user_id=user.id, first_name=first, last_name=last, matricule=matricule, class_id=class_id))
    db.session.commit()

with app.test_client() as client:
    login_founder(client)
    csv = "Nom complet,Matricule,Classe,Sexe\nPaul MBOG,REC-001,1A REC,M\n".encode()
    preview = client.post("/eleves/import/previsualiser", data={
        "class_id": str(class_id),
        "department_id": str(department_id),
        "import_file": (BytesIO(csv), "liste_rec.csv"),
    }, content_type="multipart/form-data")
    assert preview.status_code == 200, (preview.status_code, preview.headers.get("Location"), preview.data[:300])
    assert b"Paul MBOG" in preview.data
    confirmed = client.post("/eleves/import/confirmer")
    assert confirmed.status_code in (302, 303)

with app.app_context():
    assert Student.query.filter_by(matricule="REC-001").count() == 1
    assert Student.query.filter_by(matricule="REC-002").count() == 0
    assert Student.query.filter_by(matricule="REC-001").one().user.check_password("AncienMotDePasse#2026")
    assert User.query.filter_by(username="jeanne.nkoa").count() == 0

print("STUDENT_IMPORT_RECONCILE_FEATURE_TEST_OK")
