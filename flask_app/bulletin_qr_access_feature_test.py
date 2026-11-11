"""Test d'accès QR bulletin : permissions, signature, année et rendu inline.

Lancer directement depuis ``flask_app/`` :
    python bulletin_qr_access_feature_test.py
"""

import os
from io import BytesIO
from urllib.parse import urlsplit
from unittest.mock import patch

DATABASE_URL = "sqlite:////tmp/ltt-bulletin-qr-access.sqlite"
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ.setdefault("LTT_ENV", "development")
os.environ.setdefault("LTT_INITIAL_ADMIN_PASSWORD", "FoundateurQR#2026")

assert DATABASE_URL.startswith("sqlite:////tmp/"), "refus de drop_all hors SQLite temporaire"

from app import app  # noqa: E402
from bulletin_qr import (  # noqa: E402
    QR_SALT,
    build_bulletin_qr_url,
    register_bulletin_qr_routes,
)
from itsdangerous import URLSafeSerializer  # noqa: E402
from models import (  # noqa: E402
    AppSetting,
    Department,
    Section,
    SchoolClass,
    Student,
    User,
    db,
)


def add_user(username, role, section_id=None):
    user = User(
        username=username,
        full_name=username,
        role=role,
        active=True,
        section_id=section_id,
        must_change_password=False,
    )
    user.set_password("Test#2026")
    db.session.add(user)
    db.session.flush()
    return user


def login(client, username):
    response = client.post(
        "/login", data={"username": username, "password": "Test#2026"}
    )
    assert response.status_code in (302, 303), response.status_code


def token_from(url):
    return urlsplit(url).path.rsplit("/", 1)[-1]


