import os
import sys

os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurTest#2026")
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import User


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        founder = User.query.filter_by(role="directeur").first()
        assert founder is not None
        assert founder.must_change_password is True
        assert founder.plain_password is None
        assert founder.check_password(os.environ["LTT_INITIAL_ADMIN_PASSWORD"])
    print("FOUNDER_BOOTSTRAP_SMOKE_TEST_OK")


if __name__ == "__main__":
    main()
