import os
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-bulletin-1astt-restore.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")
from app import app
from flask import render_template
from models import Course, Department, Grade, SchoolClass, Section, Student, Subject, Teacher, User, db
from pdf_utils import render_pdf
from utils import bulletin_data

root = Path(__file__).parent
body = (root / "templates/pdf/_bulletin_body.html").read_text(encoding="utf-8")
individual = (root / "templates/pdf/bulletin_pdf.html").read_text(encoding="utf-8")
grouped = (root / "templates/pdf/class_bulletins_pdf.html").read_text(encoding="utf-8")
assert 'class="institution-header"' in body
assert 'class="institution-logo"' in body
assert 'class="footer-table"' in body
assert '{% include "pdf/_bulletin_body.html" %}' in individual
assert '{% include "pdf/_bulletin_body.html" %}' in grouped
assert 'page-break-before: always' in grouped
assert 'official-bulletin' not in body

def user(username, role):
    item = User(username=username, full_name=username, role=role, active=True)
    item.set_password("Test#2026")
    db.session.add(item)
    db.session.flush()
    return item

with app.app_context():
    db.drop_all(); db.create_all()
    section = Section(name="Section 1ASTT", code="ASTT")
    db.session.add(section); db.session.flush()
    department = Department(name="Filière 1ASTT", code="ASTT", section_id=section.id)
    db.session.add(department); db.session.flush()
    school_class = SchoolClass(name="1A COME", level="1A", department_id=department.id)
    teacher_user = user("enseignant.1astt", "enseignant")
    student_user = user("eleve.1astt", "eleve")
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    db.session.add_all([school_class, teacher]); db.session.flush()
    student = Student(user_id=student_user.id, class_id=school_class.id, matricule="ASTT-001", first_name="Élève", last_name="Test")
    subject = Subject(name="Mathématiques", coefficient=2, category="Enseignements Généraux", department_id=department.id)
    db.session.add_all([student, subject]); db.session.flush()
    course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
    db.session.add(course); db.session.flush()
    db.session.add(Grade(value=14, student_id=student.id, course_id=course.id, term="Trimestre 1", sequence=1, type="Évaluation"))
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    with app.test_request_context("/"):
        pdf = render_pdf("pdf/bulletin_pdf.html", student=student, data=data, term="Trimestre 1", school_year="2025-2026")
        assert pdf.getvalue().startswith(b"%PDF")
        grouped_pdf = render_pdf("pdf/class_bulletins_pdf.html", students_data=[{"student": student, "data": data, "photo_path": None, "bulletin_ref": None}], term="Trimestre 1", school_year="2025-2026")
        assert grouped_pdf.getvalue().startswith(b"%PDF")
        html = render_template("pdf/bulletin_pdf.html", student=student, data=data, term="Trimestre 1", school_year="2025-2026")
        assert "institution-header" in html and "footer-table" in html
    Path("/tmp/ltt-bulletin-1astt-individual.pdf").write_bytes(pdf.getvalue())
    Path("/tmp/ltt-bulletin-1astt-grouped.pdf").write_bytes(grouped_pdf.getvalue())
print("BULLETIN_1ASTT_RESTORE_FEATURE_TEST_OK")
