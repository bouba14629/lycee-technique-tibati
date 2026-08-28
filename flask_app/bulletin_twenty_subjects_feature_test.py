import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

from app import app
from flask import render_template
from models import BulletinApproval, Course, Department, Grade, SchoolClass, Section, Student, Subject, Teacher, User, db
from pdf_utils import render_pdf
from utils import annual_bulletin_data, bulletin_data


assert 'subtitle2">Section' not in Path("templates/pdf/_bulletin_body.html").read_text(encoding="utf-8")
assert "VISA DU PROVISEUR" in Path("templates/pdf/_bulletin_body.html").read_text(encoding="utf-8")
assert 'height:42pt' in Path("templates/pdf/_bulletin_body.html").read_text(encoding="utf-8")
assert 'class="student-photo"' in Path("templates/pdf/bulletin_annual_pdf.html").read_text(encoding="utf-8")
assert 'class="photo-frame"' in Path("templates/pdf/bulletin_annual_pdf.html").read_text(encoding="utf-8")


def user(username, role):
    item = User(username=username, full_name=username, role=role, active=True)
    item.set_password("Test#2026")
    db.session.add(item)
    db.session.flush()
    return item


with app.app_context():
    db.drop_all()
    db.create_all()
    section = Section(name="Section Industrielle", code="IND")
    db.session.add(section); db.session.flush()
    department = Department(name="Simulation dense", code="SIM", section_id=section.id)
    db.session.add(department); db.session.flush()
    school_class = SchoolClass(name="Tle SIM", level="Tle", department_id=department.id)
    teacher_user = user("enseignant.simulation", "enseignant")
    student_user = user("eleve.simulation", "eleve")
    peer_user = user("eleve.comparaison", "eleve")
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    student = Student(user_id=student_user.id, matricule="SIM-020", first_name="Élève", last_name="Simulation")
    peer = Student(user_id=peer_user.id, matricule="SIM-021", first_name="Élève", last_name="Comparaison")
    db.session.add_all([school_class, teacher, student, peer]); db.session.flush()
    student.class_id = school_class.id
    peer.class_id = school_class.id
    for index in range(1, 21):
        subject = Subject(name=f"Matière {index:02d}", coefficient=1 + (index % 3), category="Enseignements Généraux", department_id=department.id)
        db.session.add(subject); db.session.flush()
        course = Course(subject_id=subject.id, teacher_id=teacher.id, class_id=school_class.id)
        db.session.add(course); db.session.flush()
        db.session.add(Grade(value=10 + (index % 8), student_id=student.id, course_id=course.id, term="Trimestre 1", sequence=1, type="Évaluation"))
        db.session.add(Grade(value=7 + (index % 4), student_id=peer.id, course_id=course.id, term="Trimestre 1", sequence=1, type="Évaluation"))
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    assert sum(len(category["rows"]) for category in data["categories"]) == 20
    with app.test_request_context("/"):
        pdf = render_pdf("pdf/bulletin_pdf.html", student=student, data=data, term="Trimestre 1", school_year="2025-2026")
    assert pdf and pdf.getvalue().startswith(b"%PDF")
    with open("/tmp/ltt-bulletin-twenty-subjects.pdf", "wb") as output:
        output.write(pdf.getvalue())
    annual = annual_bulletin_data(student)
    assert annual and sum(len(category["rows"]) for category in annual["categories"]) == 20
    assert all(row["rank"] == 1 for category in annual["categories"] for row in category["rows"])
    annual_approval = BulletinApproval(class_id=school_class.id, term="Annuel", status="Validé", validated_by_id=teacher_user.id, validated_at=datetime.utcnow())
    db.session.add(annual_approval); db.session.commit()
    with app.test_request_context("/"):
        annual_preview = render_template("bulletin_annual_preview.html", student=student, data=annual,
                                         school_year="2025-2026", pdf_url="#", preview_pdf_url="#", approval=annual_approval)
    assert "Prévisualisation avant impression" in annual_preview and "Validé numériquement" in annual_preview
    with app.test_request_context("/"):
        annual_pdf = render_pdf("pdf/bulletin_annual_pdf.html", student=student, data=annual, school_year="2025-2026", approval=annual_approval)
    assert annual_pdf and annual_pdf.getvalue().startswith(b"%PDF")
    with open("/tmp/ltt-bulletin-annual-twenty-subjects.pdf", "wb") as output:
        output.write(annual_pdf.getvalue())

print("BULLETIN_TWENTY_SUBJECTS_FEATURE_TEST_OK")