with app.app_context():
    assert db.engine.url.drivername == 'sqlite' and db.engine.url.database == '/tmp/ltt-bulletin-qr-access.sqlite'
    db.drop_all()
    db.create_all()

    setting = AppSetting(current_school_year="2026-2027")
    db.session.add(setting)
    section_a = Section(name="Section QR A", code="QRA")
    section_b = Section(name="Section QR B", code="QRB")
    db.session.add_all([section_a, section_b])
    db.session.flush()
    department_a = Department(name="Département QR A", code="QRA", section_id=section_a.id)
    department_b = Department(name="Département QR B", code="QRB", section_id=section_b.id)
    db.session.add_all([department_a, department_b])
    db.session.flush()
    class_a = SchoolClass(
        name="Classe QR A", level="Test", department_id=department_a.id, school_year="2026-2027"
    )
    class_b = SchoolClass(
        name="Classe QR B", level="Test", department_id=department_b.id, school_year="2026-2027"
    )
    db.session.add_all([class_a, class_b])
    db.session.flush()

    director = add_user("director.qr", "directeur")
    censeur_a = add_user("censeur.qr.a", "censeur", section_id=section_a.id)
    censeur_b = add_user("censeur.qr.b", "censeur", section_id=section_b.id)
    teacher = add_user("teacher.qr", "enseignant")
    student_user_a = add_user("student.qr.a", "eleve")
    student_user_b = add_user("student.qr.b", "eleve")
    parent_user_a = add_user("parent.qr.a", "parent")
    parent_user_b = add_user("parent.qr.b", "parent")

    student_a = Student(
        user_id=student_user_a.id,
        class_id=class_a.id,
        matricule="QR-A-001",
        first_name="Alice",
        last_name="QR",
    )
    student_b = Student(
        user_id=student_user_b.id,
        class_id=class_b.id,
        matricule="QR-B-001",
        first_name="Bob",
        last_name="QR",
    )
    from models import Parent  # noqa: E402

    parent_a = Parent(user_id=parent_user_a.id)
    parent_b = Parent(user_id=parent_user_b.id)
    db.session.add_all([student_a, student_b, parent_a, parent_b])
    db.session.flush()
    parent_a.children.append(student_a)
    parent_b.children.append(student_b)
    db.session.commit()

    register_bulletin_qr_routes(app)
    assert "bulletin_qr_access" in app.view_functions

    # URL signing is deterministic for payload/context and does not carry notes.
    quarterly_url = build_bulletin_qr_url(
        student_a,
        {"overall_avg": 19, "notes": "NE DOIT JAMAIS ÊTRE DANS LE QR"},
        school_year="2026-2027",
        term="Trimestre 1",
    )
    annual_url = build_bulletin_qr_url(
        student_a,
        {"overall_avg": 1},
        school_year="2026-2027",
        term="Annuel",
    )
    other_term_url = build_bulletin_qr_url(
        student_a, {}, school_year="2026-2027", term="Trimestre 2"
    )
    assert quarterly_url.startswith("https://lt-tibati.com/bulletins/qr/")
    assert len({quarterly_url, annual_url, other_term_url}) == 3
    assert "NE%20DOIT" not in quarterly_url and "notes" not in quarterly_url
    decoded = URLSafeSerializer(app.config["SECRET_KEY"], salt=QR_SALT).loads(
        token_from(quarterly_url)
    )
    assert decoded == {"s": student_a.id, "t": "Trimestre 1", "y": "2026-2027"}

    # Host injection is rejected; the documented host is accepted.
    with app.test_request_context("/", base_url="https://evil.example"):
        assert build_bulletin_qr_url(student_a, {}, "2026-2027", "Annuel").startswith(
            "https://lt-tibati.com/"
        )
    with app.test_request_context(
        "/", base_url="https://lyceetech-njuwbcl2.manus.space"
    ):
        assert build_bulletin_qr_url(student_a, {}, "2026-2027", "Annuel").startswith(
            "https://lyceetech-njuwbcl2.manus.space/"
        )

    quarterly_token = token_from(quarterly_url)
    annual_token = token_from(annual_url)
    render_calls = []

    def fake_render(template_name, **context):
        render_calls.append((template_name, context))
        return BytesIO(b"%PDF-QR-test")

    def fake_photo(student, *args, **kwargs):
        return None

    def fake_quarterly_data(student, term=None, **kwargs):
        return {"student_id": student.id, "term": term}

    def fake_annual_data(student, **kwargs):
        return {"student_id": student.id, "annual": True}

    with patch("pdf_utils.render_pdf", side_effect=fake_render), patch(
        "pdf_utils.get_student_photo_source", side_effect=fake_photo
    ), patch("bulletin_qr.bulletin_data", side_effect=fake_quarterly_data), patch(
        "bulletin_qr.annual_bulletin_data", side_effect=fake_annual_data
    ):
        # Le retour après connexion n'accepte que le chemin local du QR.
        with app.test_client() as client:
            anonymous = client.get(f"/bulletins/qr/{quarterly_token}")
            assert anonymous.status_code in (302, 303)
            assert urlsplit(anonymous.headers["Location"]).path == "/login"
            assert "next=" in anonymous.headers["Location"]
            result = client.post(anonymous.headers['Location'], data={'username':'director.qr', 'password':'Test#2026'})
            assert urlsplit(result.headers['Location']).path == f'/bulletins/qr/{quarterly_token}'
            assert client.get(result.headers['Location']).data.startswith(b'%PDF')
        with app.test_client() as client:
            result = client.post('/login?next=https://attacker.example', data={'username':'director.qr', 'password':'Test#2026'})
            assert urlsplit(result.headers['Location']).path == '/dashboard'

        # Invalid signature is never decoded into a student lookup.
        with app.test_client() as client:
            invalid = client.get(f"/bulletins/qr/{quarterly_token[:-1]}x")
            assert invalid.status_code == 404

        # The student may read only the matching identity; a parent may read
        # only the existing many-to-many child relation.
        with app.test_client() as client:
            login(client, "student.qr.a")
            own = client.get(f"/bulletins/qr/{quarterly_token}")
            assert own.status_code == 200 and own.mimetype == 'text/html'
            assert not own.data.startswith(b"%PDF")
            cross = client.get(
                f"/bulletins/qr/{token_from(build_bulletin_qr_url(student_b, {}, '2026-2027', 'Trimestre 1'))}"
            )
            assert cross.status_code == 403

        with app.test_client() as client:
            login(client, "parent.qr.a")
            own = client.get(f"/bulletins/qr/{quarterly_token}")
            assert own.status_code == 200 and own.mimetype == 'text/html'
            assert not own.data.startswith(b"%PDF")
            cross = client.get(
                f"/bulletins/qr/{token_from(build_bulletin_qr_url(student_b, {}, '2026-2027', 'Trimestre 1'))}"
            )
            assert cross.status_code == 403

        # A censeur can access only classes in the actual section scope;
        # teachers and other unlisted roles remain denied by default.
        with app.test_client() as client:
            login(client, "censeur.qr.a")
            assert client.get(f"/bulletins/qr/{quarterly_token}").status_code == 200
            b_token = token_from(
                build_bulletin_qr_url(student_b, {}, "2026-2027", "Trimestre 1")
            )
            assert client.get(f"/bulletins/qr/{b_token}").status_code == 403

        with app.test_client() as client:
            login(client, "censeur.qr.b")
            assert client.get(f"/bulletins/qr/{quarterly_token}").status_code == 403

        with app.test_client() as client:
            login(client, "teacher.qr")
            assert client.get(f"/bulletins/qr/{quarterly_token}").status_code == 403

        with app.test_client() as client:
            login(client, "director.qr")
            quarterly = client.get(f"/bulletins/qr/{quarterly_token}")
            annual = client.get(f"/bulletins/qr/{annual_token}")
            assert quarterly.status_code == 200 and annual.status_code == 200
            assert render_calls[-2][0] == "pdf/bulletin_pdf.html"
            assert render_calls[-1][0] == "pdf/bulletin_annual_pdf.html"
            assert render_calls[-2][1]["data"]["student_id"] == student_a.id
            assert render_calls[-1][1]["data"]["student_id"] == student_a.id

        # A token from another school year is expired, rather than rendering
        # data mixed with the current school year.
        old_token = token_from(
            build_bulletin_qr_url(student_a, {}, "2025-2026", "Trimestre 1")
        )
        with app.test_client() as client:
            login(client, "director.qr")
            assert client.get(f"/bulletins/qr/{old_token}").status_code == 410

        # Deleted students do not leave a usable QR token.
        deleted_token = token_from(
            build_bulletin_qr_url(student_b, {}, "2026-2027", "Annuel")
        )
        db.session.delete(student_b)
        db.session.commit()
        with app.test_client() as client:
            login(client, "director.qr")
            assert client.get(f"/bulletins/qr/{deleted_token}").status_code == 404

print("BULLETIN_QR_ACCESS_FEATURE_TEST_OK")
