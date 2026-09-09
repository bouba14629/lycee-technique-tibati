"""Smoke test des rôles sur une base SQLite temporaire uniquement.

Ce test refuse toute DATABASE_URL non locale afin de ne jamais toucher aux comptes,
mots de passe ou données d’une instance active.
"""

import os
import sys
from pathlib import Path

DEFAULT_TEST_DB = Path("/tmp/ltt-role-smoke.sqlite")
configured_database_url = os.environ.get("DATABASE_URL", "")
configured_is_local = configured_database_url.startswith("sqlite:///") and (
    "/tmp/" in configured_database_url or ":memory:" in configured_database_url
)
if not configured_is_local:
    # Ne jamais hériter d’une URL active injectée dans l’environnement du shell.
    os.environ["DATABASE_URL"] = f"sqlite:///{DEFAULT_TEST_DB}"
os.environ.setdefault("LTT_ENV", "development")
os.environ["LTT_BOOTSTRAP_MODE"] = "demo"

DATABASE_URL = os.environ["DATABASE_URL"]
if not (DATABASE_URL.startswith("sqlite:///") and ("/tmp/" in DATABASE_URL or ":memory:" in DATABASE_URL)):
    raise RuntimeError("role_smoke_test.py exige une DATABASE_URL SQLite temporaire.")

sys.path.insert(0, os.path.dirname(__file__))

from app import app  # noqa: E402


ACCOUNTS = [
    ("directeur", "proviseur1", "Direction@2026"),
    ("censeur_stt", "censeur.stt", "CenseurSTT@2026"),
    ("censeur_ind", "censeur.ind", "CenseurIND@2026"),
    ("censeur_eg", "censeur.eg", "CenseurEG@2026"),
    ("censeur_crm", "censeur.crm", "CenseurCRM@2026"),
    ("surveillant", "surveillant.stt", "SurveilSTT@2026"),
    ("chef_travaux", "cheftravaux.stt", "TravauxSTT@2026"),
    ("chef_crm", "chefcrm1", "CentreCRM@2026"),
    ("orientation", "orientation1", "Orient@2026"),
    ("enseignant", "demo.aca", "Demo@2026"),
    ("eleve", "demo.eleve", "Demo@2026"),
    ("parent", "demo.parent", "Demo@2026"),
]


def main():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        for label, username, password in ACCOUNTS:
            client.get("/logout")
            login = client.post("/login", data={"username": username, "password": password})
            assert login.status_code in (302, 303), (label, login.status_code)
            dashboard = client.get("/dashboard")
            assert dashboard.status_code == 200, (label, dashboard.status_code)
            assert b"Erreur interne" not in dashboard.data, label
        print(f"ROLE_SMOKE_TEST_OK {len(ACCOUNTS)}")


if __name__ == "__main__":
    main()
