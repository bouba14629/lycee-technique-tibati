import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Announcement, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        author = User(username="proviseur.test", role="directeur", full_name="Proviseur Test")
        author.set_password("Lyttib")
        db.session.add(author)
        db.session.flush()
        db.session.add_all([
            Announcement(title="Rentrée générale", body="Les cours reprennent le lundi à 7 h 30.", target_role="tous", author_id=author.id),
            Announcement(title="Réunion enseignants", body="Annonce réservée aux enseignants.", target_role="enseignant", author_id=author.id),
        ])
        db.session.commit()

    with app.test_client() as client:
        page = client.get("/login")
        assert page.status_code == 200
        assert b"Communiqu" in page.data
        assert b"Rentr\xc3\xa9e g\xc3\xa9n\xc3\xa9rale" in page.data
        assert b"R\xc3\xa9union enseignants" not in page.data
    print("PUBLIC_ANNOUNCEMENT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
