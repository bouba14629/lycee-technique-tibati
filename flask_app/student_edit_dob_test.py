import os
import sys
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-edit-dob.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User


def set_session(client, user):
    user.session_token = f"test-session-{user.id}"
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = user.role
        sess["name"] = user.full_name
        sess["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.edit", full_name="Proviseur Test", role="directeur", active=True)
    director.set_password("MotDePasseTest#2026")
    student_user = User(username="eleve.edit", full_name="Moussa Oumayatou", role="eleve", active=True)
    student_user.set_password("MotDePasseTest#2026")
    section = Section(name="Industriel", code="IND")
    db.session.add_all([director, student_user, section])
    db.session.flush()
    department = Department(name="Mécanique", code="MEC", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Deuxième année COME", level="Deuxième", department_id=department.id)
    db.session.add(school_class)
    db.session.flush()
    student = Student(
        user_id=student_user.id,
        matricule="EDIT-001",
        first_name="Moussa",
        last_name="Oumayatou",
        dob=date(2012, 1, 1),
        birth_place="Tibati",
        sex="M",
        class_id=school_class.id,
        status="Inscrit",
    )
    db.session.add(student)
    db.session.commit()
    student_id = student.id

    client = app.test_client()
    set_session(client, director)

    response = client.post(
        f"/eleves/{student_id}/modifier",
        data={
            "first_name": "Moussa",
            "last_name": "Oumayatou",
            "matricule": "EDIT-001",
            "sex": "M",
            "dob": "2011-09-14",
            "birth_place": "Tibati",
            "class_id": str(school_class.id),
        },
    )
    assert response.status_code in (302, 303)
    assert db.session.get(Student, student_id).dob == date(2011, 9, 14)

    detail = client.get(f"/eleves/{student_id}")
    assert detail.status_code == 200
    assert b"14/09/2011" in detail.data
    assert b'name="dob"' in detail.data
    assert b'value="2011-09-14"' in detail.data

    invalid = client.post(
        f"/eleves/{student_id}/modifier",
        data={
            "first_name": "Moussa",
            "last_name": "Oumayatou",
            "matricule": "EDIT-001",
            "sex": "M",
            "dob": "14-09-2011",
            "birth_place": "Tibati",
            "class_id": str(school_class.id),
        },
    )
    assert invalid.status_code in (302, 303)
    assert db.session.get(Student, student_id).dob == date(2011, 9, 14)

print("STUDENT_EDIT_DOB_TEST_OK")
