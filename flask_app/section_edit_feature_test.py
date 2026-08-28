import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Section, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        proviseur = User(username="proviseur.test", role="directeur", full_name="Proviseur Test")
        proviseur.set_password("Test#2026")
        industrial = Section(name="Industrielle", code="IND")
        commercial = Section(name="Commerciale", code="COM")
        db.session.add_all([proviseur, industrial, commercial])
        db.session.commit()
        industrial_id = industrial.id
        commercial_id = commercial.id

    client = app.test_client()
    login = client.post("/login", data={"username": "proviseur.test", "password": "Test#2026"})
    assert login.status_code in (302, 303)

    edited = client.post(
        f"/directeur/structure/section/{industrial_id}/modifier",
        data={"name": "Section Industrielle", "code": "SECTION-INDUSTRIELLE"},
    )
    assert edited.status_code in (302, 303)
    with app.app_context():
        section = db.session.get(Section, industrial_id)
        assert section.name == "Section Industrielle"
        assert section.code == "SECTION-INDUSTRIELLE"

    duplicate = client.post(
        f"/directeur/structure/section/{industrial_id}/modifier",
        data={"name": "Commerciale", "code": "COM"},
    )
    assert duplicate.status_code in (302, 303)
    with app.app_context():
        section = db.session.get(Section, industrial_id)
        assert section.name == "Section Industrielle"
        assert section.code == "SECTION-INDUSTRIELLE"
        assert db.session.get(Section, commercial_id).code == "COM"

    oversized = client.post(
        f"/directeur/structure/section/{industrial_id}/modifier",
        data={"name": "Section Industrielle", "code": "X" * 21},
    )
    assert oversized.status_code in (302, 303)
    with app.app_context():
        assert db.session.get(Section, industrial_id).code == "SECTION-INDUSTRIELLE"

    template = os.path.join(os.path.dirname(__file__), "templates", "dir_structure.html")
    content = open(template, encoding="utf-8").read()
    assert "sectionEdit{{ section.id }}Modal" in content
    assert "url_for('dir_section_edit', section_id=section.id)" in content
    assert content.count('maxlength="20"') >= 2
    assert content.index("Créer une section") < content.index("Ajouter une filière") < content.index("{% for section in sections %}")
    print("SECTION_EDIT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
