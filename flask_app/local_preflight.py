"""Préflight local obligatoire avant publication.

Il ne se connecte jamais à la base active : il force une base SQLite temporaire,
crée une structure de test, vérifie le garde-fou de suppression et s’arrête.
"""
import os
import tempfile


tmp_db = os.path.join(tempfile.gettempdir(), "ltt-local-preflight.sqlite")
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
os.environ["LTT_ENV"] = "development"

from app import app  # noqa: E402
from models import User, db  # noqa: E402

with app.app_context():
    db.drop_all()
    db.create_all()
    user = User(username="preflight-only", role="directeur", full_name="Préflight")
    user.set_password("PreflightOnly#2026")
    db.session.add(user)
    db.session.commit()
    assert User.query.count() == 1
    db.drop_all()

# Vérification indépendante du refus hors SQLite temporaire.
os.environ["DATABASE_URL"] = "mysql://production-guard-check"
from models import _safe_drop_all  # noqa: E402
try:
    _safe_drop_all()
except RuntimeError as exc:
    assert "interdit" in str(exc)
else:
    raise AssertionError("Le garde-fou n'a pas bloqué drop_all hors base temporaire")

print("LOCAL_PREFLIGHT_OK")
