import os
from datetime import date
from urllib.parse import quote

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:////tmp/ltt-export-smoke.sqlite")
os.environ["LTT_ENV"] = "development"
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app  # noqa: E402
from models import Department, SchoolClass, Section, Student, User, db  # noqa: E402


def assert_export(client, path, expected_type, signature):
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code)
    assert expected_type in response.content_type, (path, response.content_type)
    assert response.data.startswith(signature), path


def login(client, username, password):
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code in (302, 303), response.status_code


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        password = "ExportTest#2026"
        director = User(username="proviseur.export", full_name="Proviseur Export", role="directeur", active=True)
        censeur = User(username="censeur.export", full_name="Censeur Export", role="censeur", active=True)
        student_user = User(username="eleve.export", full_name="Élève Export", role="eleve", active=True)
        for user in (director, censeur, student_user):
            user.set_password(password)
        section = Section(name="Section Export", code="EXP")
        censeur.section = section
        db.session.add_all([director, censeur, student_user, section])
        db.session.flush()
        department = Department(name="Filière Export", code="EXP", section_id=section.id)
        db.session.add(department)
        db.session.flush()
        school_class = SchoolClass(name="Classe Export", code="EXP-1", level="1A", department_id=department.id)
        db.session.add(school_class)
        db.session.flush()
        student = Student(
            user_id=student_user.id,
            matricule="EXP0001",
            first_name="Élève",
            last_name="Export",
            dob=date(2012, 1, 1),
            birth_place="Tibati",
            sex="M",
            class_id=school_class.id,
            status="Inscrit",
        )
        db.session.add(student)
        db.session.commit()
        student_id = student.id
        class_id = school_class.id

    term = quote("Trimestre 1")
    xlsx_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with app.test_client() as client:
        login(client, "proviseur.export", "ExportTest#2026")
        assert_export(client, "/directeur/utilisateurs/export.xlsx", xlsx_type, b"PK")
        assert_export(client, "/eleves/export.xlsx", xlsx_type, b"PK")
        assert_export(client, "/eleves/export.pdf", "application/pdf", b"%PDF")
        client.get("/logout")
        login(client, "censeur.export", "ExportTest#2026")
        assert_export(client, f"/eleves/{student_id}/bulletin/telecharger?term={term}", "application/pdf", b"%PDF")
        assert_export(client, f"/eleves/{student_id}/bulletin/telecharger.xlsx?term={term}", xlsx_type, b"PK")
        assert_export(client, f"/censeur/emplois-du-temps/{class_id}/officiel.pdf", "application/pdf", b"%PDF")
        assert_export(client, f"/censeur/emplois-du-temps/{class_id}/officiel.xlsx", xlsx_type, b"PK")
    print("EXPORT_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
