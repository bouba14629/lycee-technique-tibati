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
        user = User(username="proviseur", role="directeur", full_name="Proviseur Test", must_change_password=False)
        user.set_password("Lyttib")
        db.session.add(user)
        db.session.commit()

    first_client = app.test_client()
    second_client = app.test_client()
    first_login = first_client.post("/login", data={"username": "proviseur", "password": "Lyttib"})
    assert first_login.status_code in (302, 303)
    with app.app_context():
        signed_in_user = User.query.filter_by(username="proviseur").one()
        first_token = signed_in_user.session_token
        assert signed_in_user.last_login_at is not None
        assert first_token
    second_login = second_client.post("/login", data={"username": "proviseur", "password": "Lyttib"})
    assert second_login.status_code in (302, 303)
    with app.app_context():
        second_token = User.query.filter_by(username="proviseur").one().session_token
        assert second_token and second_token != first_token
    first_dashboard = first_client.get("/dashboard")
    assert first_dashboard.status_code in (302, 303)
    assert "/login" in first_dashboard.headers["Location"]
    closed_session_login = first_client.get("/login")
    assert closed_session_login.status_code == 200
    assert b"Connexion interrompue" in closed_session_login.data
    second_dashboard = second_client.get("/dashboard")
    assert second_dashboard.status_code == 200
    print("SINGLE_SESSION_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
