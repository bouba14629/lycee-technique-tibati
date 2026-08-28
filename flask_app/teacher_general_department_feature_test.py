import os
import sys


os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-teacher-general-department.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules)
                    if name in {"app", "models", "utils", "directeur_routes", "censeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import Department, Section, Teacher, User, db


with app.app_context():
    db.drop_all()
    db.create_all()
    principal = User(username="proviseur.general", full_name="Proviseur Général", role="directeur",
                     active=True, must_change_password=False)
    principal.set_password("Test#2026")
    section = Section(name="Section Test", code="TST")
    db.session.add_all([principal, section])
    db.session.flush()
    department = Department(name="Filière technique", code="FT", section_id=section.id)
    db.session.add(department)
    db.session.commit()

    with app.test_client() as client:
        assert client.post("/login", data={"username": "proviseur.general", "password": "Test#2026"}).status_code == 302
        form = client.get("/directeur/utilisateurs/nouveau")
        assert form.status_code == 200
        assert b"Civilit\xc3\xa9" in form.data
        assert b'value="Mme."' in form.data and b'value="M."' in form.data
        assert b"Enseignement g\xc3\xa9n\xc3\xa9ral" in form.data
        assert b"Fili\xc3\xa8re technique" in form.data

        created = client.post("/directeur/utilisateurs/nouveau", data={
            "full_name": "Mathieu Général",
            "role": "enseignant",
            "civility": "Mme.",
            "department_id": "",
            "specialty": "Mathématiques",
            "grade": "PLEG",
            "hours_due": "18",
        })
        assert created.status_code in (302, 303)
        teacher_user = User.query.filter_by(full_name="Mathieu Général").one()
        teacher = Teacher.query.filter_by(user_id=teacher_user.id).one()
        assert teacher.department_id is None
        assert teacher.specialty == "Mathématiques"
        assert teacher_user.civility == "Mme."
        assert teacher_user.must_change_password is True

print("TEACHER_GENERAL_DEPARTMENT_FEATURE_TEST_OK")
