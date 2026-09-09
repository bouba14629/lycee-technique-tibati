"""Smoke test local de connexion sur une base SQLite temporaire uniquement."""

import os
import sys
from pathlib import Path

DEFAULT_TEST_DB = Path("/tmp/ltt-smoke.sqlite")
configured_database_url = os.environ.get("DATABASE_URL", "")
configured_is_local = configured_database_url.startswith("sqlite:///") and (
    "/tmp/" in configured_database_url or ":memory:" in configured_database_url
)
if not configured_is_local:
    os.environ["DATABASE_URL"] = f"sqlite:///{DEFAULT_TEST_DB}"
os.environ.setdefault("LTT_ENV", "development")
os.environ["LTT_BOOTSTRAP_MODE"] = "demo"

if not (os.environ["DATABASE_URL"].startswith("sqlite:///") and (
    "/tmp/" in os.environ["DATABASE_URL"] or ":memory:" in os.environ["DATABASE_URL"]
)):
    raise RuntimeError("smoke_test.py exige une DATABASE_URL SQLite temporaire.")

sys.path.insert(0, os.path.dirname(__file__))

from app import app  # noqa: E402
from models import User  # noqa: E402


def main():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.test_client() as client:
        response = client.get("/login")
        assert response.status_code == 200, response.status_code
        response = client.post(
            "/login",
            data={"username": "proviseur1", "password": "Direction@2026"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303), response.status_code
        response = client.get("/dashboard")
        assert response.status_code == 200, response.status_code
        with app.app_context():
            assert User.query.count() > 0
    print("SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
