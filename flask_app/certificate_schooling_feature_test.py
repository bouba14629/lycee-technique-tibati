from datetime import date
from types import SimpleNamespace

from certificate_utils import render_schooling_certificate
from enseignant_routes import _parse_grade_value


assert _parse_grade_value("12,25") == 12.25
assert _parse_grade_value("12,75") == 12.75
assert _parse_grade_value("12.25") == 12.25

student = SimpleNamespace(
    id=1,
    first_name="Amina",
    last_name="Test",
    matricule="CERT-001",
    dob=date(2010, 4, 5),
    birth_place="Tibati",
    school_class=SimpleNamespace(name="PREMIERE ESF"),
    parents=[
        SimpleNamespace(user=SimpleNamespace(full_name="Parent Un")),
        SimpleNamespace(user=SimpleNamespace(full_name="Parent Deux")),
    ],
)

pdf = render_schooling_certificate(student, "2026-2027", "M. Proviseur")
content = pdf.read()
assert content.startswith(b"%PDF")
assert b"/Count 1" in content or b"/Pages" in content
print("CERTIFICATE_SCHOOLING_FEATURE_TEST_OK")
