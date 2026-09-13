import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-subject-protection.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils", "directeur_routes", "censeur_routes"}]:
    del sys.modules[module_name]

from app import app
from models import Course, Department, Room, ScheduleEntry, Section, SchoolClass, Subject, Teacher, User, db


def make_user(username, role):
    item = User(username=username, full_name=username, role=role, active=True)
    item.set_password("Test#2026")
    return item


with app.app_context():
    db.drop_all()
    db.create_all()
    section = Section(name="Section Protection", code="SP")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Filière Protection", code="FP", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Classe Protection", code="FP-1A", level="1A", department_id=department.id)
    other_class = SchoolClass(name="Classe Protection B", code="FP-1B", level="1A", department_id=department.id)
    censeur = make_user("censeur.protection", "censeur")
    teacher_user = make_user("enseignant.protection", "enseignant")
    db.session.add_all([school_class, other_class, censeur, teacher_user])
    db.session.flush()
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    subject = Subject(name="Mathématiques", coefficient=2, category="Enseignements Généraux",
                      department_id=department.id, class_id=school_class.id, is_tronc_commun=False)
    db.session.add_all([teacher, subject])
    db.session.flush()
    course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
    db.session.add(course)
    db.session.flush()
    db.session.add(ScheduleEntry(course_id=course.id, day="Lundi", start_time="07:30", end_time="09:30", published=True))
    db.session.commit()
    subject_id = subject.id

    with app.test_client() as client:
        login = client.post("/login", data={"username": "censeur.protection", "password": "Test#2026"})
        assert login.status_code in (302, 303)

        blocked_delete = client.get(f"/directeur/structure/matiere/{subject_id}/supprimer", follow_redirects=True)
        assert blocked_delete.status_code == 200
        assert b"deja programm" in blocked_delete.data or b"d\xc3\xa9j\xc3\xa0 programm" in blocked_delete.data
        assert Subject.query.get(subject_id) is not None
        assert ScheduleEntry.query.count() == 1

        duplicate = client.post("/directeur/structure/matiere/nouvelle", data={
            "target_scope": f"classe:{school_class.id}",
            "name": " mathematiques ",
            "coefficient": 2,
            "category": "Enseignements Généraux",
        }, follow_redirects=True)
        assert duplicate.status_code == 200
        assert Subject.query.filter_by(class_id=school_class.id).count() == 1
        assert b"Math" in duplicate.data

        duplicate_tronc = client.post("/directeur/structure/matiere/nouvelle", data={
            "creation_mode": "tronc_commun",
            "tronc_class_ids": [str(school_class.id), str(other_class.id)],
            "name": "Mathématiques",
            "coefficient": 2,
            "category": "Enseignements Généraux",
        }, follow_redirects=True)
        assert duplicate_tronc.status_code == 200
        assert Subject.query.filter_by(name="Mathématiques").count() == 1

print("SUBJECT_PROTECTION_FEATURE_TEST_OK")

if __name__ == "__main__":
    pass
