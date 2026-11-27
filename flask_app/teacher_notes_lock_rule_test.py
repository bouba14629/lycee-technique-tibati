import os
from datetime import date, datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-teacher-notes-lock-rule.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

from app import app
from enseignant_routes import (_notify_teacher_before_notes_lock, _teacher_grade_locked,
                               _teacher_notes_open, _teacher_notes_status)
from models import (Course, Department, Grade, Notification, SchoolClass, Section,
                    Student, Subject, Teacher, TeacherIndicator, User, db)


with app.app_context():
    db.drop_all()
    db.create_all()

    section = Section(name="Section verrouillage", code="LOCK")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Département verrouillage", code="LOCK", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Classe verrouillage", code="LOCK-1", level="Test", department_id=department.id)
    subject = Subject(name="Matière verrouillage", department_id=department.id)
    user = User(username="teacher-lock-test", full_name="Teacher Lock Test", role="enseignant", active=True)
    user.set_password("Test#2026")
    db.session.add_all([school_class, subject, user])
    db.session.flush()
    teacher = Teacher(user_id=user.id, department_id=department.id)
    db.session.add(teacher)
    db.session.flush()
    course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
    student = Student(class_id=school_class.id, matricule="LOCK-001", first_name="Test", last_name="Élève")
    db.session.add_all([course, student])
    db.session.commit()

    assert _teacher_notes_open(teacher, course, "Trimestre 1") is False

    grade = Grade(value=12, type="Évaluation", sequence=1, term="Trimestre 1",
                  date=date.today(), student_id=student.id, course_id=course.id)
    db.session.add(grade)
    indicator = TeacherIndicator(
        teacher_id=teacher.id, course_id=course.id, term="Trimestre 1",
        hours_due=22, hours_done=0, lessons_planned=0, lessons_done=0,
        digital_lessons_planned=0, digital_lessons_done=0, tp_planned=0,
        tp_done=0, digital_tp_planned=0, digital_tp_done=0,
        updated_at=datetime.utcnow() + timedelta(seconds=1),
    )
    db.session.add(indicator)
    db.session.commit()

    # Un seul indicateur enregistré suffit, même si tous les autres valent zéro.
    assert _teacher_notes_open(teacher, course, "Trimestre 1") is True
    assert _teacher_grade_locked(grade) is False
    status = _teacher_notes_status(teacher, course, "Trimestre 1")
    assert status["opening_date"] == date.today()
    assert status["expiration_date"] == date.today() + timedelta(days=5)

    grade.date = date.today() - timedelta(days=4)
    db.session.commit()
    status = _teacher_notes_status(teacher, course, "Trimestre 1")
    assert status["expiration_date"] == date.today() + timedelta(days=5)
    assert status["open"] is True
    # L’évaluation non renseignée reste donc saisissable malgré cette note ancienne.
    indicator.updated_at = datetime.utcnow() - timedelta(days=4)
    db.session.commit()
    status = _teacher_notes_status(teacher, course, "Trimestre 1")
    assert status["expiration_date"] == date.today() + timedelta(days=1)
    assert _notify_teacher_before_notes_lock(teacher, course, "Trimestre 1", status) is True
    db.session.commit()
    assert Notification.query.filter_by(user_id=teacher.user_id).count() == 1
    assert _notify_teacher_before_notes_lock(teacher, course, "Trimestre 1", status) is False

    indicator.updated_at = datetime.utcnow() - timedelta(days=5)
    grade.date = date.today() - timedelta(days=5)
    db.session.commit()
    assert _teacher_grade_locked(grade) is True
    assert _teacher_notes_open(teacher, course, "Trimestre 1") is False

print("TEACHER_NOTES_LOCK_RULE_TEST_OK")
