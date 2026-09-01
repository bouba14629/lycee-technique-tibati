import os
from pathlib import Path

TEST_DB = Path("/tmp/ltt-profile-password-change.sqlite")
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LTT_ENV"] = "development"
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FounderTest#2026")

from app import app  # noqa: E402
from models import User, db  # noqa: E402


ROLES = [
    "directeur",
    "censeur",
    "censeur_crm",
    "surveillant_general",
    "conseiller_orientation",
    "chef_travaux",
    "chef_crm",
    "enseignant",
    "eleve",
    "parent",
]


def main():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        for index, role in enumerate(ROLES):
            user = User(
                username=f"password.{index}",
                full_name=f"Utilisateur {index}",
                role=role,
                active=True,
                must_change_password=False,
            )
            user.set_password("AncienMot#2026")
            db.session.add(user)
        db.session.commit()

    with app.test_client() as client:
        for index, role in enumerate(ROLES):
            username = f"password.{index}"
            login = client.post(
                "/login",
                data={"username": username, "password": "AncienMot#2026"},
                follow_redirects=False,
            )
            assert login.status_code in (302, 303), role
            profile = client.get("/profil")
            assert profile.status_code == 200
            assert b"Mot de passe actuel" in profile.data
            assert b"Confirmer le nouveau mot de passe" in profile.data

            changed = client.post(
                "/profil",
                data={
                    "email": "",
                    "phone": "",
                    "current_password": "AncienMot#2026",
                    "new_password": f"NouveauMot#{index}2026",
                    "confirm_password": f"NouveauMot#{index}2026",
                },
                follow_redirects=False,
            )
            assert changed.status_code in (302, 303), role
            with app.app_context():
                user = User.query.filter_by(username=username).one()
                assert user.check_password(f"NouveauMot#{index}2026"), role
                assert not user.check_password("AncienMot#2026"), role
            client.get("/logout", follow_redirects=False)

        client.post(
            "/login",
            data={"username": "password.0", "password": "NouveauMot#02026"},
            follow_redirects=False,
        )
        with app.app_context():
            user = User.query.filter_by(username="password.0").one()
            previous_hash = user.password_hash
        invalid = client.post(
            "/profil",
            data={
                "current_password": "incorrect",
                "new_password": "AnotherMot#2026",
                "confirm_password": "AnotherMot#2026",
            },
            follow_redirects=False,
        )
        assert invalid.status_code in (302, 303)
        with app.app_context():
            user = User.query.filter_by(username="password.0").one()
            assert user.password_hash == previous_hash

    print("PROFILE_PASSWORD_CHANGE_TEST_OK")


if __name__ == "__main__":
    main()
