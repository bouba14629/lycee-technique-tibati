import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-subject-scope.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils", "directeur_routes", "censeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import Department, SchoolClass, Section, Subject, Teacher, User, db


def user(username, role):
    item = User(username=username, full_name=username, role=role, active=True)
    item.set_password("Test#2026")
    return item


with app.app_context():
    db.drop_all()
    db.create_all()
    director = user("proviseur.scope", "directeur")
    censeur = user("censeur.scope", "censeur")
    teacher_user = user("enseignant.scope", "enseignant")
    section = Section(name="Section Test", code="TST")
    db.session.add_all([director, censeur, teacher_user, section])
    db.session.flush()
    department = Department(name="Filière Test", code="FT", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    class_a = SchoolClass(name="Classe Alpha", code="ALPHA", level="1A", department_id=department.id)
    class_b = SchoolClass(name="Classe Beta", code="BETA", level="1A", department_id=department.id)
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    db.session.add_all([class_a, class_b, teacher])
    db.session.commit()

    with app.test_client() as client:
        client.post("/login", data={"username": "proviseur.scope", "password": "Test#2026"})
        rejected_filiere = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"filiere:{department.id}", "name": "Mathématiques", "coefficient": 3,
            "category": "Enseignements Généraux",
        })
        assert rejected_filiere.status_code == 403
        assert Subject.query.filter_by(name="Mathématiques").count() == 0

        director_structure = client.get("/directeur/structure")
        assert director_structure.status_code == 200
        assert b"Ajouter une mati\xc3\xa8re" not in director_structure.data

        blocked_director = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"classe:{class_a.id}", "name": "Atelier Alpha", "coefficient": 4,
            "category": "Enseignements Professionnels Pratiques",
        })
        assert blocked_director.status_code == 403
        assert Subject.query.filter_by(name="Atelier Alpha").count() == 0

        client.get("/logout")
        client.post("/login", data={"username": "censeur.scope", "password": "Test#2026"})
        by_class = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"classe:{class_a.id}", "name": "Atelier Alpha", "coefficient": 4,
            "category": "Enseignements Professionnels Pratiques",
        })
        assert by_class.status_code in (302, 303)
        dedicated = Subject.query.filter_by(name="Atelier Alpha").one()
        assert dedicated.department_id == department.id and dedicated.class_id == class_a.id
        assert dedicated.category == "Enseignements G\u00e9n\u00e9raux"

        structure = client.get("/directeur/structure")
        assert structure.status_code == 200
        assert b"Choisir une classe" in structure.data
        assert b"Fili\xc3\xa8re :" not in structure.data
        assert b"Atelier Alpha" in structure.data and b"Classe : Classe Alpha" in structure.data
        assert b"Ajouter une mati\xc3\xa8re" in structure.data
        assert b"G\xc3\xa9rer les classes" not in structure.data
        assert b"Voir les classes" not in structure.data
        assert f'value="classe:{class_a.id}" selected'.encode() in structure.data

        second_subject = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"classe:{class_a.id}", "name": "Sciences Alpha", "coefficient": 2,
            "category": "Enseignements G\u00e9n\u00e9raux",
        })
        assert second_subject.status_code in (302, 303)
        assert Subject.query.filter_by(name="Sciences Alpha", class_id=class_a.id).count() == 1
        structure_after_second_subject = client.get("/directeur/structure")
        assert f'value="classe:{class_a.id}" selected'.encode() in structure_after_second_subject.data

        class_a_schedule = client.get(f"/censeur/emplois-du-temps?class_id={class_a.id}")
        assert class_a_schedule.status_code == 200
        assert b"Atelier Alpha" in class_a_schedule.data
        class_b_schedule = client.get(f"/censeur/emplois-du-temps?class_id={class_b.id}")
        assert class_b_schedule.status_code == 200
        assert b"Atelier Alpha" not in class_b_schedule.data

print("SUBJECT_SCOPE_FEATURE_TEST_OK")
