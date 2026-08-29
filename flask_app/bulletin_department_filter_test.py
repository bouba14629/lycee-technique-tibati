import os
import re
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-bulletin-department-filter.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Department, SchoolClass, Section, User, db


def set_session(client, user):
    user.session_token = f"bulletin-filter-session-{user.id}"
    db.session.commit()
    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["role"] = user.role
        session["name"] = user.full_name
        session["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.filtre", full_name="Proviseur Filtre", role="directeur", active=True)
    director.set_password("MotDePasseTest#2026")
    section = Section(name="Section test", code="TEST")
    db.session.add_all([director, section])
    db.session.flush()
    electricity = Department(name="Électricité", code="ELEQ", section_id=section.id)
    mechanics = Department(name="Mécanique automobile", code="MA", section_id=section.id)
    db.session.add_all([electricity, mechanics])
    db.session.flush()
    electric_class = SchoolClass(name="2nde ELEQ", level="2nde", department_id=electricity.id)
    mechanic_class = SchoolClass(name="2nde MA", level="2nde", department_id=mechanics.id)
    db.session.add_all([electric_class, mechanic_class])
    db.session.commit()

    client = app.test_client()
    set_session(client, director)

    filtered = client.get(f"/censeur/bulletins?department_id={electricity.id}")
    assert filtered.status_code == 200
    class_select = re.search(rb'<select id="bulletinClassFilter".*?</select>', filtered.data, re.DOTALL)
    assert class_select
    assert b"2nde ELEQ" in class_select.group(0)
    assert b"2nde MA" not in class_select.group(0)
    assert b"bulletinClassData" in filtered.data
    with open("/tmp/ltt-bulletin-filter-preview.html", "wb") as preview_file:
        preview_file.write(filtered.data)

    selected = client.get(f"/censeur/bulletins?department_id={electricity.id}&class_id={electric_class.id}")
    assert selected.status_code == 200
    assert b'option value="1" selected' in selected.data

    inferred = client.get(f"/censeur/bulletins?class_id={mechanic_class.id}")
    assert inferred.status_code == 200
    assert f'value="{mechanics.id}" selected'.encode() in inferred.data

    mismatch = client.get(f"/censeur/bulletins?department_id={electricity.id}&class_id={mechanic_class.id}")
    assert mismatch.status_code == 400

print("BULLETIN_DEPARTMENT_FILTER_TEST_OK")
