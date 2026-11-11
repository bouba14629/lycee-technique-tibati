import os
import sys
from pathlib import Path

TEST_DB = Path("/tmp/ltt-class-schedule-consultation.sqlite")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_BOOTSTRAP_MODE"] = "demo"

for module_name in [name for name in list(sys.modules)
                    if name in {"app", "models", "utils", "enseignant_routes", "eleve_routes", "parent_routes"}]:
    del sys.modules[module_name]

sys.path.insert(0, os.path.dirname(__file__))
from app import app  # noqa: E402
from models import (Course, Department, Parent, ScheduleEntry, SchoolClass, Section, Student,
                    Subject, Teacher, User, db)  # noqa: E402


def login(client, username, password):
    response = client.post("/login", data={"username": username, "password": password})
    assert response.status_code == 302
    return response


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()

        section = Section(name="Section test emploi", code="TEST")
        department = Department(name="Département test", code="TST", section=section)
        class_a = SchoolClass(name="Classe A programmée", code="A-PROG", level="2nde", department=department)
        class_b = SchoolClass(name="Classe B sans créneau", code="B-VIDE", level="1ère", department=department)
        class_c = SchoolClass(name="Classe C autre enseignant", code="C-AUTRE", level="Tle", department=department)
        subject_math = Subject(name="Mathématiques test", coefficient=2, department=department)
        subject_french = Subject(name="Français test", coefficient=1, department=department)
        subject_physics = Subject(name="Physique test", coefficient=1, department=department)
        teacher_one_user = User(username="teacher.one.schedule", full_name="Professeur Un", role="enseignant",
                                must_change_password=False, session_token="teacher-one-token")
        teacher_one_user.set_password("TeacherOne#2026")
        teacher_two_user = User(username="teacher.two.schedule", full_name="Professeur Deux", role="enseignant",
                                must_change_password=False, session_token="teacher-two-token")
        teacher_two_user.set_password("TeacherTwo#2026")
        student_user = User(username="student.schedule", full_name="Élève Classe A", role="eleve",
                            must_change_password=False, session_token="student-token")
        student_user.set_password("Student#2026")
        no_class_user = User(username="student.no.class.schedule", full_name="Élève Sans Classe", role="eleve",
                             must_change_password=False, session_token="student-no-class-token")
        no_class_user.set_password("NoClass#2026")
        parent_user = User(username="parent.schedule", full_name="Parent Rattaché", role="parent",
                           must_change_password=False, session_token="parent-token")
        parent_user.set_password("Parent#2026")
        foreign_parent_user = User(username="parent.foreign.schedule", full_name="Parent Étranger", role="parent",
                                   must_change_password=False, session_token="foreign-parent-token")
        foreign_parent_user.set_password("Foreign#2026")
        forbidden_user = User(username="director.schedule.forbidden", full_name="Compte Interdit", role="directeur",
                              must_change_password=False, session_token="forbidden-token")
        forbidden_user.set_password("Forbidden#2026")
        db.session.add_all([section, department, class_a, class_b, class_c,
                            subject_math, subject_french, subject_physics,
                            teacher_one_user, teacher_two_user, student_user, no_class_user,
                            parent_user, foreign_parent_user, forbidden_user])
        db.session.flush()

        teacher_one = Teacher(user_id=teacher_one_user.id, department_id=department.id, specialty="Mathématiques")
        teacher_two = Teacher(user_id=teacher_two_user.id, department_id=department.id, specialty="Français")
        student = Student(user_id=student_user.id, matricule="SCH-A-001", first_name="Élève", last_name="Classe A",
                          class_id=class_a.id)
        second_student = Student(matricule="SCH-C-002", first_name="Élève", last_name="Classe C",
                                 class_id=class_c.id)
        no_class_student = Student(user_id=no_class_user.id, matricule="SCH-NULL-001", first_name="Élève", last_name="Sans Classe")
        parent = Parent(user_id=parent_user.id)
        foreign_parent = Parent(user_id=foreign_parent_user.id)
        parent.children.extend([student, second_student])
        db.session.add_all([teacher_one, teacher_two, student, second_student, no_class_student, parent, foreign_parent])
        db.session.flush()

        own_course = Course(subject_id=subject_math.id, teacher_id=teacher_one.id, class_id=class_a.id)
        peer_course = Course(subject_id=subject_french.id, teacher_id=teacher_two.id, class_id=class_a.id)
        draft_course = Course(subject_id=subject_physics.id, teacher_id=teacher_two.id, class_id=class_a.id)
        unscheduled_course = Course(subject_id=subject_math.id, teacher_id=teacher_one.id, class_id=class_b.id)
        other_course = Course(subject_id=subject_french.id, teacher_id=teacher_two.id, class_id=class_c.id)
        db.session.add_all([own_course, peer_course, draft_course, unscheduled_course, other_course])
        db.session.flush()
        db.session.add_all([
            ScheduleEntry(course_id=own_course.id, day="Lundi", start_time="07:30", end_time="08:20", published=True),
            ScheduleEntry(course_id=peer_course.id, day="Mardi", start_time="08:20", end_time="09:10", published=True),
            ScheduleEntry(course_id=draft_course.id, day="Mercredi", start_time="09:10", end_time="10:00", published=False),
            ScheduleEntry(course_id=other_course.id, day="Jeudi", start_time="10:15", end_time="11:05", published=True),
        ])
        db.session.commit()
        ids = {
            "class_a": class_a.id,
            "class_b": class_b.id,
            "class_c": class_c.id,
            "own_course": own_course.id,
            "peer_course": peer_course.id,
            "other_course": other_course.id,
            "student": student.id,
            "second_student": second_student.id,
            "teacher_one": teacher_one.id,
            "teacher_two": teacher_two.id,
        }
        credentials = {
            user.id: (user.username, user.password_hash, user.plain_password,
                      user.must_change_password, user.active)
            for user in [teacher_one_user, teacher_two_user, student_user, no_class_user,
                         parent_user, foreign_parent_user, forbidden_user]
        }

    with app.test_client() as teacher_client:
        login(teacher_client, "teacher.one.schedule", "TeacherOne#2026")
        class_list = teacher_client.get("/enseignant/emploi-du-temps/classes")
        assert class_list.status_code == 200
        assert b"Classe A programm" in class_list.data
        assert b"Classe B sans cr" not in class_list.data
        assert b"Classe C autre" not in class_list.data
        assert (f"/enseignant/emploi-du-temps/classes/{ids['class_a']}".encode() in class_list.data
                or f"/enseignant/emploi-du-temps/classe/{ids['class_a']}".encode() in class_list.data)

        class_view = teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}")
        assert class_view.status_code == 200
        assert b"Math\xc3\xa9matiques test" in class_view.data
        assert b"Fran\xc3\xa7ais test" in class_view.data
        assert b"Professeur Un" in class_view.data
        assert b"Professeur Deux" in class_view.data
        assert b"Physique test" not in class_view.data
        assert b"Consultation uniquement" in class_view.data
        assert teacher_client.post(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}").status_code == 405
        assert teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_c']}").status_code == 403
        assert teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_b']}").status_code == 403

        # La route individuelle existante est conservée.
        assert teacher_client.get("/enseignant/emploi-du-temps").status_code == 200

    with app.test_client() as parent_client:
        login(parent_client, "parent.schedule", "Parent#2026")
        selector = parent_client.get("/parent/emplois-du-temps")
        assert selector.status_code == 200
        assert b"\xc3\x89l\xc3\xa8ve Classe A" in selector.data
        assert b"\xc3\x89l\xc3\xa8ve Classe C" in selector.data
        child_schedule = parent_client.get(f"/parent/enfant/{ids['student']}/emploi-du-temps")
        assert child_schedule.status_code == 200
        assert b"Math\xc3\xa9matiques test" in child_schedule.data
        assert b"Fran\xc3\xa7ais test" in child_schedule.data
        assert b"Physique test" not in child_schedule.data
        second_child_schedule = parent_client.get(f"/parent/enfant/{ids['second_student']}/emploi-du-temps")
        assert second_child_schedule.status_code == 200
        assert b"Fran\xc3\xa7ais test" in second_child_schedule.data
        assert parent_client.get(f"/parent/enfant/{ids['student']}/emploi-du-temps?class_id={ids['class_c']}").status_code == 200
        assert parent_client.post(f"/parent/enfant/{ids['student']}/emploi-du-temps").status_code == 405

        with app.app_context():
            foreign_student = Student(matricule="SCH-FOREIGN-001", first_name="Enfant", last_name="Étranger", class_id=ids["class_c"])
            db.session.add(foreign_student)
            db.session.commit()
            foreign_student_id = foreign_student.id
        assert parent_client.get(f"/parent/enfant/{foreign_student_id}/emploi-du-temps").status_code == 403

    with app.test_client() as student_client:
        login(student_client, "student.schedule", "Student#2026")
        assert student_client.get("/eleve/emploi-du-temps").status_code == 200
        assert student_client.post("/eleve/emploi-du-temps").status_code == 405

    with app.test_client() as no_class_client:
        login(no_class_client, "student.no.class.schedule", "NoClass#2026")
        assert no_class_client.get("/eleve/emploi-du-temps").status_code == 403

    with app.test_client() as forbidden_client:
        login(forbidden_client, "director.schedule.forbidden", "Forbidden#2026")
        assert forbidden_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}").status_code == 403
        assert forbidden_client.get("/parent/emplois-du-temps").status_code == 403

    with app.app_context():
        # Le changement d'affectation et la programmation est reflété sans cache.
        peer_course = db.session.get(Course, ids["peer_course"])
        peer_course.teacher_id = ids["teacher_one"]
        db.session.add(ScheduleEntry(course_id=peer_course.id, day="Vendredi", start_time="11:05", end_time="11:55", published=True))
        own_course = db.session.get(Course, ids["own_course"])
        own_entries = list(own_course.schedule_entries)
        for entry in own_entries:
            db.session.delete(entry)
        db.session.commit()

    with app.test_client() as teacher_client:
        login(teacher_client, "teacher.one.schedule", "TeacherOne#2026")
        assert teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}").status_code == 200
        # La classe reste autorisée car le cours réaffecté est désormais programmé.
        assert b"Fran\xc3\xa7ais test" in teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}").data
        assert b"Math\xc3\xa9matiques test" not in teacher_client.get(f"/enseignant/emploi-du-temps/classe/{ids['class_a']}").data

    with app.app_context():
        student = db.session.get(Student, ids["student"])
        student.class_id = ids["class_c"]
        db.session.commit()

    with app.test_client() as parent_client:
        login(parent_client, "parent.schedule", "Parent#2026")
        assert parent_client.get("/parent/emplois-du-temps").status_code == 200
        changed_schedule = parent_client.get(f"/parent/enfant/{ids['student']}/emploi-du-temps")
        assert changed_schedule.status_code == 200
        assert b"Fran\xc3\xa7ais test" in changed_schedule.data
        assert b"Math\xc3\xa9matiques test" not in changed_schedule.data

        with app.app_context():
            student = db.session.get(Student, ids["student"])
            parent = db.session.query(Parent).filter_by(user_id=db.session.query(User).filter_by(username="parent.schedule").one().id).one()
            parent.children.remove(student)
            db.session.commit()
        assert parent_client.get(f"/parent/enfant/{ids['student']}/emploi-du-temps").status_code == 403

    with app.app_context():
        for user_id, expected in credentials.items():
            user = db.session.get(User, user_id)
            assert (user.username, user.password_hash, user.plain_password,
                    user.must_change_password, user.active) == expected

    print("CLASS_SCHEDULE_CONSULTATION_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
