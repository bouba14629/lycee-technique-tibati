import os

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-counselor-indicator-all-classes.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

from app import app
from models import (Course, Department, ScheduleEntry, SchoolClass, Section, Subject,
                    Teacher, TeacherIndicator, User, db)


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

    counselor_user = add_user("conseiller.classes", "Conseiller Toutes Classes", "conseiller_orientation")
    chief_user = add_user("chef.orientation", "Chef Orientation", "chef_orientation")
    teacher_user = add_user("enseignant.standard", "Enseignant Standard", "enseignant")

    section = Section(name="Section Test", code="TEST")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Département Test", code="DT", section_id=section.id)
    db.session.add(department)
    db.session.flush()

    class_with_schedule = SchoolClass(name="Première Test", code="1TEST", level="1ère", department_id=department.id)
    class_without_schedule = SchoolClass(name="Terminale Test", code="TTEST", level="Tle", department_id=department.id)
    orientation = Subject(name="Orientation Scolaire", department_id=department.id)
    mathematics = Subject(name="Mathématiques", department_id=department.id)
    counselor = Teacher(user_id=counselor_user.id, department_id=department.id, specialty="Orientation Scolaire")
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id, specialty="Mathématiques")
    db.session.add_all([class_with_schedule, class_without_schedule, orientation, mathematics, counselor, teacher])
    db.session.flush()

    scheduled_orientation_course = Course(subject_id=orientation.id, teacher_id=counselor.id,
                                          class_id=class_with_schedule.id)
    standard_course = Course(subject_id=mathematics.id, teacher_id=teacher.id,
                             class_id=class_with_schedule.id)
    db.session.add_all([scheduled_orientation_course, standard_course])
    db.session.flush()
    db.session.add_all([
        ScheduleEntry(course_id=scheduled_orientation_course.id, day="Lundi", start_time="07:30", end_time="08:20", published=True),
        ScheduleEntry(course_id=standard_course.id, day="Mardi", start_time="07:30", end_time="08:20", published=True),
    ])
    db.session.commit()

    with app.test_client() as client:
        switch_user(client, counselor_user)
        form = client.get("/enseignant/indicateurs")
        assert form.status_code == 200
        assert b"1TEST" in form.data and b"TTEST" in form.data

        unscheduled_form = client.get(f"/enseignant/indicateurs?class_id={class_without_schedule.id}")
        assert unscheduled_form.status_code == 200
        assert b'<option value="36"' in unscheduled_form.data
        assert b'Toutes les classes de l\'\xc3\xa9tablissement sont propos\xc3\xa9es' not in unscheduled_form.data
        assert Course.query.filter_by(teacher_id=counselor.id, class_id=class_without_schedule.id).count() == 0

        save = client.post("/enseignant/indicateurs", data={
            "class_id": class_without_schedule.id,
            "hours_due": 36,
            "hours_done": 12,
            "lessons_planned": 10,
            "lessons_done": 4,
            "digital_lessons_planned": 0,
            "digital_lessons_done": 0,
            "tp_planned": 8,
            "tp_done": 3,
            "observations": "Suivi de la classe sans créneau personnel.",
        }, follow_redirects=True)
        assert save.status_code == 200
        assert "Indicateurs pédagogiques enregistrés.".encode() in save.data
        indicator_course = Course.query.filter_by(teacher_id=counselor.id, class_id=class_without_schedule.id).one()
        assert indicator_course.subject.name == "Orientation Scolaire"
        assert not indicator_course.schedule_entries
        indicator = TeacherIndicator.query.filter_by(course_id=indicator_course.id, teacher_id=counselor.id).one()
        assert indicator.hours_due == 36 and indicator.observations.startswith("Suivi")

        switch_user(client, chief_user)
        chief_summary = client.get("/censeur/indicateurs")
        assert chief_summary.status_code == 200
        assert b"TTEST" in chief_summary.data

        switch_user(client, teacher_user)
        teacher_form = client.get(f"/enseignant/indicateurs?course_id={standard_course.id}")
        assert teacher_form.status_code == 200
        assert b'<option value="36"' not in teacher_form.data

    db.drop_all()

print("COUNSELOR_INDICATOR_ALL_CLASSES_FEATURE_TEST_OK")
