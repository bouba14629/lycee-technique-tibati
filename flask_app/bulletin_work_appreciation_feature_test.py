import os
import sys
from io import BytesIO

from pypdf import PdfReader

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-bulletin-work-appreciation.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils", "directeur_routes", "import_routes"}]:
    del sys.modules[module_name]

from app import app
from models import (BulletinWorkAppreciation, Course, Department, Grade, ScheduleEntry, SchoolClass,
                    Section, Student, Subject, Teacher, User, db)
from utils import bulletin_data
from pdf_utils import render_pdf


with app.app_context():
    assert db.engine.url.drivername == "sqlite" and db.engine.url.database == "/tmp/ltt-bulletin-work-appreciation.sqlite"
    db.drop_all()
    db.create_all()
    censeur_user = User(username="censeur.appreciation", full_name="Censeur Test", role="censeur", active=True)
    teacher_user = User(username="enseignant.appreciation", full_name="Enseignant Test", role="enseignant", active=True)
    censeur_user.set_password("Test#2026")
    teacher_user.set_password("Test#2026")
    db.session.add_all([censeur_user, teacher_user])
    db.session.flush()
    section = Section(name="Section Test", code="TST")
    db.session.add(section)
    db.session.flush()
    department = Department(name="Filière Test", code="FT", section_id=section.id)
    db.session.add(department)
    db.session.flush()
    school_class = SchoolClass(name="Classe Test", level="1A", department_id=department.id)
    teacher = Teacher(user_id=teacher_user.id, department_id=department.id)
    db.session.add_all([school_class, teacher])
    db.session.flush()
    student = Student(first_name="Amina", last_name="Test", matricule="APP-001", sex="F", class_id=school_class.id, status="Inscrit")
    general_subject = Subject(name="Mathématiques", coefficient=2, category="Enseignements Généraux", department_id=department.id)
    professional_subject = Subject(name="Électronique", coefficient=2, category="Enseignements Professionnels Théoriques", department_id=department.id)
    db.session.add_all([student, general_subject, professional_subject])
    db.session.flush()
    general_course = Course(subject_id=general_subject.id, teacher_id=teacher.id, class_id=school_class.id)
    professional_course = Course(subject_id=professional_subject.id, teacher_id=teacher.id, class_id=school_class.id)
    db.session.add_all([general_course, professional_course])
    db.session.flush()
    db.session.add_all([
        ScheduleEntry(course_id=general_course.id, day="Lundi", start_time="07:30", end_time="08:20", published=True),
        ScheduleEntry(course_id=professional_course.id, day="Mardi", start_time="07:30", end_time="08:20", published=True),
    ])
    db.session.add_all([
        Grade(value=8, student_id=student.id, course_id=general_course.id, term="Trimestre 1", sequence=1, type="Évaluation"),
        Grade(value=12, student_id=student.id, course_id=professional_course.id, term="Trimestre 1", sequence=1, type="Évaluation"),
    ])
    db.session.commit()

    data = bulletin_data(student, "Trimestre 1")
    assert data["automatic_work_appreciation"] == ""
    assert data["work_appreciation"] == ""
    initial_overall_avg = data["overall_avg"]

    Grade.query.filter_by(student_id=student.id, course_id=professional_course.id, term="Trimestre 1").one().value = 7
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    assert data["automatic_work_appreciation"] == ""
    assert data["work_appreciation"] == ""
    assert data["overall_avg"] != initial_overall_avg
    assert [grade.value for grade in Grade.query.filter_by(student_id=student.id).order_by(Grade.id)] == [8, 7]

    # Même bloc scolaire élargi et même appréciation vide dans les deux modèles PDF.
    school_class.name = "TERMINALE ESF"
    school_class.homeroom_teacher_id = teacher.id
    teacher_user.full_name = "DJIMDO ALI"
    teacher_user.civility = "Mme."
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    grade_values = [grade.value for grade in Grade.query.filter_by(student_id=student.id).order_by(Grade.id)]
    header = "Professeur Principal : Mme. DJIMDO ALI"
    with app.test_request_context("/"):
        common = dict(school_year="2026-2027", term="Trimestre 1", term_ordinal="PREMIER",
                      TERM_SEQ_A=1, TERM_SEQ_B=2, approval=None, student_photo_path=None,
                      photo_available=False, bulletin_ref="APP-001-T1")
        solo = render_pdf("pdf/bulletin_pdf.html", student=student, data=data, **common)
        grouped = render_pdf("pdf/class_bulletins_pdf.html", students_data=[dict(student=student, data=data,
                             photo_path=None, photo_available=False, bulletin_ref="APP-001-T1")], **common)
        texts = []
        for pdf in (solo, grouped):
            assert pdf is not None
            reader = PdfReader(BytesIO(pdf.getvalue()))
            assert len(reader.pages) == 1
            text = reader.pages[0].extract_text()
            assert any(header in line for line in text.splitlines()), text
            assert "APPRÉCIATION DU TRAVAIL DE L'ÉLÈVE" in " ".join(text.split())
            assert "effort s" not in text and "en cet enseignement" not in text
            texts.append(text)
        assert texts[0] == texts[1], "Le modèle individuel et le modèle groupé divergent"
    assert grade_values == [grade.value for grade in Grade.query.filter_by(student_id=student.id).order_by(Grade.id)]
    print("BULLETIN_HEADER_SINGLE_LINE_AND_GROUPED_PARITY_OK")

    db.session.add(BulletinWorkAppreciation(student_id=student.id, term="Trimestre 1", updated_by_id=censeur_user.id,
                                             content="Le Censeur a ajouté son appréciation."))
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    assert data["automatic_work_appreciation"] == ""
    assert data["work_appreciation"] == "Le Censeur a ajouté son appréciation."
    assert data["overall_avg"] != initial_overall_avg
    with app.test_request_context("/"):
        pdf = render_pdf("pdf/bulletin_pdf.html", student=student, data=data, **common)
        text = PdfReader(BytesIO(pdf.getvalue())).pages[0].extract_text()
        assert "Le Censeur a ajouté son appréciation." in " ".join(text.split())

print("BULLETIN_WORK_APPRECIATION_FEATURE_TEST_OK")
