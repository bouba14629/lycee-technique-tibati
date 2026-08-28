import os
from datetime import date

os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from censeur_routes import _absence_hours
from excel_utils import absence_hours_workbook
from models import Attendance, Course, Department, SchoolClass, Section, Student, Subject, Teacher, User, db
from pdf_utils import render_pdf


with app.app_context():
    db.drop_all(); db.create_all()
    section = Section(name="Industrielle", code="IND"); db.session.add(section); db.session.flush()
    dep = Department(name="Test", code="TST", section_id=section.id); db.session.add(dep); db.session.flush()
    school_class = SchoolClass(name="Tle TST", level="Tle", department_id=dep.id); db.session.add(school_class); db.session.flush()
    teacher_user = User(username="teacher.abs", full_name="Enseignant", role="enseignant", active=True); teacher_user.set_password("Test#2026")
    student_user = User(username="student.abs", full_name="Élève", role="eleve", active=True); student_user.set_password("Test#2026")
    db.session.add_all([teacher_user, student_user]); db.session.flush()
    teacher = Teacher(user_id=teacher_user.id, department_id=dep.id); student = Student(user_id=student_user.id, class_id=school_class.id, matricule="ABS-01", first_name="Élève", last_name="Absent")
    db.session.add_all([teacher, student]); db.session.flush()
    subject = Subject(name="Mathématiques", coefficient=2, department_id=dep.id); db.session.add(subject); db.session.flush()
    course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id); db.session.add(course); db.session.flush()
    db.session.add_all([Attendance(student_id=student.id, course_id=course.id, date=date.today(), start_time="07:30", end_time="09:30", type="Absence"), Attendance(student_id=student.id, course_id=course.id, date=date.today(), start_time="10:00", end_time="11:30", type="Absence")]); db.session.commit()
    assert _absence_hours(student.id) == 3.5
    workbook = absence_hours_workbook(school_class, [{"student": student, "hours": 3.5, "count": 2, "records": Attendance.query.all()}])
    assert workbook.getvalue().startswith(b"PK")
    with app.test_request_context("/"):
        pdf = render_pdf("pdf/absence_class_pdf.html", school_class=school_class,
                         rows=[{"student": student, "hours": 3.5, "count": 2, "records": Attendance.query.all()}])
    assert pdf and pdf.getvalue().startswith(b"%PDF")

print("ABSENCE_EXPORTS_FEATURE_TEST_OK")
