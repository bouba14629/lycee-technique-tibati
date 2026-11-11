"""Tests HTTP isolés : prénom obligatoire, nom facultatif, retrait des points.
Aucune connexion à la base réelle ; les fichiers temporaires sont nettoyés.
"""
import os
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path


class InputFields(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))


def assert_form_fields(html):
    parser = InputFields()
    parser.feed(html)
    firsts = [field for field in parser.inputs if field.get("name") == "first_name"]
    lasts = [field for field in parser.inputs if field.get("name") == "last_name"]
    assert firsts and all("required" in field for field in firsts)
    assert lasts and all("required" not in field for field in lasts)
    assert all("replace(/\\./g" in field.get("oninput", "") for field in lasts)


def main():
    with tempfile.TemporaryDirectory(prefix="ltt-optional-last-name-") as tmp:
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tmp) / "test.sqlite")
        os.environ["LTT_ENV"] = "development"
        os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "IsolatedTest#2026"
        from app import app
        from models import db, User, Section, Department, SchoolClass, Student, Parent

        with app.app_context():
            director = User(username="name-test.director", full_name="Directeur Test", role="directeur", session_token="name-test-token")
            director.set_password("IsolatedTest#2026")
            section = Section(name="Test", code="NAME")
            db.session.add_all([director, section]); db.session.flush()
            department = Department(name="Test", code="NAME", section_id=section.id)
            db.session.add(department); db.session.flush()
            school_class = SchoolClass(name="Classe Test", code="NAME", level="1A", department_id=department.id)
            db.session.add(school_class); db.session.flush()
            linked_user = User(username="existing.identifier.unchanged", full_name="Amina Al.pha", role="eleve", email="test@example.invalid", phone="123", session_token="existing-token")
            linked_user.set_password("PreserveThisPassword#2026")
            db.session.add(linked_user); db.session.flush()
            existing = Student(user_id=linked_user.id, matricule="NAME-EXISTING", first_name="Amina", last_name="Al.pha", class_id=school_class.id, dob=date(2010, 5, 8), birth_place="Tibati", photo="/manus-storage/students/unchanged.png", address="Adresse conservée", sex="F", is_repeater=True)
            untouched = Student(matricule="NAME-UNTOUCHED", first_name="Prénom Conservé", last_name="Nom.Avec.Point", class_id=school_class.id)
            db.session.add_all([existing, untouched]); db.session.commit()
            student_id, user_id, class_id = existing.id, linked_user.id, school_class.id
            credentials = (linked_user.username, linked_user.password_hash, linked_user.plain_password, linked_user.must_change_password, linked_user.session_token, linked_user.active)
            kept_student_data = (existing.matricule, existing.class_id, existing.dob, existing.birth_place, existing.photo, existing.address, existing.sex, existing.is_repeater)
            director_snapshot = (director.username, director.password_hash, director.plain_password)

            def assert_preserved():
                db.session.expire_all()
                student = db.session.get(Student, student_id)
                user = db.session.get(User, user_id)
                assert (user.username, user.password_hash, user.plain_password, user.must_change_password, user.session_token, user.active) == credentials
                assert (student.matricule, student.class_id, student.dob, student.birth_place, student.photo, student.address, student.sex, student.is_repeater) == kept_student_data
                assert db.session.get(Student, untouched.id).last_name == "Nom.Avec.Point"
                assert (director.username, director.password_hash, director.plain_password) == director_snapshot

            with app.test_client() as client:
                with client.session_transaction() as session:
                    session.update(user_id=director.id, role="directeur", session_token=director.session_token)

                for url in ("/eleves/inscription", f"/eleves/{student_id}", "/directeur/utilisateurs?role=eleve"):
                    response = client.get(url)
                    assert response.status_code == 200, (url, response.status_code)
                    assert_form_fields(response.get_data(as_text=True))

                for index, last in enumerate((None, "", ".", "  N.Diaye.  ")):
                    form = {"first_name": "Prénom", "matricule": f"NAME-NEW-{index}", "class_id": class_id, "return_class_id": class_id}
                    if last is not None:
                        form["last_name"] = last
                    response = client.post("/eleves/inscription", data=form)
                    assert response.status_code == 302
                    assert response.headers["Location"].endswith(f"/eleves?class_id={class_id}")
                    new = Student.query.filter_by(matricule=f"NAME-NEW-{index}").one()
                    assert new.first_name == "Prénom"
                    assert new.last_name == ("NDiaye" if index == 3 else "")
                    assert not new.user.full_name.endswith(" ")
                    assert new.user.check_password("0000")
                    assert client.get(f"/eleves/{new.id}").status_code == 200

                count = Student.query.count()
                for first in (None, "", "   "):
                    form = {"matricule": "NAME-REJECT", "last_name": "Nom", "class_id": class_id}
                    if first is not None:
                        form["first_name"] = first
                    response = client.post("/eleves/inscription", data=form)
                    assert response.status_code == 302
                    assert "inscription" in response.headers["Location"]
                    assert Student.query.count() == count

                for last, expected in (("  N.Diaye.  ", "NDiaye"), ("", ""), (".", "")):
                    response = client.post(f"/eleves/{student_id}/modifier", data={
                        "first_name": "Amina", "last_name": last, "is_repeater": "1", "return_class_id": class_id,
                    })
                    assert response.status_code == 302
                    assert response.headers["Location"].endswith(f"/eleves?class_id={class_id}")
                    assert db.session.get(Student, student_id).last_name == expected
                    assert_preserved()

                for endpoint in (f"/eleves/{student_id}/modifier", f"/directeur/utilisateurs/{user_id}/modifier"):
                    for first in ("", "   "):
                        response = client.post(endpoint, data={"first_name": first, "last_name": "Must.not.save", "email": "must-not-save@example.invalid", "new_password": "MustNotSave#2026"})
                        assert response.status_code == 302
                        assert db.session.get(Student, student_id).first_name == "Amina"
                        assert db.session.get(Student, student_id).last_name == ""
                        assert db.session.get(User, user_id).email == "test@example.invalid"
                        assert_preserved()

                for last, expected in (("N.om.", "Nom"), ("", "")):
                    response = client.post(f"/directeur/utilisateurs/{user_id}/modifier", data={"first_name": "Amina", "last_name": last, "role_filter": "eleve"})
                    assert response.status_code == 302
                    assert db.session.get(Student, student_id).last_name == expected
                    assert db.session.get(User, user_id).full_name == ("Amina Nom" if expected else "Amina")
                    assert_preserved()

                # Un POST partiel de modification garde le prénom déjà saisi.
                response = client.post(f"/eleves/{student_id}/modifier", data={"last_name": ".", "is_repeater": "1"})
                assert response.status_code == 302
                assert db.session.get(Student, student_id).first_name == "Amina"
                assert_preserved()

                parent_user = User(username="name-test.parent", full_name="Parent Test", role="parent", session_token="parent-test-token")
                parent_user.set_password("IsolatedParent#2026")
                db.session.add(parent_user); db.session.flush()
                parent = Parent(user_id=parent_user.id)
                parent.children.append(db.session.get(Student, student_id))
                db.session.add(parent); db.session.commit()
                with client.session_transaction() as session:
                    session.clear()
                    session.update(user_id=parent_user.id, role="parent", session_token=parent_user.session_token)
                for url in ("/dashboard", "/parent/enfants"):
                    response = client.get(url)
                    assert response.status_code == 200, (url, response.status_code)
                    assert "Amina" in response.get_data(as_text=True)

            print("STUDENT_OPTIONAL_LAST_NAME_FEATURE_TEST_OK")
            print("HTTP_FORMS_SERVER_VALIDATION_DOT_REMOVAL_AND_EXISTING_CREDENTIALS_PRESERVED_OK")
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    main()
