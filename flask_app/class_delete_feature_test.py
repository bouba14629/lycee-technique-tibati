import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import (db, User, Section, Department, Teacher, Subject, SchoolClass,
                    Course, PlannedAssessment)


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        principal = User(username="proviseur", role="directeur", full_name="Proviseur Test")
        principal.set_password("Lyttib")
        principal.must_change_password = False
        section = Section(name="Section test", code="T")
        department = Department(name="Filière test", code="FT", section=section)
        teacher_user = User(username="enseignant", role="enseignant", full_name="Enseignant Test")
        teacher_user.set_password("Test#2026")
        teacher = Teacher(user=teacher_user, department=department, grade="Grade libre")
        subject = Subject(name="Matière test", department=department)
        school_class = SchoolClass(name="2nde FT", level="2nde", department=department)
        db.session.add_all([principal, section, department, teacher_user, teacher, subject, school_class])
        db.session.flush()
        course = Course(subject=subject, teacher=teacher, school_class=school_class)
        db.session.add(course)
        db.session.flush()
        assessment = PlannedAssessment(course=course, term="Trimestre 1", sequence=1,
                                       title="Évaluation test", scheduled_date=school_class.school_year and __import__("datetime").date.today(),
                                       created_by=principal)
        db.session.add(assessment)
        db.session.commit()
        class_id = school_class.id

    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur", "password": "Lyttib"})
        assert login.status_code in (302, 303)
        deleted = client.get(f"/directeur/structure/classe/{class_id}/supprimer")
        assert deleted.status_code in (302, 303)

    with app.app_context():
        assert SchoolClass.query.get(class_id) is None
        assert Course.query.count() == 0
        assert PlannedAssessment.query.count() == 0
    print("CLASS_DELETE_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
