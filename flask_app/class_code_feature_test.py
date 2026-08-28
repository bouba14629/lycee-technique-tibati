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
        data={"department_id": department_id, "level": "1A", "specialty": "ELEQ", "code": "IND-1A-ELEQ"},
    )
    assert created.status_code in (302, 303)

    with app.app_context():
        school_class = SchoolClass.query.one()
        assert school_class.code == "IND-1A-ELEQ"
        class_id = school_class.id

    duplicate = client.post(
        "/directeur/structure/classe/nouvelle",
        data={"department_id": department_id, "level": "2A", "specialty": "ELEQ", "code": "IND-1A-ELEQ"},
    )
    assert duplicate.status_code in (302, 303)
    with app.app_context():
        assert SchoolClass.query.count() == 1

    updated = client.post(
        f"/directeur/structure/classe/{class_id}/modifier",
        data={"level": "Tle", "specialty": "F3", "code": "IND-TLE-F3"},
    )
    assert updated.status_code in (302, 303)
    with app.app_context():
        school_class = db.session.get(SchoolClass, class_id)
        assert school_class.code == "IND-TLE-F3"
        assert school_class.name == "TERMINALE F3"

    for template_name in ("dir_structure.html", "censeur_council_stats.html", "censeur_indicators.html", "teacher_indicators.html"):
        template_path = os.path.join(os.path.dirname(__file__), "templates", template_name)
        with open(template_path, encoding="utf-8") as template_file:
            assert ".code" in template_file.read()

    excel_path = os.path.join(os.path.dirname(__file__), "excel_utils.py")
    with open(excel_path, encoding="utf-8") as excel_file:
        excel_content = excel_file.read()
    assert "CODE" in excel_content
    assert "school_class.code" in excel_content
    assert "row['class'].code or 'Sans code', row" in excel_content
    print("CLASS_CODE_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
