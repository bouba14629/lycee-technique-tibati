"""Restaure uniquement l’accès du compte Proviseur initial.

Ce script ne supprime aucune donnée scolaire. Il corrige les comptes de test créés
accidentellement dans une instance vierge et rétablit le compte attendu « proviseur ».
"""

import os

from app import app, db
from models import User


INITIAL_USERNAME = "proviseur"
INITIAL_PASSWORD = os.environ["LTT_PROVISEUR_NEW_PASSWORD"]


def main():
    with app.app_context():
        proviseur = User.query.filter_by(username=INITIAL_USERNAME).first()
        test_proviseur = User.query.filter_by(username="proviseur.test").first()

        if not proviseur and test_proviseur:
            proviseur = test_proviseur
            proviseur.username = INITIAL_USERNAME

        if not proviseur:
            proviseur = User(username=INITIAL_USERNAME, role="directeur", full_name="Proviseur")
            db.session.add(proviseur)

        proviseur.role = "directeur"
        proviseur.full_name = "Proviseur"
        proviseur.active = True
        proviseur.must_change_password = True
        proviseur.session_token = None
        proviseur.set_password(INITIAL_PASSWORD)

        db.session.commit()
        print("PROVISEUR_ACCESS_RESTORED")


if __name__ == "__main__":
    main()
