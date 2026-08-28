import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Department, SchoolClass, Section, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        proviseur = User(username="proviseur.test", role="directeur", full_name="Proviseur Test")
        proviseur.set_password("Test#2026")
        section = Section(name="Industrielle", code="IND")
        department = Department(name="Électrotechnique", code="ELEQ", section=section)
        db.session.add_all([proviseur, section, department])
        db.session.commit()
        department_id = department.id

    client = app.test_client()
    login = client.post("/login", data={"username": "proviseur.test", "password": "Test#2026"})
    assert login.status_code in (302, 303)

    created = client.post(
        "/directeur/structure/classe/nouvelle",
        data={"department_id": department_id, "level": "1A", "specialty": "ELEQ"},
    )
    assert created.status_code in (302, 303)

    with app.app_context():
        school_class = SchoolClass.query.one()
        assert school_class.level == "1A"
        assert school_class.name == "PREMIERE ANNEE ELEQ"
        class_id = school_class.id

    edited = client.post(
        f"/directeur/structure/classe/{class_id}/modifier",
        data={"level": "Tle", "specialty": "ELEQ"},
    )
    assert edited.status_code in (302, 303)

    with app.app_context():
        school_class = db.session.get(SchoolClass, class_id)
        assert school_class.level == "Tle"
        assert school_class.name == "TERMINALE ELEQ"

    template_path = os.path.join(os.path.dirname(__file__), "templates", "dir_structure.html")
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()
    for label in ("PREMIERE ANNEE", "DEUXIEME ANNEE", "TROISIEME ANNEE", "QUATRIEME ANNEE", "SECONDE", "PREMIERE", "TERMINALE"):
        assert label in content
    print("CLASS_LEVEL_LABELS_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
