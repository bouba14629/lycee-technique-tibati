import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-edit-all-classes.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "seed", "utils", "directeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import db, Department, SchoolClass, Section, Student, User

with app.app_context():
    db.drop_all()
    db.create_all()
    director = User(username="proviseur.edit.classes", full_name="Proviseur Test", role="directeur", active=True)
    director.set_password("MotDePasseTest#2026")
    student_user = User(username="eleve.edit.classes", full_name="Amina Alpha", role="eleve", active=True)
    student_user.set_password("MotDePasseTest#2026")
    section = Section(name="Section Classes", code="CLS")
    db.session.add_all([director, student_user, section])
    db.session.flush()
    first_department = Department(name="Premier Département", code="DEP1", section_id=section.id)
    second_department = Department(name="Second Département", code="DEP2", section_id=section.id)
    db.session.add_all([first_department, second_department])
    db.session.flush()
    current_class = SchoolClass(name="Classe Actuelle", code="ACT", level="Test", department_id=first_department.id)
    other_class = SchoolClass(name="Classe Autre Filière", code="AUT", level="Test", department_id=second_department.id)
    db.session.add_all([current_class, other_class])
    db.session.flush()
    student = Student(user_id=student_user.id, matricule="ALL-001", first_name="Amina", last_name="Alpha",
                      sex="F", class_id=current_class.id, status="Inscrit")
    db.session.add(student)
    db.session.commit()

    student_id = student.id
    with app.test_client() as client:
        director.session_token = "test-session-director-all-classes"
        db.session.commit()
        with client.session_transaction() as session:
            session["user_id"] = director.id
            session["role"] = director.role
            session["name"] = director.full_name
            session["session_token"] = director.session_token
        response = client.get(f"/eleves/{student_id}")
        assert response.status_code == 200
        assert f'value="{current_class.id}" selected'.encode() in response.data
        assert f'value="{other_class.id}"'.encode() in response.data
        assert b"Classe Autre Fili\xc3\xa8re" in response.data

print("STUDENT_EDIT_ALL_CLASSES_FEATURE_TEST_OK")
