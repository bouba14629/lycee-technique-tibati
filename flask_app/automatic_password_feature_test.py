import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User
from utils import generate_account_password


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        founder = User(username="proviseur", role="directeur", full_name="Proviseur Test", must_change_password=True)
        founder.set_password("Lyttib")
        founder.plain_password = None
        db.session.add(founder)
        db.session.commit()

        one = generate_account_password("Marie Nguemo", "enseignant")
        two = generate_account_password("Marie Nguemo", "enseignant")
        assert one.startswith("Ltt-ENS-MN") and one != two and len(one) >= 16

    with app.test_client() as client:
        assert client.post("/login", data={"username": "proviseur", "password": "Lyttib"}).status_code in (302, 303)
        proposal = client.get("/premiere-connexion")
        assert proposal.status_code == 200 and b"Mot de passe personnel g" in proposal.data
        with app.app_context():
            founder = User.query.filter_by(username="proviseur").one()
            generated_founder_password = founder.plain_password
            assert generated_founder_password and generated_founder_password.startswith("Ltt-DIR-PT")
            assert founder.check_password("Lyttib")
        assert client.post("/premiere-connexion", data={"action": "accept_generated"}).status_code in (302, 303)

        created = client.post("/directeur/utilisateurs/nouveau", data={
            "full_name": "Marie Nguemo", "role": "enseignant", "password": "SaisieManuelleInterdite!",
            "grade": "PLET", "hours_due": "18",
        })
        assert created.status_code in (302, 303)
        with app.app_context():
            teacher_user = User.query.filter_by(full_name="Marie Nguemo").one()
            assert teacher_user.must_change_password is True
            assert teacher_user.plain_password and teacher_user.plain_password.startswith("Ltt-ENS-MN")
            assert teacher_user.plain_password != "SaisieManuelleInterdite!"
            teacher_id = teacher_user.id
            previous_password = teacher_user.plain_password
        reset = client.post(f"/directeur/utilisateurs/{teacher_id}/reinitialiser")
        assert reset.status_code in (302, 303)
        with app.app_context():
            teacher_user = User.query.get(teacher_id)
            assert teacher_user.must_change_password is True
            assert teacher_user.plain_password and teacher_user.plain_password != previous_password
    print("AUTOMATIC_PASSWORD_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
