import io
import json
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-photo-edit.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"
os.environ["JWT_SECRET"] = "photo-test-secret"
os.environ["PORT"] = "3000"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User
import directeur_routes


class FakeUploadResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"url": "/manus-storage/students/EDIT-PHOTO-001-abc.jpg"}).encode("utf-8")


def set_session(client, user):
    user.session_token = f"photo-session-{user.id}"
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = user.role
        sess["name"] = user.full_name
        sess["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.photo", full_name="Proviseur Photo", role="directeur", active=True)
    director.set_password("MotDePassePhoto#2026")
    student_user = User(username="eleve.photo", full_name="Amina Photo", role="eleve", active=True)
    student_user.set_password("MotDePassePhoto#2026")
    section = Section(name="Industriel", code="IND-PHOTO")
    db.session.add_all([director, student_user, section])
    db.session.flush()
    department = Department(name="Mécanique", code="MEC-PHOTO", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Deuxième année Photo", level="Deuxième", department_id=department.id)
    db.session.add(school_class)
    db.session.flush()
    student = Student(
        user_id=student_user.id,
        matricule="EDIT-PHOTO-001",
        first_name="Amina",
        last_name="Photo",
        sex="F",
        class_id=school_class.id,
        status="Inscrit",
    )
    db.session.add(student)
    db.session.commit()
    student_id = student.id

    client = app.test_client()
    set_session(client, director)

    original_urlopen = directeur_routes.urlopen
    directeur_routes.urlopen = lambda _request, timeout=20: FakeUploadResponse()
    try:
        response = client.post(
            f"/eleves/{student_id}/modifier",
            data={
                "first_name": "Amina",
                "last_name": "Photo",
                "matricule": "EDIT-PHOTO-001",
                "sex": "F",
                "class_id": str(school_class.id),
                "photo": (io.BytesIO(b"fake-jpeg-bytes"), "portrait.JPG"),
            },
            content_type="multipart/form-data",
        )
    finally:
        directeur_routes.urlopen = original_urlopen

    assert response.status_code in (302, 303)
    saved_student = db.session.get(Student, student_id)
    assert saved_student.photo == "/manus-storage/students/EDIT-PHOTO-001-abc.jpg"

    detail = client.get(f"/eleves/{student_id}")
    assert detail.status_code == 200
    assert b"/manus-storage/students/EDIT-PHOTO-001-abc.jpg" in detail.data
    assert b"studentEditPhotoPreview" in detail.data
    assert b"studentEditPhoto" in detail.data

print("STUDENT_PHOTO_EDIT_TEST_OK")
