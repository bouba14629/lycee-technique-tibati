import os

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-student-class-filter-return.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

from app import app
from models import Department, SchoolClass, Section, Student, User, db


def add_user(username, full_name, role):
    user = User(username=username, full_name=full_name, role=role, active=True)
    user.set_password("Test#2026")
    db.session.add(user)
    db.session.flush()
    return user


def switch_user(client, user):
    user.session_token = f"test-session-{user.id}"
    db.session.commit()
    with client.session_transaction() as session:
        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["session_token"] = user.session_token


with app.app_context():
    db.drop_all()
    db.create_all()

    director = add_user("proviseur.retour", "Proviseur Retour Classe", "directeur")
    student_user = add_user("eleve.modifier", "Amina Alpha", "eleve")
    deleted_user = add_user("eleve.supprimer", "Binta Beta", "eleve")
    other_user = add_user("eleve.autre", "Charlie Gamma", "eleve")

    section = Section(name="Section Retour", code="RET")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Département Retour", code="DR", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    selected_class = SchoolClass(name="Classe Sélectionnée", code="SEL", level="Test", department_id=department.id)
    other_class = SchoolClass(name="Autre Classe", code="AUT", level="Test", department_id=department.id)
    db.session.add_all([selected_class, other_class])
    db.session.flush()

    edited_student = Student(user_id=student_user.id, matricule="RET-001", first_name="Amina", last_name="Alpha",
                             sex="F", class_id=selected_class.id, status="Inscrit")
    deleted_student = Student(user_id=deleted_user.id, matricule="RET-002", first_name="Binta", last_name="Beta",
                              sex="F", class_id=selected_class.id, status="Inscrit")
    other_student = Student(user_id=other_user.id, matricule="RET-003", first_name="Charlie", last_name="Gamma",
                            sex="M", class_id=other_class.id, status="Inscrit")
    db.session.add_all([edited_student, deleted_student, other_student])
    db.session.commit()

    edited_id = edited_student.id
    deleted_id = deleted_student.id
    selected_class_id = selected_class.id
    other_class_id = other_class.id

    with app.test_client() as client:
        switch_user(client, director)

        filtered_list = client.get(f"/eleves?class_id={selected_class_id}")
        assert filtered_list.status_code == 200
        assert f"/eleves/{edited_id}?return_class_id={selected_class_id}".encode() in filtered_list.data
        assert b"Amina Alpha" in filtered_list.data and b"Charlie Gamma" not in filtered_list.data

        detail = client.get(f"/eleves/{edited_id}?return_class_id={selected_class_id}")
        assert detail.status_code == 200
        assert f'name="return_class_id" value="{selected_class_id}"'.encode() in detail.data
        assert f"/eleves/{edited_id}/supprimer?return_class_id={selected_class_id}".encode() in detail.data

        edited = client.post(f"/eleves/{edited_id}/modifier", data={
            "return_class_id": selected_class_id,
            "first_name": "Aminata",
            "last_name": "Alpha",
            "matricule": "RET-001",
            "sex": "F",
            "dob": "",
            "birth_place": "Tibati",
            "class_id": other_class_id,
        }, follow_redirects=False)
        assert edited.status_code in (302, 303)
        assert edited.headers["Location"].endswith(f"/eleves?class_id={selected_class_id}")
        assert db.session.get(Student, edited_id).class_id == other_class_id

        deleted = client.get(
            f"/eleves/{deleted_id}/supprimer?return_class_id={selected_class_id}",
            follow_redirects=False,
        )
        assert deleted.status_code in (302, 303)
        assert deleted.headers["Location"].endswith(f"/eleves?class_id={selected_class_id}")
        assert db.session.get(Student, deleted_id) is None

    db.drop_all()

print("STUDENT_CLASS_FILTER_RETURN_FEATURE_TEST_OK")
