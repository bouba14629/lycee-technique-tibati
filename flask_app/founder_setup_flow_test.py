import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Section


def main():
    initial_password = os.environ["LTT_INITIAL_ADMIN_PASSWORD"]
    app.config.update(TESTING=True)
    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur", "password": initial_password})
        assert "/premiere-connexion" in login.headers["Location"]
        first_login = client.post("/premiere-connexion", data={
            "password": "NouveauMotDePasse#2026",
            "confirmation": "NouveauMotDePasse#2026",
        })
        assert "/dashboard" in first_login.headers["Location"]
        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200
        assert b"D\xc3\xa9marrage de l\xe2\x80\x99\xc3\xa9tablissement" in dashboard.data
        assert b"Configurer l\xe2\x80\x99\xc3\xa9tablissement" in dashboard.data
        section_create = client.post("/directeur/structure/section/nouvelle", data={
            "name": "Section Pilote",
            "code": "PIL",
        })
        assert section_create.status_code in (302, 303)
        with app.app_context():
            assert Section.query.filter_by(code="PIL").count() == 1
        for path in ("/directeur/structure", "/directeur/utilisateurs", "/directeur/parametres"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
    print("FOUNDER_SETUP_FLOW_TEST_OK")


if __name__ == "__main__":
    main()
