import os
os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-dashboard-500-repro.sqlite"
os.environ["LTT_ENV"] = "development"
from app import app
from models import db, User, Section, Department, SchoolClass, Subject, Teacher, Course, Student, Attendance

app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
with app.app_context():
    db.drop_all()
    db.create_all()
    section = Section(name="Section test", code="TST")
    department = Department(name="Filière test", code="FT", section=section)
    school_class = SchoolClass(name="1A TEST", level="1A", specialty="TEST", department=department)
    subject = Subject(name="Matière test", category="Enseignements Généraux", department=department, class_id=school_class.id)
    users = []
    for role in ("directeur", "censeur", "censeur_crm", "surveillant_general"):
        user = User(username=f"{role}.test", role=role, full_name=role.title(), active=True,
                    section=section if role in ("censeur", "surveillant_general") else None)
        user.set_password("Test#2026")
        users.append(user)
    teacher_user = User(username="enseignant.test", role="enseignant", full_name="Enseignant Test", active=True)
    teacher_user.set_password("Test#2026")
    teacher = Teacher(user=teacher_user, department=department)
    course = Course(subject=subject, teacher=teacher, school_class=school_class)
    student = Student(matricule="TEST-001", first_name="Élève", last_name="Test", school_class=school_class)
    attendance = Attendance(student=student, course=course, type="Absence")
    db.session.add_all([section, department, school_class, subject, *users, teacher_user, teacher, course, student, attendance])
    db.session.commit()

client = app.test_client()
for role in ("directeur", "censeur", "censeur_crm", "surveillant_general"):
    login = client.post("/login", data={"username": f"{role}.test", "password": "Test#2026"}, follow_redirects=False)
    assert login.status_code in (302, 303), (role, login.status_code)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 200, (role, response.status_code, response.data[:500])
    filtered = client.get("/dashboard?attendance_section_id=1&attendance_department_id=1&attendance_class_id=1&attendance_class_id=2&attendance_subject_id=1&attendance_subject_id=2", follow_redirects=False)
    assert filtered.status_code == 200, (role, filtered.status_code, filtered.data[:500])
    client.get("/logout")
print("DASHBOARD_500_REPRODUCTION_OK")
