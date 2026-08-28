import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import User


def reset_proviseur_password():
    password = os.getenv("LTT_PROVISEUR_NEW_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("LTT_PROVISEUR_NEW_PASSWORD doit contenir au moins 12 caractères.")

    with app.app_context():
        user = User.query.filter_by(username="proviseur").one_or_none()
        if user is None:
            raise RuntimeError("Le compte proviseur est introuvable ; aucune donnée n’a été modifiée.")

        user.set_password(password)
        db.session.commit()
        print("PROVISEUR_PASSWORD_UPDATED")


if __name__ == "__main__":
    reset_proviseur_password()
