import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Department, Section, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        proviseur = User(username="proviseur.test", role="directeur", full_name="Proviseur Test")
        proviseur.set_password("Test#2026")
        section = Section(name="Industrielle", code="IND")
        db.session.add_all([proviseur, section])
        db.session.commit()
        section_id = section.id

    client = app.test_client()
    login = client.post("/login", data={"username": "proviseur.test", "password": "Test#2026"})
    assert login.status_code in (302, 303)

    created = client.post(
        "/directeur/structure/filiere/nouvelle",
        data={"section_id": section_id, "name": "Électrotechnique", "code": "ELEQ", "capacity": "999"},
    )
    assert created.status_code in (302, 303)

    with app.app_context():
        department = Department.query.filter_by(code="ELEQ").first()
        assert department is not None
        assert department.capacity == 48
        department_id = department.id

    edited = client.post(
        f"/directeur/structure/filiere/{department_id}/modifier",
        data={"name": "Électrotechnique appliquée", "capacity": "1"},
    )
    assert edited.status_code in (302, 303)

    with app.app_context():
        department = db.session.get(Department, department_id)
        assert department.name == "Électrotechnique appliquée"
        assert department.capacity == 48

    template_path = os.path.join(os.path.dirname(__file__), "templates", "dir_structure.html")
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()
    department_form = content.split('action="{{ url_for(\'dir_department_new\') }}"', 1)[1]
    department_form = department_form.split("</form>", 1)[0]
    assert 'name="capacity"' not in department_form
    print("DEPARTMENT_CAPACITY_REMOVAL_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
