"""Remise à zéro volontaire d’une instance de démonstration LTT.

Exécuter uniquement avec LTT_CONFIRM_RESET=WIPE_FICTIONAL_DATA. La commande supprime
toutes les tables applicatives, recrée le schéma et initialise un unique Proviseur fondateur.
"""

import os

if os.getenv("LTT_CONFIRM_RESET") != "WIPE_FICTIONAL_DATA":
    raise SystemExit("Confirmation explicite requise : LTT_CONFIRM_RESET=WIPE_FICTIONAL_DATA")

from app import app
from models import User, db
from seed import bootstrap_founder


def main():
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        bootstrap_founder()
        founder = User.query.filter_by(role="directeur").one_or_none()
        if not founder or User.query.count() != 1 or not founder.must_change_password:
            raise RuntimeError("La création du compte Proviseur fondateur a échoué.")
        print(f"RESET_OK username={founder.username} users={User.query.count()}")


if __name__ == "__main__":
    main()
