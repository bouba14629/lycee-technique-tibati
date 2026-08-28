import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User, Section, Department, SchoolClass
from reset_school_instance import reset_school_instance


def main():
    app.config.update(TESTING=True)
    os.environ["LTT_RESET_CONFIRM"] = "RESET_LTT"
    with app.app_context():
        db.drop_all()
        db.create_all()
        old_user = User(username="essai", role="enseignant", full_name="Compte d’essai")
        old_user.set_password("AncienTest#2026")
        section = Section(name="Section d’essai", code="E")
        department = Department(name="Filière d’essai", code="FE", section=section)
        school_class = SchoolClass(name="2nde FE", level="2nde", department=department)
        db.session.add_all([old_user, section, department, school_class])
        db.session.commit()

    founder_id = reset_school_instance()

    with app.app_context():
        founder = db.session.get(User, founder_id)
        assert User.query.count() == 1
        assert founder.username == "proviseur"
        assert founder.role == "directeur"
        assert founder.active is True and founder.must_change_password is True
        assert founder.plain_password is None
        assert founder.check_password("Lyttib")
        assert Section.query.count() == Department.query.count() == SchoolClass.query.count() == 0
    print("RESET_SCHOOL_INSTANCE_TEST_OK")


if __name__ == "__main__":
    main()
