import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Attendance, Course, Department, Grade, SchoolClass, Section, Student, Subject, Teacher, User, db
from utils import dashboard_alerts


def make_user(username, role, full_name):
    user = User(username=username, role=role, full_name=full_name)
    user.set_password("TestMotDePasse#2026")
    db.session.add(user); db.session.flush()
    return user


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        section = Section(name="Section test", code="TST")
        db.session.add(section); db.session.flush()
        department = Department(name="Filière test", code="FT", section_id=section.id)
        db.session.add(department); db.session.flush()
        school_class = SchoolClass(name="1A FT", level="1A", department_id=department.id)
        db.session.add(school_class); db.session.flush()
        subject = Subject(name="Mathématiques", coefficient=2, department_id=department.id)
        db.session.add(subject); db.session.flush()
        teacher_user = make_user("teacher.test", "enseignant", "Teacher Test")
        teacher = Teacher(user_id=teacher_user.id, department_id=department.id, specialty="Maths")
        db.session.add(teacher); db.session.flush()
        student_user = make_user("student.test", "eleve", "Student Test")
        student = Student(user_id=student_user.id, matricule="TEST-001", first_name="Student", last_name="Test",
                          class_id=school_class.id)
        db.session.add(student); db.session.flush()
        course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
        db.session.add(course); db.session.flush()
        for offset in (1, 5, 12):
            db.session.add(Attendance(student_id=student.id, course_id=course.id,
                                      date=date.today() - timedelta(days=offset), type="Absence"))
        db.session.commit()

        titles = {alert[2] for alert in dashboard_alerts()}
        assert "Absences" in titles
        assert "Évaluations" in titles
        db.session.add(Grade(student_id=student.id, course_id=course.id, value=14, max_value=20))
        db.session.commit()
        titles_after_grade = {alert[2] for alert in dashboard_alerts()}
        assert "Absences" in titles_after_grade
        assert "Évaluations" not in titles_after_grade
    print("ALERT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
