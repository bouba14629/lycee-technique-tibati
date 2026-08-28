"""Réinitialise l’instance LTT à une base vierge avec son seul compte Proviseur.

Utilisation :
  LTT_RESET_CONFIRM=RESET_LTT python3 reset_school_instance.py

La confirmation explicite empêche toute exécution accidentelle contre la base persistante.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User


RESET_CONFIRMATION = "RESET_LTT"
INITIAL_USERNAME = "proviseur"
INITIAL_NAME = "Proviseur du Lycée Technique de Tibati"


def reset_school_instance():
    if os.getenv("LTT_RESET_CONFIRM") != RESET_CONFIRMATION:
        raise RuntimeError("Réinitialisation annulée : LTT_RESET_CONFIRM=RESET_LTT est requis.")
    initial_password = os.getenv("LTT_PROVISEUR_NEW_PASSWORD") or os.getenv("LTT_INITIAL_ADMIN_PASSWORD", "")
    if len(initial_password) < 12:
        raise RuntimeError("Un mot de passe proviseur sécurisé d’au moins 12 caractères est requis.")

    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

        founder = User(
            username=INITIAL_USERNAME,
            role="directeur",
            full_name=INITIAL_NAME,
            active=True,
            must_change_password=True,
        )
        founder.set_password(initial_password)
        # Aucun mot de passe n’est conservé en clair dans la base.
        founder.plain_password = None
        db.session.add(founder)
        db.session.commit()
        return founder.id


if __name__ == "__main__":
    founder_id = reset_school_instance()
    print(f"LTT_INSTANCE_RESET_OK founder_id={founder_id} username={INITIAL_USERNAME}")
