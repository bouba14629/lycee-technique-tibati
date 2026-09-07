import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-subject-tronc.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils", "directeur_routes", "censeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import Department, Room, SchoolClass, Section, Subject, Teacher, User, db


def make_user(username, section_id=None):
    item = User(username=username, full_name=username, role="censeur", active=True, section_id=section_id)
    item.set_password("Test#2026")
    return item


with app.app_context():
    db.drop_all()
    db.create_all()
    section = Section(name="Section Tronc", code="TRC")
    db.session.add(section)
    db.session.flush()
    department_a = Department(name="Filière A", code="A", section_id=section.id)
    department_b = Department(name="Filière B", code="B", section_id=section.id)
    db.session.add_all([department_a, department_b])
    db.session.flush()
    class_a = SchoolClass(name="Première A", code="A-P", level="P", department_id=department_a.id)
    class_b = SchoolClass(name="Première B", code="B-P", level="P", department_id=department_b.id)
    class_other = SchoolClass(name="Terminale A", code="A-T", level="Tle", department_id=department_a.id)
    censeur = make_user("censeur.tronc", section.id)
    teacher_user = User(username="enseignant.tronc", full_name="Enseignant Tronc", role="enseignant", active=True)
    teacher_user.set_password("Test#2026")
    db.session.add_all([class_a, class_b, class_other, censeur, teacher_user])
    db.session.flush()
    teacher = Teacher(user_id=teacher_user.id, department_id=department_a.id, specialty="Communication")
    room = Room(name="Salle Tronc", type="Salle", capacity=60, department_id=department_a.id)
    db.session.add_all([teacher, room])
    db.session.commit()
    class_a_id, class_b_id, class_other_id = class_a.id, class_b.id, class_other.id
    teacher_id, room_id = teacher.id, room.id

    with app.test_client() as client:
        assert client.post("/login", data={"username": "censeur.tronc", "password": "Test#2026"}).status_code in (302, 303)
        created = client.post("/directeur/structure/matiere/nouvelle", data={
            "creation_mode": "tronc_commun", "name": "Communication", "coefficient": 2,
            "category": "Enseignements Généraux", "tronc_class_ids": [str(class_a_id), str(class_b_id)],
        })
        assert created.status_code in (302, 303)
        subjects = Subject.query.filter_by(name="Communication", is_tronc_commun=True).order_by(Subject.class_id).all()
        assert len(subjects) == 2
        assert {subject.class_id for subject in subjects} == {class_a_id, class_b_id}
        assert all(subject.coefficient == 2 for subject in subjects)

        schedule = client.post(f"/censeur/emplois-du-temps?class_id={class_a_id}", data={
            "subject_id": str(subjects[0].id), "teacher_id": str(teacher_id), "room_id": str(room_id),
            "day": "Lundi", "start_time": "08:00", "end_time": "10:00",
            "tronc_commun_class_ids": [str(class_b_id)],
        }, follow_redirects=True)
        assert schedule.status_code == 200
        assert b"Tronc commun" in schedule.data
        assert len(subjects[0].courses) == 1 and len(subjects[1].courses) == 1
        assert len(subjects[0].courses[0].schedule_entries) == 1
        assert len(subjects[1].courses[0].schedule_entries) == 1
        assert subjects[0].courses[0].schedule_entries[0].start_time == subjects[1].courses[0].schedule_entries[0].start_time == "08:00"

        invalid = client.post("/directeur/structure/matiere/nouvelle", data={
            "creation_mode": "tronc_commun", "name": "Communication invalide", "coefficient": 2,
            "category": "Enseignements Généraux", "tronc_class_ids": [str(class_a_id), str(class_other_id)],
        })
        assert invalid.status_code in (302, 303)
        assert Subject.query.filter_by(name="Communication invalide").count() == 0

        structure = client.get("/directeur/structure")
        assert structure.status_code == 200
        assert b"Tronc commun" in structure.data
        assert b"Classes du m\xc3\xaame niveau" in structure.data

print("SUBJECT_TRONC_COMMUN_CREATION_TEST_OK")
