import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import SchoolClass, Student


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
        student = Student.query.order_by(Student.id).first()
        school_class = SchoolClass.query.order_by(SchoolClass.id).first()
        assert student is not None
        assert school_class is not None
        student_id = student.id
        class_id = school_class.id

    term = quote("Trimestre 1")
    xlsx_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with app.test_client() as client:
        login(client, "proviseur1", "Direction@2026")
        assert_export(client, "/directeur/utilisateurs/export.xlsx", xlsx_type, b"PK")
        assert_export(client, "/eleves/export.xlsx", xlsx_type, b"PK")
        assert_export(client, "/eleves/export.pdf", "application/pdf", b"%PDF")
        client.get("/logout")
        login(client, "censeur.stt", "CenseurSTT@2026")
        assert_export(client, f"/eleves/{student_id}/bulletin/telecharger?term={term}", "application/pdf", b"%PDF")
        assert_export(client, f"/eleves/{student_id}/bulletin/telecharger.xlsx?term={term}", xlsx_type, b"PK")

        assert_export(client, f"/censeur/emplois-du-temps/{class_id}/officiel.pdf", "application/pdf", b"%PDF")
        assert_export(client, f"/censeur/emplois-du-temps/{class_id}/officiel.xlsx", xlsx_type, b"PK")
    print("EXPORT_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
