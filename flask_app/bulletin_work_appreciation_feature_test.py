import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-bulletin-work-appreciation.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_INITIAL_ADMIN_PASSWORD"] = "FoundateurTest#2026"

for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils", "directeur_routes", "import_routes"}]:
    del sys.modules[module_name]

from app import app
from models import (BulletinWorkAppreciation, Course, Department, Grade, SchoolClass,
                    Section, Student, Subject, Teacher, User, db)
from utils import bulletin_data


with app.app_context():
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
        Grade(value=8, student_id=student.id, course_id=general_course.id, term="Trimestre 1", sequence=1, type="Évaluation"),
        Grade(value=12, student_id=student.id, course_id=professional_course.id, term="Trimestre 1", sequence=1, type="Évaluation"),
    ])
    db.session.commit()

    data = bulletin_data(student, "Trimestre 1")
    assert data["automatic_work_appreciation"] == "Un effort s’impose en cet enseignement."
    assert data["work_appreciation"] == "Un effort s’impose en cet enseignement."

    Grade.query.filter_by(student_id=student.id, course_id=professional_course.id, term="Trimestre 1").one().value = 7
    db.session.commit()
    data = bulletin_data(student, "Trimestre 1")
    assert data["automatic_work_appreciation"] == "Un effort s’impose en tout."

    db.session.add(BulletinWorkAppreciation(student_id=student.id, term="Trimestre 1", updated_by_id=censeur_user.id,
                                             content="Le Censeur a ajouté son appréciation."))
    db.session.commit()
    assert bulletin_data(student, "Trimestre 1")["work_appreciation"] == "Le Censeur a ajouté son appréciation."

print("BULLETIN_WORK_APPRECIATION_FEATURE_TEST_OK")
