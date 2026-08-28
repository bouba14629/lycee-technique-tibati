import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User


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

    with app.test_client() as client:
        assert client.post("/login", data={"username": "proviseur", "password": "Lyttib"}).status_code in (302, 303)
        first_page = client.get("/premiere-connexion")
        assert first_page.status_code == 200
        assert b"Mot de passe personnel g" in first_page.data and b"generatedPassword" in first_page.data
        changed = client.post("/premiere-connexion", data={"action": "accept_generated"})
        assert changed.status_code in (302, 303) and "/dashboard" in changed.headers["Location"]
        with app.app_context():
            refreshed_founder = User.query.filter_by(username="proviseur").one()
            assert refreshed_founder.must_change_password is False
            assert refreshed_founder.plain_password and len(refreshed_founder.plain_password) >= 16
        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200
        assert b"Synth\xc3\xa8se de pilotage" in dashboard.data
        assert b"Effectifs et capacit\xc3\xa9" in dashboard.data
    print("FIRST_LOGIN_DASHBOARD_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
