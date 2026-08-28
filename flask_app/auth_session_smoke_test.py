import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/ltt-auth-session-smoke.sqlite")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")
sys.path.insert(0, os.path.dirname(__file__))

from app import app


def main():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.post(
            "/login",
            data={"username": "proviseur", "password": os.environ["LTT_INITIAL_ADMIN_PASSWORD"]},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303), response.status_code
        assert response.headers.get("Location"), "La connexion doit rediriger vers une page protégée."

        protected = client.get("/dashboard")
        assert protected.status_code in (200, 302, 303), protected.status_code
        assert b"Connexion" not in protected.data or protected.status_code != 200

        logout = client.get("/logout", follow_redirects=False)
        assert logout.status_code in (302, 303), logout.status_code

    print("AUTH_SESSION_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
