import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Course, User


def login(client, username, password):
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code in (302, 303), (username, response.status_code)


def check_page(client, path, marker):
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code)
    if marker:
        assert marker.encode("utf-8") in response.data, path


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        teacher = User.query.filter_by(username="demo.aca").first()
        assert teacher and teacher.teacher_profile
        course = Course.query.filter_by(teacher_id=teacher.teacher_profile.id).first()
        assert course
        course_id = course.id

    with app.test_client() as client:
        login(client, "proviseur1", "Direction@2026")
        check_page(client, "/annonces", "Annonces")
        check_page(client, "/messages", "Messagerie")

        client.get("/logout")
        login(client, "censeur.stt", "CenseurSTT@2026")
        check_page(client, "/censeur/emplois-du-temps", "Emplois du temps")

        client.get("/logout")
        login(client, "surveillant.stt", "SurveilSTT@2026")
        check_page(client, "/censeur/absences", "Absences")

        client.get("/logout")
        login(client, "demo.aca", "Demo@2026")
        check_page(client, f"/enseignant/notes/{course_id}", "Notes")

        client.get("/logout")
        login(client, "demo.eleve", "Demo@2026")
        check_page(client, "/eleve/notes", None)
        check_page(client, "/eleve/absences", None)
    print("MODULE_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
