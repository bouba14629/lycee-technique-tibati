import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Announcement, Department, Grade, Student, Teacher, User


def main():
    password = os.environ["LTT_INITIAL_ADMIN_PASSWORD"]
    app.config.update(TESTING=True)
    with app.app_context():
        founder = User.query.filter_by(username="proviseur", role="directeur").one()
        assert User.query.count() == 1
        assert founder.must_change_password is True
        assert founder.plain_password is None
        assert Student.query.count() == Teacher.query.count() == Department.query.count() == 0
        assert Grade.query.count() == Announcement.query.count() == 0

    with app.test_client() as client:
        login_page = client.get("/login")
        assert login_page.status_code == 200
        login = client.post("/login", data={"username": "proviseur", "password": password})
        assert login.status_code in (302, 303)
        assert "/premiere-connexion" in login.headers["Location"]
        dashboard = client.get("/dashboard")
        assert dashboard.status_code in (302, 303)
        assert "/premiere-connexion" in dashboard.headers["Location"]
    print("FOUNDER_PRODUCTION_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
