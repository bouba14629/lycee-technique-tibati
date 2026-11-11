import os
import sys
from pathlib import Path

TEST_DB = Path("/tmp/ltt-annual-bulletin-data-sync.sqlite")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LTT_ENV"] = "development"
os.environ["LTT_BOOTSTRAP_MODE"] = "demo"
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")

# Permet l’exécution isolée après d’autres tests qui auraient déjà importé Flask.
for module_name in [name for name in list(sys.modules) if name in {"app", "models", "utils"}]:
    del sys.modules[module_name]
sys.path.insert(0, os.path.dirname(__file__))

from app import app  # noqa: E402
from models import (  # noqa: E402
    Attendance,
    Course,
    Department,
    Grade,
    ScheduleEntry,
    SchoolClass,
    Section,
    Student,
    Subject,
    Teacher,
    User,
    db,
)
from utils import annual_bulletin_data  # noqa: E402


def add_user(username, full_name, role):
    account = User(username=username, full_name=full_name, role=role, active=True)
    account.set_password("Test#2026")
    db.session.add(account)
    db.session.flush()
    return account


def row_for(data, subject_name):
    return next(
        row
        for category in data["categories"]
        for row in category["rows"]
        if row["course"].subject.name == subject_name
    )


def category_for(data, category_name):
    return next(category for category in data["categories"] if category["name"] == category_name)


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()

        section = Section(name="Section annuelle test", code="ANN")
        department = Department(name="Département annuel test", code="DAT", section=section)
        school_class = SchoolClass(name="3A annuelle", code="3A-ANN", level="3A", department=department)
        teacher_one_user = add_user("teacher.annual.one", "Professeur Un", "enseignant")
        teacher_two_user = add_user("teacher.annual.two", "Professeur Deux", "enseignant")
        student_user = add_user("student.annual.one", "BOUBA BELL BELLO SERGE", "eleve")
        peer_user = add_user("student.annual.peer", "Élève Comparaison", "eleve")
        db.session.add_all([section, department, school_class])
        db.session.flush()

        teacher_one = Teacher(user_id=teacher_one_user.id, department_id=department.id)
        teacher_two = Teacher(user_id=teacher_two_user.id, department_id=department.id)
        student = Student(
            user_id=student_user.id,
            matricule="LTT20262222",
            first_name="BOUBA BELL BELLO",
            last_name="SERGE",
            class_id=school_class.id,
        )
        peer = Student(
            user_id=peer_user.id,
            matricule="ANN-PEER-001",
            first_name="Élève",
            last_name="Comparaison",
            class_id=school_class.id,
        )
        db.session.add_all([teacher_one, teacher_two, student, peer])
        db.session.flush()

        mathematics = Subject(
            name="Mathématiques",
            coefficient=2,
            category="Enseignements Généraux",
            department_id=department.id,
        )
        french = Subject(
            name="Français",
            coefficient=1,
            category="Enseignements Généraux",
            department_id=department.id,
        )
        unscheduled_subject = Subject(
            name="Projet non programmé",
            coefficient=5,
            category="Enseignements Divers",
            department_id=department.id,
        )
        db.session.add_all([mathematics, french, unscheduled_subject])
        db.session.flush()

        math_course = Course(subject_id=mathematics.id, teacher_id=teacher_one.id, class_id=school_class.id)
        french_course = Course(subject_id=french.id, teacher_id=teacher_one.id, class_id=school_class.id)
        unscheduled_course = Course(
            subject_id=unscheduled_subject.id, teacher_id=teacher_one.id, class_id=school_class.id
        )
        db.session.add_all([math_course, french_course, unscheduled_course])
        db.session.flush()
        db.session.add_all([
            ScheduleEntry(course_id=math_course.id, day="Lundi", start_time="07:30", end_time="08:20", published=True),
            ScheduleEntry(course_id=french_course.id, day="Mardi", start_time="07:30", end_time="08:20", published=True),
        ])

        # La note annuelle officielle est la moyenne des notes existantes de chaque trimestre,
        # puis la moyenne des trimestres connus; ce contrôle indépendant donne 14 pour Mathématiques.
        for term, value in zip(("Trimestre 1", "Trimestre 2", "Trimestre 3"), (12, 14, 16)):
            db.session.add(Grade(value=value, student_id=student.id, course_id=math_course.id, term=term, type="Évaluation"))
            db.session.add(Grade(value=11, student_id=peer.id, course_id=math_course.id, term=term, type="Évaluation"))
            db.session.add(Grade(value=13, student_id=peer.id, course_id=french_course.id, term=term, type="Évaluation"))

        # Ces notes ne doivent jamais faire apparaître le cours sans créneau dans le bulletin annuel.
        for term in ("Trimestre 1", "Trimestre 2", "Trimestre 3"):
            db.session.add(Grade(value=20, student_id=student.id, course_id=unscheduled_course.id, term=term, type="Évaluation"))

        # Heures décimales : floor séparément selon la règle d’affichage existante.
        db.session.add_all([
            Attendance(
                student_id=student.id,
                course_id=math_course.id,
                type="Absence",
                justified=True,
                start_time="07:30",
                end_time="09:00",
            ),
            Attendance(
                student_id=student.id,
                course_id=math_course.id,
                type="Absence",
                justified=False,
                start_time="10:00",
                end_time="10:45",
            ),
            Attendance(student_id=student.id, course_id=math_course.id, type="Retard"),
        ])
        db.session.commit()

        first = annual_bulletin_data(student)
        assert [row["course"].subject.name for category in first["categories"] for row in category["rows"]] == [
            "Français",
            "Mathématiques",
        ]
        assert "Projet non programmé" not in [
            row["course"].subject.name for category in first["categories"] for row in category["rows"]
        ]
        math_row = row_for(first, "Mathématiques")
        assert math_row["terms"] == [12.0, 14.0, 16.0]
        assert math_row["annual"] == 14.0
        assert math_row["appreciation"] == "Compétences bien acquises (B+)"
        assert first["overall_avg"] == 14.0
        assert first["term_averages"] == [12.0, 14.0, 16.0]
        assert first["overall_coef"] == 2
        assert first["class_size"] == 2
        assert first["rank"] == 1
        assert first["class_avg"] == 12.84
        assert first["class_high"] == 14.0
        assert first["class_low"] == 11.67
        assert first["absences_justified_hours"] == 1
        assert first["absences_non_justified_hours"] == 0
        # 1 h 30 + 45 min = 2 h 15 ; arrondi après cumul, uniquement au bulletin.
        assert first["total_absence_hours"] == 2
        assert first["absences_total_hours"] == 2
        assert first["absences_justified_days"] == 1
        assert first["absences_non_justified_days"] == 1
        assert first["retards"] == 1
        assert category_for(first, "Enseignements Généraux")["pending_count"] == 1

        old_grade_values = [grade.value for grade in Grade.query.filter_by(student_id=student.id, course_id=math_course.id).all()]
        math_course.teacher_id = teacher_two.id
        db.session.commit()
        after_teacher_change = annual_bulletin_data(student)
        changed_math_row = row_for(after_teacher_change, "Mathématiques")
        assert changed_math_row["teacher"].id == teacher_two.id
        assert [grade.value for grade in Grade.query.filter_by(student_id=student.id, course_id=math_course.id).all()] == old_grade_values
        assert after_teacher_change["overall_avg"] == first["overall_avg"]
        assert after_teacher_change["term_averages"] == first["term_averages"]

        # Les métadonnées de la matière sont lues au prochain appel, sans cache persistant.
        french.name = "Communication"
        french.category = "Enseignements Professionnels Théoriques"
        french.coefficient = 3
        db.session.commit()
        after_subject_change = annual_bulletin_data(student)
        communication_row = row_for(after_subject_change, "Communication")
        assert communication_row["coef"] == 3
        assert communication_row["pending"] is True
        assert communication_row["appreciation"] == "Notes en attente"
        professional_category = category_for(after_subject_change, "Enseignements Professionnels Théoriques")
        assert professional_category["pending_count"] == 1
        assert professional_category["total_coef"] == 0  # only graded courses contribute to the total coefficient
        assert after_subject_change["overall_avg"] == 14.0  # pending subject remains excluded from official average
        assert after_subject_change["class_avg"] == 13.1
        assert after_subject_change["class_high"] == 14.0
        assert after_subject_change["class_low"] == 12.2
        assert after_subject_change["rank"] == 1
        assert after_subject_change["official_work_appreciation"] == "Compétences bien acquises (B+)"

    assert TEST_DB.exists()
    print("ANNUAL_BULLETIN_DATA_SYNC_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
