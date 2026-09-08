import os
os.environ["DATABASE_URL"] = "sqlite:////tmp/ltt-isolated-restore_proviseur_access_feature_test.sqlite"
os.environ["LTT_ENV"] = "development"
os.environ.setdefault("LTT_PROVISEUR_NEW_PASSWORD", "TestRestore#2026")

import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import User, db
from restore_proviseur_access import main as restore_proviseur_access


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        test_proviseur = User(username="proviseur.test", role="directeur", full_name="Proviseur Test")
        test_proviseur.set_password("AncienMotDePasse")
        test_teacher = User(username="enseignant.test", role="enseignant", full_name="Enseignant Test")
        test_teacher.set_password("AncienMotDePasse")
        db.session.add_all([test_proviseur, test_teacher])
        db.session.commit()

    restore_proviseur_access()

    with app.app_context():
        proviseur = User.query.filter_by(username="proviseur").one()
        teacher = User.query.filter_by(username="enseignant.test").one()
        assert proviseur.role == "directeur"
        assert proviseur.active is True
        assert proviseur.must_change_password is True
        assert proviseur.check_password(os.environ["LTT_PROVISEUR_NEW_PASSWORD"])
        assert teacher.active is True

    with app.test_client() as client:
        response = client.post("/login", data={"username": "proviseur", "password": os.environ["LTT_PROVISEUR_NEW_PASSWORD"]})
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/premiere-connexion")

    print("RESTORE_PROVISEUR_ACCESS_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
